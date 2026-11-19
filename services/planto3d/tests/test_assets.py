"""Every downloaded asset is in assets/manifest.json with a licence that allows redistribution, and every asset the
code asks for comes from an allowed source.  python3 tests/test_assets.py   (skips when the assets are not downloaded)"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import fetch_assets as fa  # noqa: E402

assert all(src["licence"] in fa.ALLOWED_LICENCES for src in fa.SOURCES.values()), fa.SOURCES
if not os.path.exists(fa.MANIFEST):
    print("skip assets: no assets/manifest.json (run python3 fetch_assets.py)")
    sys.exit(0)
man = json.load(open(fa.MANIFEST))
bad = {k: v for k, v in man.items() if v.get("licence") not in fa.ALLOWED_LICENCES or v.get("source") not in fa.SOURCES}
assert not bad, f"assets without an allowed licence: {bad}"
on_disk = set(os.listdir(os.path.join(fa.ROOT, "models"))) | set(os.listdir(os.path.join(fa.ROOT, "textures")))
unlisted = sorted(n for n in on_disk if not n.startswith(".") and n not in man)
assert not unlisted, f"assets on disk that the manifest does not list: {unlisted}"
print(f"ok   assets: {len(man)} listed, all {', '.join(sorted({v['licence'] for v in man.values()}))}")
