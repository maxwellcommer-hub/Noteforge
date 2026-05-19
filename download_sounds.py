"""
Downloads official Minecraft Java Edition note block sounds.
Runs once during Docker build.
"""
import urllib.request, json, os, sys

os.makedirs('sounds', exist_ok=True)

SOUNDS_NEEDED = [
    "harp", "bass", "bell", "flute", "chime", "guitar",
    "xylophone", "iron_xylophone", "banjo", "bit", "pling",
    "didgeridoo", "cow_bell", "basedrum", "snare", "hat",
]

# Try both old path (note/) and new path (note_block/) across multiple versions
SEARCH_PATHS = [
    "minecraft/sounds/block/note_block/{name}.ogg",  # 1.13+
    "minecraft/sounds/block/note/{name}.ogg",         # pre-1.13
]

# Pin to a known stable release instead of latest (which may be a snapshot)
PINNED_VERSION = "1.21.4"

def download():
    try:
        print("Fetching Minecraft version manifest...")
        with urllib.request.urlopen(
            "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json", timeout=15
        ) as r:
            manifest = json.loads(r.read())

        # Try pinned version first, fall back to latest release
        version_url = None
        for v in manifest['versions']:
            if v['id'] == PINNED_VERSION:
                version_url = v['url']
                print(f"Using Minecraft {PINNED_VERSION}")
                break

        if not version_url:
            latest_id = manifest['latest']['release']
            for v in manifest['versions']:
                if v['id'] == latest_id:
                    version_url = v['url']
                    print(f"Pinned version not found, using latest release: {latest_id}")
                    break

        if not version_url:
            print("Could not find a valid release version")
            return False

        with urllib.request.urlopen(version_url, timeout=15) as r:
            version_data = json.loads(r.read())

        with urllib.request.urlopen(version_data['assetIndex']['url'], timeout=15) as r:
            assets = json.loads(r.read())

        objects = assets['objects']
        downloaded = 0

        for name in SOUNDS_NEEDED:
            out_path = os.path.join('sounds', name + '.ogg')
            if os.path.exists(out_path):
                print(f"  Already exists: {name}.ogg")
                downloaded += 1
                continue

            # Try both path formats
            found = False
            for path_template in SEARCH_PATHS:
                sound_path = path_template.format(name=name)
                if sound_path in objects:
                    obj = objects[sound_path]
                    h = obj['hash']
                    url = f"https://resources.download.minecraft.net/{h[:2]}/{h}"
                    try:
                        print(f"  Downloading {name}.ogg from {sound_path}...")
                        urllib.request.urlretrieve(url, out_path)
                        downloaded += 1
                        found = True
                        break
                    except Exception as e:
                        print(f"  Failed {name}: {e}")

            if not found:
                print(f"  NOT FOUND in assets: {name}.ogg (tried both path formats)")

        print(f"\nDownloaded {downloaded}/{len(SOUNDS_NEEDED)} sounds")
        return downloaded > 0

    except Exception as e:
        print(f"Sound download failed: {e}")
        return False

if __name__ == '__main__':
    ok = download()
    sys.exit(0 if ok else 1)
