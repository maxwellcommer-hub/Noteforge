"""
Downloads official Minecraft note block sounds at Docker build time.
Searches the asset index dynamically so path changes between versions don't break it.
"""
import urllib.request, json, os, sys

os.makedirs('sounds', exist_ok=True)

SOUNDS_NEEDED = [
    "harp", "bass", "bell", "flute", "chime", "guitar",
    "xylophone", "iron_xylophone", "banjo", "bit", "pling",
    "didgeridoo", "cow_bell", "basedrum", "snare", "hat",
]

# Try multiple stable versions in order (newest first)
TRY_VERSIONS = ["1.21.4", "1.21.1", "1.20.4", "1.20.1", "1.19.4"]

def download():
    try:
        print("Fetching Minecraft version manifest...")
        with urllib.request.urlopen(
            "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json", timeout=15
        ) as r:
            manifest = json.loads(r.read())

        # Try each pinned version
        version_url = None
        chosen = None
        for vid in TRY_VERSIONS:
            for v in manifest['versions']:
                if v['id'] == vid:
                    version_url = v['url']
                    chosen = vid
                    break
            if version_url:
                break

        if not version_url:
            # Fall back to latest release
            latest_id = manifest['latest']['release']
            for v in manifest['versions']:
                if v['id'] == latest_id:
                    version_url = v['url']
                    chosen = latest_id
                    break

        print(f"Using Minecraft {chosen}")

        with urllib.request.urlopen(version_url, timeout=15) as r:
            version_data = json.loads(r.read())

        with urllib.request.urlopen(version_data['assetIndex']['url'], timeout=15) as r:
            assets = json.loads(r.read())

        objects = assets['objects']

        # Build a lookup: sound name (without .ogg) -> asset path
        # Search for anything with 'note' in the path
        note_paths = {k: v for k, v in objects.items() if 'note' in k.lower() and k.endswith('.ogg')}
        print(f"Found {len(note_paths)} note-related assets in index")

        downloaded = 0
        for name in SOUNDS_NEEDED:
            out_path = os.path.join('sounds', name + '.ogg')
            if os.path.exists(out_path):
                print(f"  Already exists: {name}.ogg")
                downloaded += 1
                continue

            # Find matching asset — search for exact name match in any subfolder
            match = None
            for asset_path in note_paths:
                # asset_path like "minecraft/sounds/block/note_block/harp.ogg"
                basename = asset_path.split('/')[-1].replace('.ogg', '')
                if basename == name:
                    match = (asset_path, note_paths[asset_path])
                    break

            if not match:
                # Try partial match (e.g. iron_xylophone might be stored differently)
                for asset_path in note_paths:
                    if name.replace('_', '') in asset_path.replace('_', '').lower():
                        match = (asset_path, note_paths[asset_path])
                        break

            if not match:
                print(f"  NOT FOUND: {name}.ogg — paths searched: {[p for p in note_paths if name[:4] in p]}")
                continue

            asset_path, obj = match
            h = obj['hash']
            url = f"https://resources.download.minecraft.net/{h[:2]}/{h}"
            try:
                print(f"  Downloading {name}.ogg (from {asset_path})...")
                urllib.request.urlretrieve(url, out_path)
                downloaded += 1
            except Exception as e:
                print(f"  Failed {name}: {e}")

        print(f"\nDownloaded {downloaded}/{len(SOUNDS_NEEDED)} sounds")
        if downloaded == 0:
            # Print all found note paths for debugging
            print("\nAll note paths found in index:")
            for p in sorted(note_paths.keys()):
                print(f"  {p}")
        return downloaded > 0

    except Exception as e:
        print(f"Sound download failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    ok = download()
    sys.exit(0 if ok else 1)
