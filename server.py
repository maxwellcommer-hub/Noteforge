import os, subprocess, tempfile, json, glob
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR)
CORS(app)

# ── Serve the main app
@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

# ── Serve Minecraft sound files from /sounds folder
@app.route('/sounds/<path:filename>')
def sounds(filename):
    sounds_dir = os.path.join(os.path.dirname(__file__), 'sounds')
    return send_from_directory(sounds_dir, filename)

# ── List available sounds (so frontend knows what loaded)
@app.route('/sounds-list')
def sounds_list():
    sounds_dir = os.path.join(os.path.dirname(__file__), 'sounds')
    files = []
    if os.path.exists(sounds_dir):
        files = [os.path.basename(f) for f in glob.glob(os.path.join(sounds_dir, '*.ogg'))]
    return jsonify({'sounds': files})

# ── YouTube → audio stream URL
@app.route('/ytdl', methods=['POST'])
def ytdl():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    # Validate it's a YouTube URL
    if 'youtube.com' not in url and 'youtu.be' not in url:
        return jsonify({'error': 'Not a YouTube URL'}), 400

    try:
        # Get the best audio URL without downloading
        result = subprocess.run(
            ['yt-dlp',
             '--no-playlist',
             '--format', 'bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio',
             '--get-url',
             '--get-title',
             url],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            err = result.stderr.strip()
            return jsonify({'error': 'yt-dlp failed: ' + err}), 500

        lines = result.stdout.strip().splitlines()
        # yt-dlp --get-title --get-url outputs title then url
        if len(lines) >= 2:
            title = lines[0]
            audio_url = lines[1]
        elif len(lines) == 1:
            title = 'YouTube Audio'
            audio_url = lines[0]
        else:
            return jsonify({'error': 'No output from yt-dlp'}), 500

        return jsonify({'url': audio_url, 'title': title})

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timed out fetching YouTube info'}), 500
    except FileNotFoundError:
        return jsonify({'error': 'yt-dlp not installed on server'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Health check
@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
