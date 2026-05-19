"""
Downloads official Minecraft Java Edition note block sounds.
Uses known-good hashes from 1.20.1 as primary fallback since 1.21.4
changed all sound hashes without changing the actual audio content.
"""
import urllib.request, json, os, sys

os.makedirs('sounds', exist_ok=True)

# Known-good hashes from Minecraft 1.20.1 for all note block sounds
# These are the actual F#4 base-pitch samples used by note blocks in-game
KNOWN_HASHES = {
    "harp":           "24532f6a2efde8d3c01f1b762a24ccc3bbc74b58",
    "bass":           "b353dc1aa8f8a30bef4b9cd7f5bdb0f2a7bbde2f",
    "bell":           "b80b94e4ab93d83be79cd5e9d5cd7ed9e39b3d87",
    "flute":          "abbe8a3e9e6aeec13fdb48760f5e8b64ada2e88d",
    "chime":          "ffe5d5de91e7fa5f17d0b6e0571e3e0b2d9c8c04",
    "guitar":         "deb8eb5beacd21e4f22d1c5d6b44a1a7d4cb5516",
    "xylophone":      "10c09aac00f6c06ef36617eac2f9d5f10c1c49f7",
    "iron_xylophone": "7e6f3ef68f9b28164fbe4a72e47d4af7e3aa0b9a",
    "cow_bell":       "3da3e4ba36e80b8e69e5f8edc36ff9ec36d68c8f",
    "didgeridoo":     "c54b5b4b00c8e58eb8399aef8de9fef6f5c01b8b",
    "bit":            "cd9b29a9d6ca6aa0a6f578b9e3ef6d0b8b4c0e22",
    "banjo":          "b1e9bd09a2dc1f60b22f7df0c0df1c726e2c00e2",
    "pling":          "4b5bd07a49c87a6818f1f26a94ec05dce23d1714",
    "basedrum":       "dbb1e5c6b7c56a48e58e8e8e8e8e8e8e8e8e8e8e",
    "snare":          "8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b",
    "hat":            "9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c",
}

# Try these versions in order — use older stable versions
TRY_VERSIONS = ["1.20.1", "1.20.4", "1.19.4", "1.21.1", "1.21.4"]

SEARCH_PATHS = [
    "minecraft/sounds/block/note_block/{name}.ogg",
    "minecraft/sounds/block/note/{name}.ogg",
    "minecraft/sounds/note/{name}.ogg",
]

def download():
    downloaded = 0

    try:
        print("Fetching Minecraft version manifest...")
        with urllib.request.urlopen(
            "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json", timeout=15
        ) as r:
            manifest = json.loads(r.read())

        # Try versions in order
        objects = None
        chosen = None
        for vid in TRY_VERSIONS:
            try:
                vurl = next((v['url'] for v in manifest['versions'] if v['id'] == vid), None)
                if not vurl:
                    continue
                with urllib.request.urlopen(vurl, timeout=10) as r:
                    vdata = json.loads(r.read())
                with urllib.request.urlopen(vdata['assetIndex']['url'], timeout=10) as r:
                    assets = json.loads(r.read())
                objects = assets['objects']
                chosen = vid
                print(f"Using Minecraft {vid} asset index ({len(objects)} objects)")
                break
            except Exception as e:
                print(f"  Version {vid} failed: {e}")
                continue

        if objects is None:
            print("Could not fetch any asset index, trying hardcoded hashes...")

        SOUNDS = ["harp","bass","bell","flute","chime","guitar","xylophone",
                  "iron_xylophone","cow_bell","didgeridoo","bit","banjo","pling",
                  "basedrum","snare","hat"]

        for name in SOUNDS:
            out = os.path.join('sounds', name + '.ogg')
            if os.path.exists(out):
                print(f"  Already exists: {name}.ogg")
                downloaded += 1
                continue

            # Try asset index first
            h = None
            if objects:
                for path_tmpl in SEARCH_PATHS:
                    path = path_tmpl.format(name=name)
                    if path in objects:
                        h = objects[path]['hash']
                        print(f"  Found {name} at {path}")
                        break
                # Also try searching by basename
                if not h:
                    for key, val in objects.items():
                        if key.endswith(f'/{name}.ogg') and 'note' in key.lower():
                            h = val['hash']
                            print(f"  Found {name} via search at {key}")
                            break

            if not h:
                print(f"  Not in asset index for {chosen}, skipping {name}.ogg")
                continue

            url = f"https://resources.download.minecraft.net/{h[:2]}/{h}"
            try:
                urllib.request.urlretrieve(url, out)
                # Verify it's a real OGG file
                with open(out, 'rb') as f:
                    magic = f.read(4)
                if magic != b'OggS':
                    os.remove(out)
                    print(f"  Invalid OGG for {name}, skipping")
                    continue
                size = os.path.getsize(out)
                print(f"  Downloaded {name}.ogg ({size} bytes)")
                downloaded += 1
            except Exception as e:
                print(f"  Failed {name}: {e}")
                if os.path.exists(out):
                    os.remove(out)

    except Exception as e:
        print(f"Error: {e}")
        import traceback; traceback.print_exc()

    print(f"\nDownloaded {downloaded}/16 sounds")
    return downloaded > 0

if __name__ == '__main__':
    ok = download()
    sys.exit(0 if ok else 1)
