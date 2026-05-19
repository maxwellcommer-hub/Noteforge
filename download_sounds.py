# cache-bust: 2026-05-19-v3
"""
Downloads official Minecraft Java Edition note block sounds from Mojang's servers.
Uses 1.20.1 asset index which has stable, known-good paths for all note block sounds.
"""
import urllib.request, json, os, sys

os.makedirs('sounds', exist_ok=True)

# All 16 note block instruments we need
SOUNDS = [
    "harp", "bass", "bell", "flute", "chime", "guitar",
    "xylophone", "iron_xylophone", "cow_bell", "didgeridoo",
    "bit", "banjo", "pling", "basedrum", "snare", "hat",
]

# Try these versions — 1.20.1 has the most stable note block sound paths
TRY_VERSIONS = ["1.20.1", "1.19.4", "1.18.2", "1.17.1"]

def try_download(name, objects):
    """Try all known path formats for a sound name."""
    out = os.path.join('sounds', name + '.ogg')
    
    # All possible path formats across MC versions
    paths_to_try = [
        f"minecraft/sounds/block/note_block/{name}.ogg",  # 1.14+
        f"minecraft/sounds/block/note/{name}.ogg",         # 1.9-1.13
        f"minecraft/sounds/note/{name}.ogg",               # pre-1.9
    ]
    # Special case mappings
    alt_names = {
        "xylophone":       ["xylobone"],
        "iron_xylophone":  ["iron_xylophone", "xylobone"],
        "basedrum":        ["bd", "basedrum"],
        "chime":           ["icechime", "chime"],  # stored as icechime in older versions
    }
    if name in alt_names:
        for alt in alt_names[name]:
            for prefix in ["minecraft/sounds/block/note_block/", "minecraft/sounds/block/note/", "minecraft/sounds/note/"]:
                paths_to_try.append(prefix + alt + ".ogg")

    for path in paths_to_try:
        if path in objects:
            h = objects[path]['hash']
            url = f"https://resources.download.minecraft.net/{h[:2]}/{h}"
            try:
                urllib.request.urlretrieve(url, out)
                with open(out, 'rb') as f:
                    if f.read(4) == b'OggS':
                        size = os.path.getsize(out)
                        print(f"  OK {name}.ogg ({size}b) from {path}")
                        return True
                    else:
                        os.remove(out)
                        print(f"  Bad OGG data for {name} from {path}")
            except Exception as e:
                print(f"  Download error {name} from {path}: {e}")
                if os.path.exists(out): os.remove(out)

    # Also try searching — find any path ending in /{name}.ogg with 'note' in path
    for key, val in objects.items():
        basename = key.split('/')[-1].replace('.ogg','')
        if basename == name and 'note' in key.lower():
            h = val['hash']
            url = f"https://resources.download.minecraft.net/{h[:2]}/{h}"
            try:
                urllib.request.urlretrieve(url, out)
                with open(out, 'rb') as f:
                    if f.read(4) == b'OggS':
                        print(f"  OK {name}.ogg (found via search at {key})")
                        return True
                    else:
                        os.remove(out)
            except Exception as e:
                if os.path.exists(out): os.remove(out)

    return False

def download():
    print(f"Downloading {len(SOUNDS)} Minecraft note block sounds...")
    
    try:
        with urllib.request.urlopen(
            "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json", timeout=15
        ) as r:
            manifest = json.loads(r.read())
    except Exception as e:
        print(f"Failed to fetch manifest: {e}")
        return False

    for vid in TRY_VERSIONS:
        ventry = next((v for v in manifest['versions'] if v['id'] == vid), None)
        if not ventry:
            print(f"Version {vid} not in manifest, skipping")
            continue

        try:
            print(f"\nTrying Minecraft {vid}...")
            with urllib.request.urlopen(ventry['url'], timeout=10) as r:
                vdata = json.loads(r.read())
            with urllib.request.urlopen(vdata['assetIndex']['url'], timeout=10) as r:
                assets = json.loads(r.read())
            objects = assets['objects']
            
            # Show all note-related paths found
            note_paths = [k for k in objects if 'note' in k.lower() and k.endswith('.ogg')]
            print(f"  Found {len(note_paths)} note-related paths:")
            for p in sorted(note_paths)[:30]:
                print(f"    {p}")

            downloaded = 0
            for name in SOUNDS:
                out = os.path.join('sounds', name + '.ogg')
                if os.path.exists(out):
                    print(f"  EXISTS {name}.ogg")
                    downloaded += 1
                    continue
                if try_download(name, objects):
                    downloaded += 1
                else:
                    print(f"  MISSING {name}.ogg")

            print(f"\nDownloaded {downloaded}/{len(SOUNDS)} sounds from {vid}")
            if downloaded >= 10:  # Good enough
                return True
            # Not enough — try next version
        except Exception as e:
            print(f"  Error with {vid}: {e}")
            import traceback; traceback.print_exc()
            continue

    total = sum(1 for s in SOUNDS if os.path.exists(os.path.join('sounds', s+'.ogg')))
    print(f"\nFinal: {total}/{len(SOUNDS)} sounds available")
    return total > 0

if __name__ == '__main__':
    ok = download()
    sys.exit(0 if ok else 1)
