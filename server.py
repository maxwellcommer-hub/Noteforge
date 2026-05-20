import os, glob, shutil, subprocess, tempfile, json, threading
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOUNDS_DIR = os.path.join(BASE_DIR, 'sounds')
app = Flask(__name__, static_folder=BASE_DIR)
CORS(app)

# ── Download sounds at startup in background thread
def ensure_sounds():
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    oggs = [f for f in os.listdir(SOUNDS_DIR) if f.endswith('.ogg')]
    mp3s = [f for f in os.listdir(SOUNDS_DIR) if f.endswith('.mp3')]
    
    # Download OGGs if missing
    if len(oggs) < 15:
        print(f"[sounds] Only {len(oggs)} OGGs found, downloading...")
        try:
            script = os.path.join(BASE_DIR, 'download_sounds.py')
            result = subprocess.run(['python3', script], capture_output=True, text=True, timeout=120)
            print(result.stdout[-2000:])
            oggs = [f for f in os.listdir(SOUNDS_DIR) if f.endswith('.ogg')]
            print(f"[sounds] Download complete: {len(oggs)} OGGs ready")
        except Exception as e:
            print(f"[sounds] Download error: {e}")
    else:
        print(f"[sounds] {len(oggs)} OGGs already present")
    
    # Convert OGGs to MP3 for Safari/iOS support
    if len(mp3s) < len(oggs):
        print(f"[sounds] Converting OGGs to MP3 for Safari support...")
        for ogg_file in os.listdir(SOUNDS_DIR):
            if not ogg_file.endswith('.ogg'):
                continue
            mp3_file = ogg_file.replace('.ogg', '.mp3')
            mp3_path = os.path.join(SOUNDS_DIR, mp3_file)
            ogg_path = os.path.join(SOUNDS_DIR, ogg_file)
            if os.path.exists(mp3_path):
                continue
            try:
                subprocess.run([
                    'ffmpeg', '-i', ogg_path, '-codec:a', 'libmp3lame',
                    '-q:a', '2', '-y', mp3_path
                ], capture_output=True, timeout=30)
                if os.path.exists(mp3_path):
                    print(f"  ✓ {mp3_file}")
            except Exception as e:
                print(f"  ✗ {mp3_file}: {e}")
        mp3s = [f for f in os.listdir(SOUNDS_DIR) if f.endswith('.mp3')]
        print(f"[sounds] {len(mp3s)} MP3s ready")
    else:
        print(f"[sounds] {len(mp3s)} MP3s already present")

# Run in background so server starts immediately
threading.Thread(target=ensure_sounds, daemon=True).start()

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
    return send_from_directory(SOUNDS_DIR, filename)

@app.route('/sounds-list')
def sounds_list():
    files = []
    if os.path.exists(SOUNDS_DIR):
        files = [os.path.basename(f) for f in glob.glob(os.path.join(SOUNDS_DIR, '*.ogg'))]
    return jsonify({'sounds': files})

@app.route('/debug')
def debug():
    sounds = glob.glob(os.path.join(SOUNDS_DIR, '*.ogg'))
    return jsonify({
        'sounds_count': len(sounds),
        'sounds': sorted([os.path.basename(s) for s in sounds]),
        'sounds_dir': SOUNDS_DIR,
        'cookies_set': bool(os.environ.get('YOUTUBE_COOKIES')),
    })

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
