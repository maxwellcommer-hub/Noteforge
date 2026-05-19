FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir bgutil-ytdlp-pot-provider gevent

COPY . .
RUN mkdir -p sounds
RUN python3 download_sounds.py || echo "Sound download skipped - synthesis fallback active"

EXPOSE 8080
# Use gevent async workers — no timeout on long yt-dlp downloads
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--worker-class", "gevent", "--workers", "2", "--worker-connections", "10", "--timeout", "300", "server:app"]
