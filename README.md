# NoteForge 🎵⛏

MP3 / YouTube → Minecraft Note Blocks converter. Hosted as a web app so it works on any phone with no limitations.

## Deploy in 10 Steps (Free, No Coding)

### Step 1 — Create a GitHub account
Go to **github.com** → Sign Up → confirm your email.

### Step 2 — Create a new repository
1. Click the **+** icon top right → "New repository"
2. Name it `noteforge`
3. Set it to **Public**
4. Click **Create repository**

### Step 3 — Upload the files
1. On your new repo page, click **"uploading an existing file"**
2. Drag ALL these files into the upload box:
   - `server.py`
   - `requirements.txt`
   - `Dockerfile`
   - `download_sounds.py`
   - The `static/` folder (drag the whole folder)
3. Click **Commit changes**

### Step 4 — Create a Railway account
Go to **railway.app** → "Start a New Project" → sign in with GitHub (this links them automatically).

### Step 5 — Deploy
1. Click **"Deploy from GitHub repo"**
2. Select your `noteforge` repository
3. Railway auto-detects the Dockerfile and starts building

### Step 6 — Wait for build (~3-5 minutes)
Railway will:
- Install Python + ffmpeg
- Install yt-dlp
- Download all 16 official Minecraft note block sounds from Mojang's servers
- Start the web server

### Step 7 — Get your URL
In the Railway dashboard, click your project → **Settings** → **Networking** → **Generate Domain**.
You'll get a URL like `noteforge-production.up.railway.app`.

### Step 8 — Open on your phone
Go to that URL in Safari or Chrome on your phone. It works like a website — you can add it to your home screen too (Share → Add to Home Screen).

### Step 9 — Updating
Any time you want to update, just re-upload files to GitHub. Railway redeploys automatically.

---

## What the Server Does

| Feature | How |
|---|---|
| YouTube audio | yt-dlp extracts audio stream server-side |
| Minecraft sounds | Downloaded from Mojang at build time, served to browser |
| MP3 processing | All pitch detection runs in your browser (Web Audio API) |
| BPM detection | Multi-resolution onset autocorrelation |

## Free Tier Limits (Railway)
- 500 hours/month free (enough for ~16 hours/day)
- Sleeps after 30min inactivity, wakes in ~5 seconds on next visit
- $5/month to keep it always-on if you want

## Local Development
```bash
pip install -r requirements.txt
python download_sounds.py
python server.py
# Open http://localhost:8080
```
