"""Overlay detection results on the rendered PDF page (for checking the detector by eye)."""
import subprocess, tempfile, os
from PIL import Image, ImageDraw


def page_image(pdf, page=1, dpi=150):
    d = tempfile.mkdtemp()
    subprocess.run(["pdftocairo", "-png", "-r", str(dpi), "-f", str(page), "-l", str(page), "-singlefile",
                    pdf, os.path.join(d, "p")], check=True)
    return Image.open(os.path.join(d, "p.png")).convert("RGB")


def draw(pdf, layers, out, page=1, dpi=150, crop=None):
    """layers: list of (kind, items, color) with kind 'rect' (x0,x1,y0,y1) | 'line' (x0,y0,x1,y1) | 'text' (x,y,s)
    in page points."""
    im = page_image(pdf, page, dpi)
    im = Image.blend(im, Image.new("RGB", im.size, "white"), 0.55)
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    g = ImageDraw.Draw(ov)
    k = dpi / 72
    for kind, items, col in layers:
        for it in items:
            if kind == "rect":
                x0, x1, y0, y1 = it[:4]
                g.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], fill=col)
            elif kind == "line":
                g.line([it[0] * k, it[1] * k, it[2] * k, it[3] * k], fill=col, width=2)
            elif kind == "text":
                g.text((it[0] * k, it[1] * k), it[2], fill=col)
            elif kind == "circle":
                cx, cy, r = it[:3]
                g.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k], outline=col, width=2)
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    if crop:
        im = im.crop([v * k for v in crop])
    im.save(out)
