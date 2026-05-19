FROM python:3.11-slim

# System deps + ffmpeg + Node.js (Node needed for YouTube PO token generation)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# bgutil yt-dlp PO token provider — fixes "Sign in to confirm you're not a bot"
# on server/datacenter IPs by generating YouTube's required proof-of-origin tokens
RUN pip install --no-cache-dir bgutil-ytdlp-pot-provider

# App files
COPY . .
RUN mkdir -p sounds

# Download official Minecraft note block sounds at build time
RUN python3 download_sounds.py || echo "Sound download skipped - synthesis fallback active"

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "server:app"]
