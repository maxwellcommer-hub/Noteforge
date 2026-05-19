import os, subprocess, tempfile, json, glob
from flask import Flask, request, jsonify, send_file, send_from_directory, Response
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR)
CORS(app)

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/sounds/<path:filename>')
def sounds(filename):
    sounds_dir = os.path.join(BASE_DIR, 'sounds')
    return send_from_directory(sounds_dir, filename)

@app.route('/sounds-list')
def sounds_list():
    sounds_dir = os.path.join(BASE_DIR, 'sounds')
    files = []
    if os.path.exists(sounds_dir):
        files = [os.path.basename(f) for f in glob.glob(os.path.join(sounds_dir, '*.ogg'))]
    return jsonify({'sounds': files})

# YouTube: download audio server-side and stream back as MP3
# - Avoids CORS entirely (browser never touches YouTube directly)
# - bgutil-ytdlp-pot-provider plugin auto-handles bot detection if installed
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
        # Get title
        title = 'YouTube Audio'
        try:
            tr = subprocess.run(
                ['yt-dlp', '--no-playlist', '--get-title', '--no-warnings', url],
                capture_output=True, text=True, timeout=20
            )
            if tr.stdout.strip():
                title = tr.stdout.strip().splitlines()[0]
        except Exception:
            pass

        # Download and convert to MP3 server-side
        dl = subprocess.run(
            ['yt-dlp',
             '--no-playlist',
             '--format', 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio',
             '--extract-audio',
             '--audio-format', 'mp3',
             '--audio-quality', '192K',
             '--no-warnings',
             '--output', out_template,
             url],
            capture_output=True, text=True, timeout=90
        )

        if dl.returncode != 0:
            err = dl.stderr.strip()
            lines = [l for l in err.splitlines() if 'ERROR' in l or 'error' in l.lower()]
            msg = lines[-1] if lines else err[-300:] if err else 'Unknown error'
            return jsonify({'error': msg}), 500

        # Find output file
        mp3_path = os.path.join(tmp_dir, 'audio.mp3')
        if not os.path.exists(mp3_path):
            candidates = [f for f in os.listdir(tmp_dir) if f.startswith('audio')]
            if not candidates:
                return jsonify({'error': 'Download produced no output file'}), 500
            mp3_path = os.path.join(tmp_dir, candidates[0])

        def stream_and_cleanup():
            try:
                with open(mp3_path, 'rb') as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        yield chunk
            finally:
                import shutil
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
        return jsonify({'error': 'Download timed out — try a shorter song'}), 500
    except FileNotFoundError:
        return jsonify({'error': 'yt-dlp not installed on server'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
