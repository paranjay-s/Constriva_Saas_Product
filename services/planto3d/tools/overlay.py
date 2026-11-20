"""Shared by tools/fast_tour.py and tools/tour_join.py (PATCHES 57): image loading in Blender's Python, titles
rendered by Blender's own text (the ffmpeg here has no text filter), the minimap with the current room lit, and
alpha compositing in NumPy."""

import os

import bpy
import numpy as np

def load(path, size=None):
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    a = np.empty(w * h * img.channels, np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(h, w, img.channels)[::-1]                 # Blender's rows run bottom-up
    bpy.data.images.remove(img)
    if a.shape[2] == 3:
        a = np.concatenate([a, np.ones((h, w, 1), np.float32)], 2)
    if size and (w, h) != size:
        ys = (np.arange(size[1]) * h / size[1]).astype(int)
        xs = (np.arange(size[0]) * w / size[0]).astype(int)
        a = a[ys][:, xs]
    return a


# ------------------------------------------------------------------ titles, rendered by Blender's text
def title_images(texts, tmp_dir):
    sc = bpy.context.scene
    for o in list(bpy.data.objects):           # the default scene's cube, light and camera
        bpy.data.objects.remove(o)
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "FLAT"
    sc.display.shading.color_type = "SINGLE"
    sc.display.shading.single_color = (1, 1, 1)
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x, sc.render.resolution_y = 1400, 120
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    cam = bpy.data.objects.new("tcam", bpy.data.cameras.new("tcam"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 14.0
    cam.location = (7.0, 0.6, 10)
    sc.collection.objects.link(cam)
    sc.camera = cam
    out = {}
    for i, t in enumerate(texts):
        cu = bpy.data.curves.new("t", "FONT")
        cu.body = t
        cu.size = 0.9
        ob = bpy.data.objects.new("t", cu)
        sc.collection.objects.link(ob)
        path = os.path.join(tmp_dir, f".title_{i}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(ob)
        out[t] = load(path)
        os.remove(path)
    return out


# ------------------------------------------------------------------ minimap
MAP = 300


def minimap(floor, highlight):
    """the storey's rooms as a small plan (MAP px square, north up as drawn), `highlight` filled warm"""
    rooms = floor["rooms"]
    xs = [v for r in rooms for q in r["rects"] for v in q[:2]]
    ys = [v for r in rooms for q in r["rects"] for v in q[2:]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    k = (MAP - 24) / max(x1 - x0, y1 - y0, 1e-6)
    img = np.zeros((MAP, MAP, 4), np.float32)
    img[..., :3], img[..., 3] = 0.05, 0.55
    for r in rooms:
        on = highlight and r is highlight
        for q in r["rects"]:
            a, b = int(12 + (q[0] - x0) * k), int(12 + (q[1] - x0) * k)
            c, d = int(MAP - 12 - (q[3] - y0) * k), int(MAP - 12 - (q[2] - y0) * k)
            img[c:d, a:b, :3] = (0.98, 0.72, 0.4) if on else (0.32, 0.34, 0.38)
            img[c:d, a:b, 3] = 0.95 if on else 0.75
            for e in ((c, c + 1, a, b), (d - 1, d, a, b), (c, d, a, a + 1), (c, d, b - 1, b)):
                img[e[0]:e[1], e[2]:e[3], :3] = 0.85
                img[e[0]:e[1], e[2]:e[3], 3] = 1
    return img


def over(base, top, x, y, alpha=1.0):
    h, w = top.shape[:2]
    h, w = min(h, base.shape[0] - y), min(w, base.shape[1] - x)
    a = top[:h, :w, 3:4] * alpha
    base[y:y + h, x:x + w, :3] = base[y:y + h, x:x + w, :3] * (1 - a) + top[:h, :w, :3] * a


def crop_text(t):
    ys, xs = np.nonzero(t[..., 3] > 0.02)
    if not len(xs):
        return t
    return t[max(0, ys.min() - 6):ys.max() + 6, max(0, xs.min() - 6):xs.max() + 6]


