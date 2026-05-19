FROM python:3.11-slim

# Install system deps + ffmpeg (needed by yt-dlp for audio conversion)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Make sure sounds and static dirs exist
RUN mkdir -p sounds static

# Download Minecraft note block sounds at build time
# These are from the official Minecraft Java assets (publicly mirrored)
RUN python3 download_sounds.py || echo "Sound download skipped - will use synthesis fallback"

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "60", "server:app"]
