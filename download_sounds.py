# cache-bust: 2026-05-20-v3
"""
Downloads official Minecraft Java Edition note block sounds.
Uses 1.20.1 asset index - gets 15/16 sounds reliably.
"""
import urllib.request, json, os, sys

os.makedirs('sounds', exist_ok=True)

SOUNDS = [
    "harp","bass","bell","flute","chime","guitar",
    "xylophone","iron_xylophone","cow_bell","didgeridoo",
    "bit","banjo","pling","basedrum","snare","hat",
]

# In 1.20.1 these sounds have different filenames in the asset index
ALT_NAMES = {
    "chime":     ["icechime", "chime"],
    "xylophone": ["xylobone", "xylophone"],
    "basedrum":  ["bd", "basedrum"],
}

TRY_VERSIONS = ["1.20.1", "1.19.4", "1.18.2"]

def verify_ogg(path):
    try:
        with open(path,'rb') as f: return f.read(4)==b'OggS'
    except: return False

def download():
    print("Fetching version manifest...")
    with urllib.request.urlopen(
        "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json", timeout=15
    ) as r:
        manifest = json.loads(r.read())

    objects = None
    chosen = None
    for vid in TRY_VERSIONS:
        ventry = next((v for v in manifest['versions'] if v['id'] == vid), None)
        if not ventry:
            continue
        try:
            print(f"Trying {vid}...")
            with urllib.request.urlopen(ventry['url'], timeout=10) as r:
                vdata = json.loads(r.read())
            with urllib.request.urlopen(vdata['assetIndex']['url'], timeout=10) as r:
                assets = json.loads(r.read())
            objects = assets['objects']
            chosen = vid
            print(f"Using {chosen}")
            break
        except Exception as e:
            print(f"  {vid} failed: {e}")

    if not objects:
        print("Could not fetch any asset index"); sys.exit(1)

    # Build basename lookup
    note_lookup = {}
    for path, val in objects.items():
        if 'note' in path.lower() and path.endswith('.ogg'):
            basename = path.split('/')[-1].replace('.ogg','')
            note_lookup[basename] = val['hash']

    print(f"Found {len(note_lookup)} note sounds: {sorted(note_lookup.keys())}")

    downloaded = 0
    for name in SOUNDS:
        out = os.path.join('sounds', name + '.ogg')
        if os.path.exists(out) and verify_ogg(out):
            print(f"  EXISTS {name}.ogg"); downloaded += 1; continue

        alts = ALT_NAMES.get(name, [name])
        found = False
        for alt in alts:
            if alt in note_lookup:
                h = note_lookup[alt]
                url = f"https://resources.download.minecraft.net/{h[:2]}/{h}"
                try:
                    urllib.request.urlretrieve(url, out)
                    if verify_ogg(out):
                        print(f"  OK {name}.ogg ({os.path.getsize(out)}b) from '{alt}'")
                        downloaded += 1; found = True; break
                    else:
                        os.remove(out)
                except Exception as e:
                    print(f"  FAIL {name} via '{alt}': {e}")
                    if os.path.exists(out): os.remove(out)

        if not found:
            print(f"  MISSING {name}.ogg")

    print(f"\nDownloaded {downloaded}/{len(SOUNDS)} sounds")
    return downloaded > 0

if __name__ == '__main__':
    ok = download()
    sys.exit(0 if ok else 1)
