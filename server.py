import os, subprocess, tempfile, json, glob, shutil
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR)
CORS(app)

COOKIES_FILE = os.path.join(BASE_DIR, 'yt_cookies.txt')

def get_cookies_args():
    """Return yt-dlp cookie args if cookies are available."""
    # Check env var first (set in Railway dashboard)
    cookies_env = os.environ.get('YOUTUBE_COOKIES', '').strip()
    if cookies_env:
        # Write env var content to temp file on first use
        if not os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'w') as f:
                f.write(cookies_env)
        return ['--cookies', COOKIES_FILE]
    # Check if cookies file was manually placed
    if os.path.exists(COOKIES_FILE):
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
    sounds_dir = os.path.join(BASE_DIR, 'sounds')
    files = []
    if os.path.exists(sounds_dir):
        files = [os.path.basename(f) for f in glob.glob(os.path.join(sounds_dir, '*.ogg'))]
    return jsonify({'sounds': files})

@app.route('/ytdl', methods=['POST'])
def ytdl():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    if 'youtube.com' not in url and 'youtu.be' not in url:
        return jsonify({'error': 'Not a YouTube URL'}), 400

    tmp_dir = tempfile.mkdtemp()
    out_template = os.path.join(tmp_dir, 'audio.%(ext)s')
    cookie_args = get_cookies_args()

    try:
        # Get title
        title = 'YouTube Audio'
        try:
            tr = subprocess.run(
                ['yt-dlp', '--no-playlist', '--get-title', '--no-warnings']
                + cookie_args + [url],
                capture_output=True, text=True, timeout=20
            )
            if tr.returncode == 0 and tr.stdout.strip():
                title = tr.stdout.strip().splitlines()[0]
        except Exception:
            pass

        # Download audio — try multiple client strategies
        dl = None
        strategies = [
            # Strategy 1: with cookies if available (most reliable)
            ['yt-dlp', '--no-playlist', '--no-warnings',
             '-f', 'bestaudio[ext=m4a]/bestaudio',
             '-o', out_template] + cookie_args + [url],
            # Strategy 2: iOS client (no cookies needed, usually works)
            ['yt-dlp', '--no-playlist', '--no-warnings',
             '--extractor-args', 'youtube:player_client=ios',
             '-f', 'bestaudio',
             '-o', out_template, url],
            # Strategy 3: tv_embedded client (different bot detection)
            ['yt-dlp', '--no-playlist', '--no-warnings',
             '--extractor-args', 'youtube:player_client=tv_embedded',
             '-f', 'bestaudio',
             '-o', out_template, url],
        ]

        last_err = ''
        for cmd in strategies:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                dl = result
                break
            last_err = result.stderr.strip()

        if dl is None:
            lines = [l for l in last_err.splitlines() if 'ERROR' in l]
            msg = lines[-1] if lines else last_err[-300:] if last_err else 'All download strategies failed'
            # Give helpful hint if it's the bot check error
            if 'Sign in' in msg or 'bot' in msg.lower():
                msg += '\n\nFix: Add your YouTube cookies to Railway environment variables. See the app README for instructions.'
            return jsonify({'error': msg}), 500

        # Find output file
        files = [f for f in os.listdir(tmp_dir) if f.startswith('audio') and not f.endswith('.part')]
        if not files:
            return jsonify({'error': 'Download produced no output file'}), 500

        audio_path = os.path.join(tmp_dir, files[0])

        # Convert to MP3
        mp3_path = os.path.join(tmp_dir, 'final.mp3')
        ffmpeg = subprocess.run(
            ['ffmpeg', '-i', audio_path, '-vn', '-ar', '44100',
             '-ac', '2', '-b:a', '192k', '-y', mp3_path],
            capture_output=True, timeout=60
        )
        if ffmpeg.returncode != 0 or not os.path.exists(mp3_path):
            mp3_path = audio_path  # serve raw if ffmpeg fails

        def stream_and_cleanup():
            try:
                with open(mp3_path, 'rb') as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        yield chunk
            finally:
                try:
                    shutil.rmtree(tmp_dir)
                except Exception:
                    pass

        safe_title = title.encode('ascii', 'replace').decode('ascii')
        return Response(
            stream_and_cleanup(),
            mimetype='audio/mpeg',
            headers={'X-Song-Title': safe_title}
        )

    except subprocess.TimeoutExpired:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({'error': 'Download timed out — try a shorter song'}), 500
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    has_cookies = bool(os.environ.get('YOUTUBE_COOKIES') or os.path.exists(COOKIES_FILE))
    return jsonify({'status': 'ok', 'youtube_cookies': has_cookies})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
