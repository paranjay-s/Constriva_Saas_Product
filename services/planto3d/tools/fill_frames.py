"""Fill frames skipped by a --step 2 render: each missing f_N.jpg = average of its two neighbours.
python3 tools/fill_frames.py FRAMES_DIR"""
import os, sys
from PIL import Image
d = sys.argv[1]
f = lambda i: os.path.join(d, f"f_{i:05d}.jpg")
last = max(int(n[2:7]) for n in os.listdir(d) if n.startswith("f_"))
filled = 0
for i in range(1, last):
    if not os.path.exists(f(i)) and os.path.exists(f(i - 1)) and os.path.exists(f(i + 1)):
        Image.blend(Image.open(f(i - 1)), Image.open(f(i + 1)), 0.5).save(f(i), quality=94)
        filled += 1
missing = [i for i in range(last + 1) if not os.path.exists(f(i))]
assert not missing, f"still missing {missing[:10]}"
print("filled", filled, "frames, sequence 0 ..", last, "complete")
