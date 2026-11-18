"""Download the CC0 textures, models and sky this project builds with, from Poly Haven, into ./assets (about 75 MB).
python3 fetch_assets.py [--tour]    files already present are skipped; --tour adds the dusk sky for blender/cinema.py
The server's home page runs the same download from its "Download materials" button."""
import json, os, sys, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
MODELS = ["covered_car", "outdoor_table_chair_set_01", "street_lamp_01"]
TEXTURES = ["american_walnut_veneer", "anti_skid_tiles", "asphalt_02", "black_walnut_veneer_01", "caban", "concrete_floor",
            "concrete_tiles", "cotton_jersey", "dry_river_pebbles", "floral_jacquard", "granite_tile",
            "herringbone_pavement", "hessian_380", "knitted_fleece", "laminate_floor_02", "large_floor_tiles_02",
            "leafy_grass", "long_white_tiles", "marble_01", "oak_veneer_01", "quatrefoil_jacquard_fabric",
            "rough_linen", "square_concrete_pavers", "stretch_poplin", "terracotta_floor_tiles", "terrazzo_tiles",
            "velour_velvet", "waffle_pique_cotton", "white_plaster_02", "wool_boucle"]
SKY, TOUR_SKY = "kloofendal_48d_partly_cloudy_puresky", "qwantani_dusk_2_puresky"
UA = {"User-Agent": "planto3d-fetch/1.0"}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()


def save(url, path):
    if os.path.exists(path):
        return
    if not os.path.realpath(path).startswith(os.path.realpath(ROOT) + os.sep):     # (file names come from the web reply)
        raise ValueError(f"refusing to write outside the assets folder: {path}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = get(url)
    with open(path + ".part", "wb") as f:
        f.write(data)
    os.replace(path + ".part", path)        # a download cut short never leaves a half-written file under the real name


def files(asset):
    return json.loads(get(f"https://api.polyhaven.com/files/{asset}"))


def missing():
    """names of the assets that are not on disk yet (the server's system check reports these)"""
    out = [m for m in MODELS if not os.path.exists(os.path.join(ROOT, "models", m, f"{m}_1k.gltf"))]
    out += [t for t in TEXTURES if not os.path.isdir(os.path.join(ROOT, "textures", t))]     # (some have no colour map, only bump)
    return out + ([] if os.path.exists(os.path.join(ROOT, "hdri", "sky.hdr")) else ["sky"])


def fetch(progress=lambda done, total, name: None, tour=False):
    """download whatever is missing; progress(done, total, name) is called before each asset. -> names that failed"""
    todo = [("model", m) for m in MODELS] + [("texture", t) for t in TEXTURES] + [("sky", SKY)] + ([("sky", TOUR_SKY)] if tour else [])
    failed, need = [], missing()
    for k, (kind, name) in enumerate(todo):
        progress(k, len(todo), name)
        have = os.path.exists(os.path.join(ROOT, "hdri", f"{name}.hdr")) if name == TOUR_SKY else ("sky" if kind == "sky" else name) not in need
        if have:
            continue
        try:
            f = files(name)
            if kind == "model":
                g = f["gltf"]["1k"]["gltf"]
                d = os.path.join(ROOT, "models", name)
                save(g["url"], os.path.join(d, os.path.basename(g["url"])))
                for rel, inc in g["include"].items():
                    save(inc["url"], os.path.join(d, rel))
            elif kind == "texture":
                for key, short in (("Diffuse", "diff"), ("nor_gl", "nor"), ("Rough", "rough")):
                    if key in f:
                        save(f[key]["1k"]["jpg"]["url"], os.path.join(ROOT, "textures", name, f"{short}.jpg"))
            elif name == SKY:
                save(f["hdri"]["1k"]["hdr"]["url"], os.path.join(ROOT, "hdri", "sky.hdr"))
            else:
                save(f["hdri"]["2k"]["hdr"]["url"], os.path.join(ROOT, "hdri", f"{name}.hdr"))
        except Exception as e:      # one asset failing (network, renamed on Poly Haven) must not stop the rest
            failed.append(name)
            print("FAILED", name, e, flush=True)
    progress(len(todo), len(todo), "")
    return failed


if __name__ == "__main__":
    bad = fetch(lambda k, n, name: print(f"[{k}/{n}] {name}", flush=True), tour="--tour" in sys.argv)
    sys.exit(f"could not download: {', '.join(bad)}" if bad else 0)
