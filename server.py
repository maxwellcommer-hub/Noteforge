import os, subprocess, tempfile, json, glob, shutil
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR)
CORS(app)

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

    try:
        # Get title separately (fast, non-blocking)
        title = 'YouTube Audio'
        try:
            tr = subprocess.run(
                ['yt-dlp', '--no-playlist', '--get-title', '--no-warnings',
                 '--extractor-args', 'youtube:player_client=ios', url],
                capture_output=True, text=True, timeout=20
            )
            if tr.returncode == 0 and tr.stdout.strip():
                title = tr.stdout.strip().splitlines()[0]
        except Exception:
            pass

        # Download audio using iOS client (avoids bot detection better than web client)
        # iOS client returns m4a audio formats that don't need PO tokens
        dl = subprocess.run(
            ['yt-dlp',
             '--no-playlist',
             '--no-warnings',
             '--extractor-args', 'youtube:player_client=ios',
             '-f', 'bestaudio',
             '-o', out_template,
             '--ffmpeg-location', '/usr/bin/ffmpeg',
             url],
            capture_output=True, text=True, timeout=120
        )

        if dl.returncode != 0:
            # Fallback: try android client
            dl = subprocess.run(
                ['yt-dlp',
                 '--no-playlist',
                 '--no-warnings',
                 '--extractor-args', 'youtube:player_client=android',
                 '-f', 'bestaudio',
                 '-o', out_template,
                 url],
                capture_output=True, text=True, timeout=120
            )

        if dl.returncode != 0:
            err = dl.stderr.strip()
            lines = [l for l in err.splitlines() if 'ERROR' in l]
            msg = lines[-1] if lines else err[-400:] if err else 'Download failed'
            return jsonify({'error': msg}), 500

        # Find downloaded file (could be .m4a, .webm, .opus, etc)
        files = [f for f in os.listdir(tmp_dir) if f.startswith('audio') and not f.endswith('.part')]
        if not files:
            return jsonify({'error': 'Download produced no output file'}), 500

        audio_path = os.path.join(tmp_dir, files[0])
        ext = os.path.splitext(files[0])[1].lower()

        # Convert to MP3 with ffmpeg if not already mp3/m4a
        mp3_path = os.path.join(tmp_dir, 'final.mp3')
        ffmpeg = subprocess.run(
            ['ffmpeg', '-i', audio_path, '-vn', '-ar', '44100', '-ac', '2',
             '-b:a', '192k', '-y', mp3_path],
            capture_output=True, timeout=60
        )
        if ffmpeg.returncode != 0 or not os.path.exists(mp3_path):
            # Just serve the raw file if ffmpeg fails
            mp3_path = audio_path

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
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
