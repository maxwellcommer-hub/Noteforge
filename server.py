import os, subprocess, tempfile, json, glob, shutil
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR)
CORS(app)

COOKIES_FILE = '/tmp/yt_cookies.txt'

def write_cookies():
    env = os.environ.get('YOUTUBE_COOKIES', '').strip()
    if not env:
        return False
    env = env.replace('\\t', '\t').replace('\\n', '\n')
    lines = [l.strip() for l in env.splitlines() if l.strip()]
    with open(COOKIES_FILE, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    return True

def cookie_args():
    if write_cookies():
        return ['--cookies', COOKIES_FILE]
    return []

def find_bgutil_script():
    """Find the built bgutil generate_once.js script."""
    patterns = [
        '/usr/local/lib/python3.11/site-packages/bgutil_ytdlp_pot_provider*/server/build/generate_once.js',
        '/usr/local/lib/python*/site-packages/bgutil_ytdlp_pot_provider*/server/build/generate_once.js',
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None

def get_yt_args(url, out_template):
    """Build the best yt-dlp argument list for the current environment."""
    ck = cookie_args()
    bgutil = find_bgutil_script()
    base = ['yt-dlp', '--no-playlist', '--no-warnings', '-o', out_template]
    
    strategies = []
    
    # Strategy 1: mweb client + bgutil PO token (best for server IPs, 2025+ fix)
    # mweb client with cookies gives us real HTTP formats, not SABR
    if bgutil and ck:
        strategies.append(base + [
            '--extractor-args', f'youtube:player_client=mweb;po_token=mweb.player+auto',
            '--js-runtimes', 'node',
        ] + ck + [url])
    
    # Strategy 2: mweb with cookies, no explicit PO token (bgutil handles it automatically)
    if ck:
        strategies.append(base + [
            '--extractor-args', 'youtube:player_client=mweb',
            '-f', 'bestaudio/best',
        ] + ck + [url])

    # Strategy 3: ios client (doesn't need PO tokens at all)
    strategies.append(base + [
        '--extractor-args', 'youtube:player_client=ios',
        '-f', 'bestaudio/best',
    ] + ck + [url])
    
    # Strategy 4: tv_embedded client
    strategies.append(base + [
        '--extractor-args', 'youtube:player_client=tv_embedded',
        '-f', 'bestaudio/best',
    ] + ck + [url])
    
    # Strategy 5: android client
    strategies.append(base + [
        '--extractor-args', 'youtube:player_client=android',
        '-f', 'bestaudio/best',
    ] + ck + [url])
    
    # Strategy 6: force missing_pot formats (allows SABR formats through)
    strategies.append(base + [
        '--extractor-args', 'youtube:formats=missing_pot',
        '-f', 'bestaudio/best',
    ] + ck + [url])
    
    # Strategy 7: absolute fallback — no format filter, no client override
    strategies.append(base + ck + [url])
    
    return strategies

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/sounds/<path:filename>')
def sounds(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'sounds'), filename)

@app.route('/sounds-list')
def sounds_list():
    d = os.path.join(BASE_DIR, 'sounds')
    files = [os.path.basename(f) for f in glob.glob(os.path.join(d, '*.ogg'))] if os.path.exists(d) else []
    return jsonify({'sounds': files})

@app.route('/debug')
def debug():
    write_cookies()
    bgutil = find_bgutil_script()
    node_ver = subprocess.run(['node', '--version'], capture_output=True, text=True).stdout.strip()
    ytdlp_ver = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True).stdout.strip()
    sounds = glob.glob(os.path.join(BASE_DIR, 'sounds', '*.ogg'))
    return jsonify({
        'yt_dlp_version': ytdlp_ver,
        'node_version': node_ver,
        'bgutil_script': bgutil,
        'bgutil_found': bool(bgutil),
        'cookies_set': bool(os.environ.get('YOUTUBE_COOKIES')),
        'cookies_file_lines': len(open(COOKIES_FILE).readlines()) if os.path.exists(COOKIES_FILE) else 0,
        'sounds_count': len(sounds),
        'sounds': [os.path.basename(s) for s in sounds],
    })

@app.route('/ytdl', methods=['POST'])
def ytdl():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    if 'youtube.com' not in url and 'youtu.be' not in url:
        return jsonify({'error': 'Not a YouTube URL'}), 400

    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, 'audio.%(ext)s')

    # Get title first (quick)
    title = 'YouTube Audio'
    try:
        tr = subprocess.run(
            ['yt-dlp', '--no-playlist', '--get-title', '--no-warnings']
            + cookie_args() + [url],
            capture_output=True, text=True, timeout=20)
        if tr.returncode == 0 and tr.stdout.strip():
            title = tr.stdout.strip().splitlines()[0]
    except Exception:
        pass

    try:
        last_err = ''
        success = False
        for cmd in get_yt_args(url, out):
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                success = True
                break
            last_err = r.stderr.strip()

        if not success:
            err_lines = [l for l in last_err.splitlines() if 'ERROR' in l]
            msg = err_lines[-1] if err_lines else last_err[-400:] if last_err else 'All download strategies failed'
            if 'Sign in' in msg or 'bot' in msg.lower():
                msg = 'YouTube bot check failed. Re-export your cookies from browser and update YOUTUBE_COOKIES in Railway.'
            elif 'format' in msg.lower():
                msg = f'No downloadable format found. Full error: {last_err[-300:]}'
            return jsonify({'error': msg}), 500

        # Find output file
        files = [f for f in os.listdir(tmp) if f.startswith('audio') and not f.endswith('.part')]
        if not files:
            return jsonify({'error': 'No output file produced'}), 500

        src = os.path.join(tmp, files[0])
        mp3 = os.path.join(tmp, 'out.mp3')
        subprocess.run(
            ['ffmpeg', '-i', src, '-vn', '-ar', '44100', '-ac', '2', '-b:a', '192k', '-y', mp3],
            capture_output=True, timeout=60)
        final = mp3 if os.path.exists(mp3) else src

        def stream():
            try:
                with open(final, 'rb') as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk: break
                        yield chunk
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

        safe_title = title.encode('ascii', 'replace').decode('ascii')
        return Response(stream(), mimetype='audio/mpeg',
            headers={'X-Song-Title': safe_title})

    except subprocess.TimeoutExpired:
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify({'error': 'Download timed out — try a shorter song'}), 500
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
