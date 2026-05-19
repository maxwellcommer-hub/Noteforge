import os, subprocess, tempfile, json, glob, shutil
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR)
CORS(app)

COOKIES_FILE = '/tmp/yt_cookies.txt'

def write_cookies_file():
    """Write cookies from env var to file every time (handles restarts cleanly)."""
    cookies_env = os.environ.get('YOUTUBE_COOKIES', '').strip()
    if not cookies_env:
        return False
    # Replace literal \n or \t with real whitespace (env vars sometimes escape these)
    cookies_env = cookies_env.replace('\\t', '\t').replace('\\n', '\n')
    # Netscape cookie files use tabs as delimiters — make sure they're real tabs
    lines = []
    for line in cookies_env.splitlines():
        line = line.strip()
        if not line:
            continue
        lines.append(line)
    content = '\n'.join(lines) + '\n'
    with open(COOKIES_FILE, 'w') as f:
        f.write(content)
    return True

def get_cookies_args():
    if write_cookies_file():
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

# ── Debug endpoint — visit /debug in browser to check cookie status
@app.route('/debug')
def debug():
    cookies_env = os.environ.get('YOUTUBE_COOKIES', '')
    cookies_written = write_cookies_file()
    cookie_file_exists = os.path.exists(COOKIES_FILE)
    cookie_file_lines = 0
    cookie_file_preview = ''
    if cookie_file_exists:
        with open(COOKIES_FILE) as f:
            lines = f.readlines()
            cookie_file_lines = len(lines)
            # Show first line only (safe, just the header)
            cookie_file_preview = lines[0].strip() if lines else ''
    return jsonify({
        'YOUTUBE_COOKIES_env_length': len(cookies_env),
        'YOUTUBE_COOKIES_set': bool(cookies_env),
        'cookies_file_written': cookies_written,
        'cookies_file_exists': cookie_file_exists,
        'cookies_file_lines': cookie_file_lines,
        'cookies_file_first_line': cookie_file_preview,
        'sounds_dir_files': len(glob.glob(os.path.join(BASE_DIR, 'sounds', '*.ogg'))),
    })

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

        # Build download strategies — cookies first if available
        strategies = []
        if cookie_args:
            strategies.append(
                ['yt-dlp', '--no-playlist', '--no-warnings',
                 '-f', 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio',
                 '-o', out_template] + cookie_args + [url]
            )
        # iOS client (avoids bot check differently)
        strategies.append(
            ['yt-dlp', '--no-playlist', '--no-warnings',
             '--extractor-args', 'youtube:player_client=ios',
             '-f', 'bestaudio', '-o', out_template] + cookie_args + [url]
        )
        # tv_embedded client
        strategies.append(
            ['yt-dlp', '--no-playlist', '--no-warnings',
             '--extractor-args', 'youtube:player_client=tv_embedded',
             '-f', 'bestaudio', '-o', out_template] + cookie_args + [url]
        )

        last_err = ''
        success = False
        for cmd in strategies:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                success = True
                break
            last_err = result.stderr.strip()

        if not success:
            lines = [l for l in last_err.splitlines() if 'ERROR' in l]
            msg = lines[-1] if lines else last_err[-300:] if last_err else 'All strategies failed'
            if 'Sign in' in msg or 'bot' in msg.lower():
                has_cookies = bool(cookie_args)
                if has_cookies:
                    msg = 'Bot check failed even with cookies — your cookies may have expired. Re-export from browser and update the Railway YOUTUBE_COOKIES variable.'
                else:
                    msg = 'YouTube requires authentication. Add YOUTUBE_COOKIES to Railway environment variables.'
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
    return jsonify({'status': 'ok', 'youtube_cookies': bool(get_cookies_args())})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# ── Basic Pitch ML transcription endpoint
# Runs Spotify's Basic Pitch model server-side for accurate note detection
@app.route('/transcribe', methods=['POST'])
def transcribe():
    import tempfile, shutil
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    f = request.files['file']
    tmp_dir = tempfile.mkdtemp()
    mp3_path = os.path.join(tmp_dir, 'input.mp3')
    wav_path = os.path.join(tmp_dir, 'input.wav')

    try:
        f.save(mp3_path)

        # Convert to WAV for Basic Pitch
        subprocess.run(
            ['ffmpeg', '-i', mp3_path, '-ar', '22050', '-ac', '1', '-y', wav_path],
            capture_output=True, timeout=30
        )

        # Run Basic Pitch
        from basic_pitch.inference import predict
        from basic_pitch import ICASSP_2022_MODEL_PATH

        model_output, midi_data, note_events = predict(wav_path)

        # Convert note events to our format
        # note_events: list of (start_time, end_time, pitch_midi, amplitude, pitch_bends)
        notes = []
        for start, end, pitch, amp, _ in note_events:
            notes.append({
                'timeSec': float(start),
                'durSec': float(end - start),
                'midi': int(pitch),
                'vel': float(min(1.0, amp))
            })

        return jsonify({'notes': notes, 'count': len(notes)})

    except ImportError:
        return jsonify({'error': 'basic-pitch not installed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
