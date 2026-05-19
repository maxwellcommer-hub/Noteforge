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
    with open(COOKIES_FILE, 'w') as f:
        f.write('\n'.join(l.strip() for l in env.splitlines() if l.strip()) + '\n')
    return True

def cookie_args():
    if write_cookies():
        return ['--cookies', COOKIES_FILE]
    return []

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
    return jsonify({
        'cookies_env_set': bool(os.environ.get('YOUTUBE_COOKIES')),
        'cookies_file_exists': os.path.exists(COOKIES_FILE),
        'cookies_file_lines': len(open(COOKIES_FILE).readlines()) if os.path.exists(COOKIES_FILE) else 0,
        'sounds_count': len(glob.glob(os.path.join(BASE_DIR, 'sounds', '*.ogg'))),
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
    ck = cookie_args()

    try:
        # Get title
        title = 'YouTube Audio'
        try:
            tr = subprocess.run(
                ['yt-dlp', '--no-playlist', '--get-title', '--no-warnings'] + ck + [url],
                capture_output=True, text=True, timeout=20)
            if tr.returncode == 0 and tr.stdout.strip():
                title = tr.stdout.strip().splitlines()[0]
        except Exception:
            pass

        # Try strategies in order — bestaudio without format restriction first
        strategies = []
        if ck:
            strategies.append(['yt-dlp', '--no-playlist', '--no-warnings',
                '-f', 'bestaudio', '-o', out] + ck + [url])
        strategies += [
            # No format filter — just grab whatever works
            ['yt-dlp', '--no-playlist', '--no-warnings',
             '-f', 'bestaudio', '-o', out] + ck + [url],
            # iOS client
            ['yt-dlp', '--no-playlist', '--no-warnings',
             '--extractor-args', 'youtube:player_client=ios',
             '-o', out] + ck + [url],
            # Any format at all
            ['yt-dlp', '--no-playlist', '--no-warnings',
             '-o', out] + ck + [url],
        ]

        last_err = ''
        ok = False
        for cmd in strategies:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                ok = True
                break
            last_err = r.stderr.strip()

        if not ok:
            lines = [l for l in last_err.splitlines() if 'ERROR' in l]
            msg = lines[-1] if lines else last_err[-300:] if last_err else 'Download failed'
            if 'Sign in' in msg or 'bot' in msg.lower():
                msg = 'YouTube bot check failed. Try re-exporting cookies from your browser and updating YOUTUBE_COOKIES in Railway.'
            elif 'format' in msg.lower():
                msg = 'No audio format available for this video. Try a different video.'
            return jsonify({'error': msg}), 500

        # Find file
        files = [f for f in os.listdir(tmp) if f.startswith('audio') and not f.endswith('.part')]
        if not files:
            return jsonify({'error': 'No output file produced'}), 500

        src = os.path.join(tmp, files[0])
        mp3 = os.path.join(tmp, 'out.mp3')

        # Convert to MP3
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

        return Response(stream(), mimetype='audio/mpeg',
            headers={'X-Song-Title': title.encode('ascii','replace').decode('ascii')})

    except subprocess.TimeoutExpired:
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify({'error': 'Timed out — try a shorter song'}), 500
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
