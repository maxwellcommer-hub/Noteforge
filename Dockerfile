FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p sounds

# Cache bust: change to force re-download
ARG CACHEBUST=2026-05-20-v3
RUN echo "Downloading sounds (bust: $CACHEBUST)" && python3 download_sounds.py || echo "Sound download failed"

EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--worker-class", "gevent", "--workers", "2", "--worker-connections", "10", "--timeout", "300", "server:app"]
