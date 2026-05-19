FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install bgutil pot provider AND build its Node.js script
# This is what actually generates PO tokens per-video on the server
RUN pip install --no-cache-dir bgutil-ytdlp-pot-provider && \
    python3 -c "import bgutil_ytdlp_pot_provider; import os; \
    script_dir = os.path.dirname(bgutil_ytdlp_pot_provider.__file__); \
    server_dir = os.path.join(script_dir, 'server'); \
    print('bgutil dir:', script_dir); \
    print('server dir exists:', os.path.exists(server_dir))" || true

# Build the bgutil server script with npm
RUN python3 -c "\
import subprocess, os, glob; \
dirs = glob.glob('/usr/local/lib/python3.11/site-packages/bgutil_ytdlp_pot_provider*'); \
print('Found dirs:', dirs); \
for d in dirs: \
    server = os.path.join(d, 'server'); \
    if os.path.exists(server): \
        print('Building in', server); \
        r = subprocess.run(['npm', 'install'], cwd=server, capture_output=True, text=True); \
        print(r.stdout[-500:]); print(r.stderr[-200:]); \
        r2 = subprocess.run(['npm', 'run', 'build'], cwd=server, capture_output=True, text=True); \
        print(r2.stdout[-500:]); print(r2.stderr[-200:]); \
" || echo "bgutil build attempted"

COPY . .
RUN mkdir -p sounds

# Cache bust: 2026-05-19-v4
ARG CACHEBUST=2026-05-19-v4
RUN python3 download_sounds.py || echo "Sound download failed - synthesis fallback active"

EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--worker-class", "gevent", "--workers", "2", "--worker-connections", "10", "--timeout", "300", "server:app"]
