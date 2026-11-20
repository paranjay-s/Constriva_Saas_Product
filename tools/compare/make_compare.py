"""PART 2 F: one sheet per room type: your reference picture, our Low walkthrough and our High still, side by side.

    python3 tools/compare/make_compare.py PAIRS.json OUT_DIR

PAIRS.json: [{"type": "Living room", "reference": "path or null", "low": "path or null", "high": "path or null",
              "note": "..."}]. HEIC references are converted with macOS `sips`. Each sheet is OUT_DIR/<type>.jpg
(1920 px wide, three panels with titles); OUT_DIR/index.md lists them. Reference pictures are the owner's own
material: the sheets stay on disk (docs/pro/**/*.jpg is git-ignored); the index is committed.
"""

import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

W, PANEL_H, HEAD = 1920, 400, 44
FONT = None
for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
    if os.path.exists(f):
        FONT = ImageFont.truetype(f, 22)
        break
FONT = FONT or ImageFont.load_default()


def open_any(path):
    if not path or not os.path.exists(path):
        return None
    if path.lower().endswith(".heic"):
        tmp = tempfile.mktemp(suffix=".jpg")
        subprocess.run(["sips", "-s", "format", "jpeg", path, "--out", tmp], capture_output=True, check=True)
        path = tmp
    return Image.open(path).convert("RGB")


def fit(im, w, h):
    canvas = Image.new("RGB", (w, h), (24, 26, 30))
    if im is None:
        ImageDraw.Draw(canvas).text((20, h // 2 - 12), "not available", fill=(150, 150, 150), font=FONT)
        return canvas
    im = im.copy()
    im.thumbnail((w, h))
    canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return canvas


def main():
    pairs, out = json.load(open(sys.argv[1])), sys.argv[2]
    os.makedirs(out, exist_ok=True)
    pw = W // 3
    lines = ["# Reference vs Low vs High, per room type (PART 2, F)", "",
             "Left: your reference picture (docs/reference/rooms). Middle: our Low walkthrough (three.js, baked light).",
             "Right: our High still (Cycles, the style handover's look). Sheets are on disk only (they contain your",
             "reference pictures). For design purposes only, not for construction.", "",
             "| Room type | Sheet | Notes |", "|---|---|---|"]
    for p in pairs:
        sheet = Image.new("RGB", (W, PANEL_H + HEAD + 36), (14, 16, 20))
        d = ImageDraw.Draw(sheet)
        d.text((16, 10), p["type"], fill=(240, 240, 240), font=FONT)
        for k, (label, key) in enumerate((("Reference", "reference"), ("Low (walkthrough)", "low"),
                                          ("High (still)", "high"))):
            sheet.paste(fit(open_any(p.get(key)), pw - 8, PANEL_H), (k * pw + 4, HEAD))
            d.text((k * pw + 12, HEAD + PANEL_H + 6), label, fill=(190, 200, 210), font=FONT)
        name = "".join(c if c.isalnum() else "_" for c in p["type"].lower()).strip("_") + ".jpg"
        sheet.save(os.path.join(out, name), quality=88)
        lines.append(f"| {p['type']} | `{name}` | {p.get('note', '')} |")
    open(os.path.join(out, "index.md"), "w").write("\n".join(lines) + "\n")
    print(len(pairs), "sheets")


if __name__ == "__main__":
    main()
