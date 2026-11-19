"""Merge every piece's entry.json into ../index.json, the library index that works before the asset_library table
exists.  python3 index.py"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

entries = sorted((json.load(open(p)) for p in glob.glob(os.path.join(ROOT, "*", "*", "entry.json"))),
                 key=lambda e: (e["kind"], e["id"]))
with open(os.path.join(ROOT, "index.json"), "w") as fh:
    json.dump(dict(version=1, entries=entries), fh, indent=1)
print(f"index: {len(entries)} entries")
