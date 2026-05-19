"""
Downloads official Minecraft Java Edition note block sounds.
Runs once during Docker build. Uses the Minecraft asset CDN.
"""
import urllib.request, json, os, sys

os.makedirs('sounds', exist_ok=True)

# Minecraft 1.20.4 asset index
ASSET_INDEX_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

SOUNDS_NEEDED = [
    "minecraft/sounds/block/note_block/harp.ogg",
    "minecraft/sounds/block/note_block/bass.ogg",
    "minecraft/sounds/block/note_block/bell.ogg",
    "minecraft/sounds/block/note_block/flute.ogg",
    "minecraft/sounds/block/note_block/chime.ogg",
    "minecraft/sounds/block/note_block/guitar.ogg",
    "minecraft/sounds/block/note_block/xylophone.ogg",
    "minecraft/sounds/block/note_block/iron_xylophone.ogg",
    "minecraft/sounds/block/note_block/banjo.ogg",
    "minecraft/sounds/block/note_block/bit.ogg",
    "minecraft/sounds/block/note_block/pling.ogg",
    "minecraft/sounds/block/note_block/didgeridoo.ogg",
    "minecraft/sounds/block/note_block/cow_bell.ogg",
    "minecraft/sounds/block/note_block/basedrum.ogg",
    "minecraft/sounds/block/note_block/snare.ogg",
    "minecraft/sounds/block/note_block/hat.ogg",
]

def download():
    try:
        print("Fetching Minecraft version manifest...")
        with urllib.request.urlopen(ASSET_INDEX_URL, timeout=15) as r:
            manifest = json.loads(r.read())

        # Get latest release
        latest_id = manifest['latest']['release']
        version_url = next(v['url'] for v in manifest['versions'] if v['id'] == latest_id)
        print(f"Using Minecraft {latest_id}")

        with urllib.request.urlopen(version_url, timeout=15) as r:
            version_data = json.loads(r.read())

        asset_index_url = version_data['assetIndex']['url']
        with urllib.request.urlopen(asset_index_url, timeout=15) as r:
            assets = json.loads(r.read())

        objects = assets['objects']
        downloaded = 0

        for sound_path in SOUNDS_NEEDED:
            name = os.path.basename(sound_path)  # e.g. harp.ogg
            out_path = os.path.join('sounds', name)

            if os.path.exists(out_path):
                print(f"  Already exists: {name}")
                downloaded += 1
                continue

            if sound_path not in objects:
                # Try alternate path format (older versions)
                alt = sound_path.replace('note_block', 'note')
                if alt in objects:
                    sound_path = alt
                else:
                    print(f"  Not found in assets: {name}")
                    continue

            obj = objects[sound_path]
            h = obj['hash']
            url = f"https://resources.download.minecraft.net/{h[:2]}/{h}"

            try:
                print(f"  Downloading {name}...")
                urllib.request.urlretrieve(url, out_path)
                downloaded += 1
            except Exception as e:
                print(f"  Failed {name}: {e}")

        print(f"\nDownloaded {downloaded}/{len(SOUNDS_NEEDED)} sounds")
        return downloaded > 0

    except Exception as e:
        print(f"Sound download failed: {e}")
        return False

if __name__ == '__main__':
    ok = download()
    sys.exit(0 if ok else 1)
