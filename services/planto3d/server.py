"""PlanTo3D web app: upload a CAD-exported PDF floor plan -> review the detected plan -> build a walkable 3D house.
Standard library only. Run: python3 server.py [--port 8080] [--host 127.0.0.1] [--cors ORIGIN]
Builds run one at a time in Blender (GPU) in a background thread; progress is polled by the pages.
--cors lets pages on another site call the API from the browser (ORIGIN such as https://example.com, or *).
There is no login: run it on a trusted network, or behind your own backend or proxy."""
import importlib, json, math, os, queue, re, shutil, struct, subprocess, sys, threading, time, traceback, unicodedata, uuid, zipfile
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = os.path.join(HERE, "jobs")
WEB = os.path.join(HERE, "web")
THREE = os.path.join(HERE, "node_modules", "three")
BLENDER = os.environ.get("BLENDER") or shutil.which("blender") or "blender"      # set BLENDER to its full path if it is not on PATH
MAX_UPLOAD = 200 * 1024 * 1024       # plans are small; recordings sent for MP4 conversion are not
MAX_PLAN = 10 * 1024 * 1024          # an imported plan is JSON: a large house is well under 1 MB
BUILD_TIMEOUT = 2 * 3600        # seconds; a high-quality build of a large house takes well under an hour
PAGES, PAGE_DPI = 6, 100        # page images for the review screen: the first pages, 100 dpi = 100/72 px per pt
PAGES_SECONDS = 20              # an upload without the detector draws its pages before it answers: the caller waits
ID = re.compile(r"^[a-f0-9]{12}$")
sys.path.insert(0, HERE)
import areaspec, catalog, checks, detect, fetch_assets, vector  # noqa: E402

os.makedirs(JOBS, exist_ok=True)
builds = queue.Queue()
waiting = []                    # ids of queued jobs, first to be built first: a job's place in it is its queue position
reading = set()                 # ids of jobs whose detector was started and has not finished: no plan is imported meanwhile
lock = threading.Lock()
plan_lock = threading.Lock()    # an import and a build of the same job check the stage and act on it as one step
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
         ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".glb": "model/gltf-binary",
         ".wasm": "application/wasm", ".svg": "image/svg+xml", ".pdf": "application/pdf", ".hdr": "application/octet-stream",
         ".zip": "application/zip"}
CORS = sys.argv[sys.argv.index("--cors") + 1] if "--cors" in sys.argv else None


def jdir(jid):
    return os.path.join(JOBS, jid)


def status(jid, **kw):
    p = os.path.join(jdir(jid), "status.json")
    with lock:
        st = json.load(open(p)) if os.path.exists(p) else {}
        st.update(kw, updated=time.time())
        tmp = p + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(st, fh)
        os.replace(tmp, p)
    return st


def read_status(jid):
    p = os.path.join(jdir(jid), "status.json")
    return json.load(open(p)) if os.path.exists(p) else None


# ------------------------------------------------------------------ system check and the materials download
_blender = None                 # Blender's version, read once ("" = not found)
assets_job = dict(running=False, done=0, total=0, failed=[])
export_lock = threading.Lock()


# Developers only: with PLAN3D_TRUTH_DIR set, the review page offers "Save as reference", which writes the corrected
# plan there as <drawing name>.json, to score the readers against (tools/score_plan.py). Unset in production.
TRUTH_DIR = os.environ.get("PLAN3D_TRUTH_DIR") or ""


def system():
    """what must be in place before a plan is accepted (shown on the home page, enforced on upload and build)"""
    global _blender
    if _blender is None:
        try:
            out = subprocess.run([BLENDER, "--version"], capture_output=True, text=True, timeout=60).stdout
            _blender = (re.search(r"Blender (\d+\.\d+)", out) or [None, ""])[1]
        except (OSError, subprocess.TimeoutExpired):
            _blender = ""
    checks = dict(
        blender=dict(ok=bool(_blender) and tuple(map(int, _blender.split("."))) >= (4, 2), version=_blender),
        pdf_tools=dict(ok=all(shutil.which(c) for c in ("pdftocairo", "pdftotext", "pdfinfo"))),
        viewer=dict(ok=os.path.isfile(os.path.join(THREE, "build", "three.module.js"))),
        materials=dict(ok=not fetch_assets.missing(), **assets_job))
    return dict(ready=all(c["ok"] for c in checks.values()), truth=bool(TRUTH_DIR), **checks)


def fetch_materials():
    def progress(done, total, name):
        assets_job.update(done=done, total=total)
    try:
        assets_job["failed"] = fetch_assets.fetch(progress)
    except Exception as e:
        traceback.print_exc()
        assets_job["failed"] = [str(e)]
    finally:
        assets_job["running"] = False


def export_blend(jid):
    """jobs/<id>/house_blender.zip: the built house as one .blend with every texture packed inside (made once per build)"""
    d = jdir(jid)
    src, out = os.path.join(d, "house_baked.blend"), os.path.join(d, "house_blender.zip")
    if not os.path.exists(src):
        raise ValueError("build the 3D house first")
    with export_lock:
        if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
            tmp = os.path.join(d, "export.blend")
            expr = f"import bpy; bpy.ops.file.pack_all(); bpy.ops.wm.save_as_mainfile(filepath={tmp!r}, copy=True, compress=True)"
            subprocess.run([BLENDER, "-b", src, "--python-expr", expr], check=True, timeout=900, capture_output=True)
            with zipfile.ZipFile(out + ".part", "w", zipfile.ZIP_STORED) as z:       # the .blend is already compressed
                z.write(tmp, "house.blend")
                z.writestr("README.txt", "house.blend - made by PlanTo3D. Open it in Blender 4.2 or newer.\n"
                           "Every texture is packed inside the file. Each storey is one mesh (bake_level_N) with its lamps;\n"
                           "the render engine is Cycles. Textures and models are CC0, from polyhaven.com.\n")
            os.remove(tmp)
            os.replace(out + ".part", out)
    return f"/jobs/{jid}/house_blender.zip"


# ------------------------------------------------------------------ your own furniture models
CUSTOM, THUMBS = os.path.join(fetch_assets.ROOT, "custom"), os.path.join(fetch_assets.ROOT, "thumbs")
thumbs_job = dict(running=False, again=False)


def render_thumbs():
    """pictures of every replaceable item as it will be built now (built-in or your model): a small house with all of
    them in a row is built without baking, then photographed. Runs again if a model changed meanwhile."""
    try:
        while True:
            thumbs_job["again"] = False
            os.makedirs(THUMBS, exist_ok=True)
            with open(os.path.join(THUMBS, "plan.json"), "w") as fh:
                json.dump(catalog.preview_plan(), fh)
            subprocess.run([BLENDER, "-b", "--factory-startup", "-P", os.path.join(HERE, "blender", "gen.py"), "--",
                            os.path.join(THUMBS, "plan.json"), THUMBS, "--no-bake"], capture_output=True, timeout=1800)
            subprocess.run([BLENDER, "-b", os.path.join(THUMBS, "house.blend"), "-P", os.path.join(HERE, "blender", "thumbs.py"),
                            "--", THUMBS], capture_output=True, timeout=600)
            if not thumbs_job["again"]:
                break
    except Exception:
        traceback.print_exc()
    finally:
        thumbs_job["running"] = False


def refresh_thumbs():
    with lock:
        if thumbs_job["running"]:
            thumbs_job["again"] = True
            return
        thumbs_job["running"] = True
    threading.Thread(target=render_thumbs, daemon=True).start()


def furniture():
    if not thumbs_job["running"] and not all(os.path.exists(os.path.join(THUMBS, f"{fn}.png")) for fn in catalog.CATALOG):
        refresh_thumbs()
    return dict(rendering=thumbs_job["running"], items=[
        dict(fn=fn, label=label, custom=os.path.exists(os.path.join(CUSTOM, f"{fn}.glb")),
             thumb=os.path.exists(os.path.join(THUMBS, f"{fn}.png"))) for fn, (label, *_) in catalog.CATALOG.items()])


# ------------------------------------------------------------------ pipeline steps
def png_size(path):
    """(width, height) in pixels from a PNG's header, or None when the file is missing or not a PNG"""
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
    except OSError:
        return None
    return struct.unpack(">II", head[16:24]) if len(head) == 24 and head[:8] == b"\x89PNG\r\n\x1a\n" else None


def render_page(jid, k, timeout=120):
    """page-k.png of the job's PDF as poppler draws it (a page with /Rotate comes out turned, as vector.py reads it).
    -> {n, w, h} in points, or None when the page cannot be drawn: a scan or a damaged page then has no
    background on the review page, but the plan still opens"""
    d = jdir(jid)
    out = os.path.join(d, f"page-{k}")
    try:
        subprocess.run(["pdftocairo", "-png", "-r", str(PAGE_DPI), "-f", str(k), "-l", str(k), "-singlefile",
                        os.path.join(d, "source.pdf"), out], check=True, timeout=max(1, timeout), capture_output=True)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        sys.stderr.write(f"page {k} of {jid} could not be drawn: {type(e).__name__}\n")
        if os.path.exists(out + ".png"):         # half written when the time ran out
            os.remove(out + ".png")
        return None
    size = png_size(out + ".png")
    return dict(n=k, w=round(size[0] * 72 / PAGE_DPI, 2), h=round(size[1] * 72 / PAGE_DPI, 2)) if size else None


def render_pages(jid, seconds=None):
    """page images of the first pages, for any PDF, vector or scanned. Kept in the job's status as `pages`
    ([{n, w, h}], the pages that could be drawn) and `page_count`. `seconds` bounds the whole call."""
    end = time.time() + seconds if seconds else None
    try:
        n = vector.page_count(os.path.join(jdir(jid), "source.pdf"))
    except Exception:                  # pdfinfo cannot open it: no page to show
        traceback.print_exc()
        n = 0
    pages = []
    for k in range(1, min(n, PAGES) + 1):
        left = end - time.time() if end else 120
        if left < 1:
            break
        pg = render_page(jid, k, min(left, 120))
        if pg:
            pages.append(pg)
    status(jid, pages=pages, page_count=n)
    return pages


def run_detect(jid):
    d = jdir(jid)
    pdf = os.path.join(d, "source.pdf")
    try:
        status(jid, stage="detecting", progress=5, message="Reading the drawing")
        render_pages(jid)
        p1 = vector.read_page(pdf, 1)
        if len(p1["segs"]) < 150:
            raise detect.PlanError("This PDF has almost no vector lines - it looks like a scan or photo. "
                                   "Please export the plan from AutoCAD / your CAD tool as a PDF.")
        importlib.reload(detect)          # pick up detector fixes without restarting the server
        plan = detect.detect(pdf)
        plan["checks"] = checks.plan_checks(plan)        # what the review page asks the person to check
        checks.annotate(plan, "detector")                 # source and confidence of every room and opening
        with open(os.path.join(d, "plan.json"), "w") as fh:
            json.dump(plan, fh)
        status(jid, stage="detected", progress=100, message="Plan detected - please review",
               floors=[f["name"] for f in plan["floors"]], scale_source=plan["scale_source"], reader="detector", notice="")
    except Exception as e:
        traceback.print_exc()
        known = isinstance(e, detect.PlanError)
        status(jid, stage="failed", message=str(e) if known else "This drawing could not be read. Is it a floor plan exported from a CAD tool?")
    finally:
        reading.discard(jid)


# seconds per million light-map pixels, by quality, for storey maps and the site map, plus model and export time:
# measured on an M1 Pro (Metal); CALIBRATION scales them to this machine after every build
RATES = {"draft": (12.0, 4.0), "high": (18.0, 8.0)}
FIXED = {"draft": 14.0, "high": 18.0}
CALIBRATION = os.path.join(JOBS, ".eta_calibration.json")


def maps_estimate(quality, maps):
    """seconds for a build whose light maps are {name: size px}: per map, its megapixels times the rate (the site map
    bakes faster), plus model and export time, times this machine's calibration factor"""
    lvl, site = RATES.get(quality, RATES["high"])
    s = FIXED.get(quality, 18.0) + sum((site if n == "site" else lvl) * (px * px / 1e6) for n, px in maps.items())
    try:
        with open(CALIBRATION) as fh:
            s *= max(0.3, min(3.0, float(json.load(fh).get(quality, 1.0))))
    except (OSError, ValueError, TypeError):
        pass
    return s


def calibrate(quality, maps, seconds):
    """after a build: how far the estimate was off on this machine (a running mean of the ratio)"""
    if not maps or seconds <= 0:
        return
    try:
        with open(CALIBRATION) as fh:
            cal = json.load(fh)
    except (OSError, ValueError):
        cal = {}
    base = maps_estimate(quality, maps) / max(0.3, min(3.0, float(cal.get(quality, 1.0))))
    ratio = seconds / max(base, 1.0)
    cal[quality] = round(0.5 * float(cal.get(quality, ratio)) + 0.5 * ratio, 3)
    with open(CALIBRATION + ".part", "w") as fh:
        json.dump(cal, fh)
    os.replace(CALIBRATION + ".part", CALIBRATION)


def estimate(jid, quality):
    """seconds this build should take: the latest finished build of the same quality on this machine, scaled by the
    number of light maps (one per storey + the site); README timings until a build has been measured"""
    n = len((read_status(jid) or {}).get("floors") or [1]) + 1
    past = [st for st in (read_status(j) for j in os.listdir(JOBS) if ID.match(j))
            if st and st.get("build_seconds") and st.get("quality") == quality]
    if not past:
        return {"draft": 45, "high": 240}[quality] * n
    st = max(past, key=lambda s: s["updated"])
    return st["build_seconds"] * n / (len(st.get("floors") or [1]) + 1)


def builder():
    while True:
        jid, quality = builds.get()
        d = jdir(jid)
        with lock:
            if jid in waiting:
                waiting.remove(jid)
        try:
            t0 = time.time()
            status(jid, stage="building", progress=1, message="Starting Blender", started=t0, eta_total=estimate(jid, quality))
            cmd = [BLENDER, "-b", "--factory-startup", "-P", os.path.join(HERE, "blender", "gen.py"), "--",
                   os.path.join(d, "plan.json"), d, "--quality", quality]
            with open(os.path.join(d, "build.log"), "w") as log:
                pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                watchdog = threading.Timer(BUILD_TIMEOUT, pr.kill)      # a hung Blender must not block every later build
                watchdog.start()
                ok = False
                for line in pr.stdout:
                    log.write(line)
                    mm = re.match(r"MAPS (.*)", line)
                    if mm:          # the light maps' sizes are known: estimate from them (maps_estimate)
                        maps = {k: int(v) for k, v in (x.split("=") for x in mm.group(1).split() if "=" in x) if v.isdigit()}
                        status(jid, eta_total=round(maps_estimate(quality, maps)), maps=maps)
                    m = re.match(r"PROGRESS (\d+) (.*)", line)
                    if m:
                        status(jid, progress=int(m.group(1)), message=m.group(2).strip())
                    ok = ok or line.startswith("GEN OK")
                pr.wait()
                watchdog.cancel()
            if not ok or not os.path.exists(os.path.join(d, "house.glb")):
                raise RuntimeError("3D build failed - see build.log")
            for f in ("house.blend", "house.blend1", "house_baked.blend1"):      # keep house_baked.blend only
                if os.path.exists(os.path.join(d, f)):
                    os.remove(os.path.join(d, f))
            status(jid, stage="done", progress=100, message="Ready", quality=quality, build_seconds=round(time.time() - t0))
            try:
                calibrate(quality, (read_status(jid) or {}).get("maps") or {}, time.time() - t0)
            except OSError:
                pass
        except Exception as e:
            traceback.print_exc()
            status(jid, stage="failed", message=str(e))
        finally:
            builds.task_done()


# ------------------------------------------------------------------ plans read by something other than the detector
# Another program (an AI plan reader, a floor plan generator) may hand in the plan, or the person traces it on the
# review page. Everything in such a plan comes from outside: each value is checked for type, range and size and
# the plan is written out afresh, so nothing unchecked reaches Blender, a file path or a page.
READERS = ("ai", "stored", "trace", "manual")      # who made an imported plan; run_detect's plans are "detector"
SCALES = ("labels", "assumed", "user", "given")    # given: the reader measured the scale itself
OPENINGS = ("door", "window", "opening")
COORD = 5000.0                  # feet: no house is larger, and Blender is never handed an absurd number
MOST = dict(floors=12, walls=4000, openings=2000, rooms=500, rects=2000, stairs=60, labels=3000, words=20)
KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,39}$")
FT_100 = 72 / 25.4 * 304.8 / 100        # page points per foot at 1:100: a traced plan's scale until it is set


def _num(v, where, lo=-COORD, hi=COORD):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f"{where} must be a number")
    if not lo <= v <= hi:
        raise ValueError(f"{where} must be between {lo:g} and {hi:g}")
    return round(float(v), 4)


def _int(v, where, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v != int(v):
        raise ValueError(f"{where} must be a whole number")
    if not lo <= v <= hi:
        raise ValueError(f"{where} must be between {lo} and {hi}")
    return int(v)


def _text(v, where, most):
    """a name or label. Control and format characters (line breaks, bidi overrides) become spaces. The pages put
    text into the document as text, never as HTML"""
    if not isinstance(v, str):
        raise ValueError(f"{where} must be text")
    v = "".join(" " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp", "Cs", "Co") else c for c in v).strip()
    if len(v) > most:
        raise ValueError(f"{where} must be at most {most} characters")
    return v


def _list(v, where, most, least=0):
    if not isinstance(v, list):
        raise ValueError(f"{where} must be a list")
    if not least <= len(v) <= most:
        raise ValueError(f"{where} must have {most} entries" if least == most else f"{where} must have {least} to {most} entries")
    return v


def _dict(v, where):
    if not isinstance(v, dict):
        raise ValueError(f"{where} must be an object")
    return v


def _bool(v, where):
    if not isinstance(v, bool):
        raise ValueError(f"{where} must be true or false")
    return v


def _rect(v, where):
    v = [_num(c, f"{where}[{i}]") for i, c in enumerate(_list(v, where, 4, 4))]
    if v[1] - v[0] < 0.01 or v[3] - v[2] < 0.01:
        raise ValueError(f"{where} must be [x0, x1, y0, y1] in feet with x0 < x1 and y0 < y1")
    return v


def _point(v, where, far=COORD):
    return [_num(c, f"{where}[{i}]", -far, far) for i, c in enumerate(_list(v, where, 2, 2))]


def _plain(v, where, depth=0):
    """a value under a key this server does not know by name (a newer detector or reader may add one): kept when
    it is plain data of a modest size"""
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, int):
        return _int(v, where, -10 ** 9, 10 ** 9)
    if isinstance(v, float):
        return _num(v, where, -1e9, 1e9)
    if isinstance(v, str):
        return _text(v, where, 200)
    if depth < 3 and isinstance(v, list) and len(v) <= 200:
        return [_plain(c, f"{where}[{i}]", depth + 1) for i, c in enumerate(v)]
    if depth < 3 and isinstance(v, dict) and len(v) <= 50:
        return {_key(k, where): _plain(c, f"{where}.{k}", depth + 1) for k, c in v.items()}
    raise ValueError(f"{where} is not plain data (numbers, text, true/false, short lists)")


def _key(k, where):
    if not KEY.match(k):
        raise ValueError(f"{where} has a key that is not a plain name")
    return k


def _rest(src, out, where):
    """the keys not checked by name, kept as plain data. Furniture placed by hand (`items`) names the builder's
    functions and model files, so it is never taken from outside"""
    if "items" in src:
        raise ValueError(f"{where}.items: furniture placed by hand cannot be imported")
    for k, v in src.items():
        if k not in out and v is not None:
            out[_key(k, where)] = _plain(v, f"{where}.{k}")
    return out


def _axis(o, r, where):
    """the axis the wall under an opening (or a stair's climb) runs along; the longer side when it is not given"""
    axis = o.get("axis") or ("x" if r[1] - r[0] >= r[3] - r[2] else "y")
    if axis not in ("x", "y"):
        raise ValueError(f'{where}.axis must be "x" or "y"')
    return axis


def clean_bg(b, where, pages):
    """where a storey lies on its page image (README: "Where a plan lies on its drawing"). Every part is optional"""
    out = {}
    if _dict(b, where).get("page") is not None:
        out["page"] = _int(b["page"], where + ".page", 1, pages)
    if b.get("rot") is not None:
        if isinstance(b["rot"], bool) or b["rot"] not in (0, 90, 180, 270):
            raise ValueError(f"{where}.rot must be 0, 90, 180 or 270")
        out["rot"] = int(b["rot"])
    if b.get("pt_per_ft") is not None:
        out["pt_per_ft"] = _num(b["pt_per_ft"], where + ".pt_per_ft", 0.01, 10000)
    if b.get("origin_pt") is not None:
        out["origin_pt"] = _point(b["origin_pt"], where + ".origin_pt", 1e5)
    if b.get("fit") is not None:
        if b["fit"] not in ("given", "matched", "guess"):
            raise ValueError(f'{where}.fit must be "given", "matched" or "guess"')
        out["fit"] = b["fit"]
    if ("pt_per_ft" in out) != ("origin_pt" in out):
        raise ValueError(f"{where} needs both pt_per_ft and origin_pt, or neither")
    return out


def clean_floor(f, i, types, pages):
    w = f"plan.floors[{i}]"
    title = _dict(f, w).get("title")
    out = dict(title=None if title is None else _text(title, w + ".title", 80))
    out["name"] = _text(f.get("name") or (out["title"] or f"Floor {i}").title().replace(" Plan", ""), w + ".name", 60) or f"Floor {i}"
    out["level"] = i                    # storeys are built bottom-up in list order
    out["page"] = _int(f.get("page", 1), w + ".page", 1, pages)
    if f.get("origin_pt") is not None:
        out["origin_pt"] = _point(f["origin_pt"], w + ".origin_pt", 1e5)
    if f.get("size") is not None:
        out["size"] = [_num(c, f"{w}.size[{k}]", 0.01, 2 * COORD) for k, c in enumerate(_list(f["size"], w + ".size", 2, 2))]
    if f.get("bg") is not None:
        out["bg"] = clean_bg(f["bg"], w + ".bg", pages)
    out["walls"] = []
    for k, v in enumerate(_list(f.get("walls"), w + ".walls", MOST["walls"])):
        q = f"{w}.walls[{k}]"
        v = _list(v, q, 5, 4)
        low = v[4] if len(v) == 5 else 0
        if isinstance(low, bool) or low not in (0, 1):
            raise ValueError(f"{q}[4] must be 0 (full height) or 1 (low wall)")
        out["walls"].append(_rect(v[:4], q) + [int(low)])
    out["openings"] = []
    for k, o in enumerate(_list(f.get("openings", []), w + ".openings", MOST["openings"])):
        q = f"{w}.openings[{k}]"
        if _dict(o, q).get("type") not in OPENINGS:
            raise ValueError(f"{q}.type must be one of: {', '.join(OPENINGS)}")
        r = _rect(o.get("rect"), q + ".rect")
        d = dict(type=o["type"], rect=r, axis=_axis(o, r, q))
        if o.get("hinge") is not None:
            d["hinge"] = _point(o["hinge"], q + ".hinge")
        if o.get("swing") is not None:
            if isinstance(o["swing"], bool) or o["swing"] not in (-1, 1):
                raise ValueError(f"{q}.swing must be 1 or -1")
            d["swing"] = int(o["swing"])
        if o.get("double") is not None:
            d["double"] = _bool(o["double"], q + ".double")
        out["openings"].append(_rest(o, d, q))
    out["rooms"] = []
    for k, z in enumerate(_list(f.get("rooms", []), w + ".rooms", MOST["rooms"])):
        q = f"{w}.rooms[{k}]"
        if not isinstance(_dict(z, q).get("type"), str) or z["type"] not in types:
            raise ValueError(f"{q}.type must be one of: {', '.join(sorted(types))}")
        rects = [_rect(r, f"{q}.rects[{j}]") for j, r in enumerate(_list(z.get("rects"), q + ".rects", MOST["rects"], 1))]
        d = dict(type=z["type"], label=_text(z.get("label") or "", q + ".label", 80), rects=rects)
        d["area"] = _num(z["area"], q + ".area", 0, COORD * COORD) if z.get("area") is not None else \
            round(sum((r[1] - r[0]) * (r[3] - r[2]) for r in rects), 1)
        d["dims"] = None if z.get("dims") is None else \
            [_num(c, f"{q}.dims[{j}]", 0, COORD) for j, c in enumerate(_list(z["dims"], q + ".dims", 2, 2))]
        out["rooms"].append(_rest(z, d, q))
    out["stairs"] = []
    for k, st in enumerate(_list(f.get("stairs", []), w + ".stairs", MOST["stairs"])):
        q = f"{w}.stairs[{k}]"
        r = _rect(_dict(st, q).get("rect"), q + ".rect")
        d = dict(rect=r, axis=_axis(st, r, q))
        run = r[1] - r[0] if d["axis"] == "x" else r[3] - r[2]
        # treads of about 10 inches when the reader did not count them
        d["steps"] = _int(st["steps"], q + ".steps", 1, 60) if st.get("steps") is not None else max(3, min(30, round(run * 1.2)))
        d["up"] = _bool(st.get("up", True), q + ".up")
        d["words"] = []
        for j, word in enumerate(_list(st.get("words") or [], q + ".words", MOST["words"])):
            word = _list(word, f"{q}.words[{j}]", 3, 3)
            d["words"].append([_text(word[0], f"{q}.words[{j}][0]", 20)] + _point(word[1:], f"{q}.words[{j}]"))
        out["stairs"].append(_rest(st, d, q))
    out["labels"] = []
    for k, lb in enumerate(_list(f.get("labels", []), w + ".labels", MOST["labels"])):
        q = f"{w}.labels[{k}]"
        out["labels"].append(_rest(lb, dict(text=_text(_dict(lb, q).get("text"), q + ".text", 120), at=_point(lb.get("at"), q + ".at")), q))
    # rooms follow the walls on the review page when the reader gave none (the builder lays floors per room)
    out["auto_rooms"] = _bool(f["auto_rooms"], w + ".auto_rooms") if f.get("auto_rooms") is not None else not out["rooms"]
    return _rest(f, out, w)


def clean_plan(plan, name, pages):
    """a plan from outside, checked value by value -> the plan for plan.json. A ValueError says what is wrong, where.
    `pages`: how many pages the PDF has (a storey's page number must exist)"""
    if _dict(plan, "plan").get("units", "ft") != "ft":
        raise ValueError('plan.units must be "ft": give every length in feet')
    out = dict(version=_int(plan.get("version", 1), "plan.version", 1, 1),
               source=_text(plan.get("source") or name, "plan.source", 120), units="ft")
    if plan.get("scale_pt_per_ft") is not None:
        out["scale_pt_per_ft"] = _num(plan["scale_pt_per_ft"], "plan.scale_pt_per_ft", 0.01, 10000)
    out["scale_source"] = plan.get("scale_source", "assumed")
    if out["scale_source"] not in SCALES:
        raise ValueError(f"plan.scale_source must be one of: {', '.join(SCALES)}")
    if plan.get("wall_pt") is not None:
        out["wall_pt"] = _num(plan["wall_pt"], "plan.wall_pt", 0, 1000)
    out["floor_height"] = _num(plan.get("floor_height", 10.0), "plan.floor_height", 8, 14)       # the review page's limits
    out["slab"] = _num(plan.get("slab", 0.5), "plan.slab", 0.25, 1.5)
    if plan.get("furnish") is not None:
        out["furnish"] = _bool(plan["furnish"], "plan.furnish")
    types = {t for t, _ in detect.ROOM_TYPES} | {"yard", "room", "duct"}       # every type the detector can give a room
    out["floors"] = [clean_floor(f, i, types, max(1, pages)) for i, f in enumerate(_list(plan.get("floors"), "plan.floors", MOST["floors"], 1))]
    return _rest(plan, out, "plan")


def empty_plan(name, pages):
    """nothing read: one storey over page 1, for tracing the walls by hand. Its coordinates are the page's own
    (plan (0, 0) is the page's lower-left corner) at 1:100 until the scale is set on the review page, so whatever
    is traced lies on the drawing. Rooms follow the walls as they are drawn (auto_rooms)."""
    w, h = next(((p["w"], p["h"]) for p in pages if p["n"] == 1), (595.0, 842.0))      # (A4 when page 1 has no image)
    return dict(version=1, source=name, units="ft", scale_pt_per_ft=round(FT_100, 4), scale_source="assumed",
                floor_height=10.0, slab=0.5,
                floors=[dict(title=None, name="Ground Floor", level=0, page=1, origin_pt=[0.0, h],
                             size=[round(w / FT_100, 2), round(h / FT_100, 2)], auto_rooms=True,
                             walls=[], openings=[], rooms=[], stairs=[], labels=[])])


def unbuildable(plan):
    """why Blender cannot build this plan, or None. gen.py takes each storey's outline from its walls and lays
    floors, lamps and furniture per room; it reads these lists without asking"""
    floors = plan.get("floors") if isinstance(plan, dict) else None
    if not isinstance(floors, list) or not floors:
        return "The plan has no floors."
    for k, f in enumerate(floors):
        if not isinstance(f, dict) or not all(isinstance(f.get(key), list) for key in ("walls", "openings", "rooms", "stairs")):
            return "The plan is incomplete: open it on the review page and save it again."
        name = str(f.get("name") or f"Floor {k}")[:60]
        if not f["walls"]:
            return f"{name} has no walls yet: draw them on the review page first."
    if not any(f["rooms"] for f in floors):
        return "The plan has no rooms: close the walls around each room (rooms are found between walls, doors and windows)."
    return None


# ------------------------------------------------------------------ http
class H(BaseHTTPRequestHandler):
    server_version = "PlanTo3D/1"

    def log_message(self, fmt, *a):
        if not self.path.startswith("/api/jobs/") or "status" not in self.path:
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % a))

    def send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.cors()
        self.end_headers()
        self.wfile.write(body)

    def cors(self):
        if CORS:
            self.send_header("Access-Control-Allow-Origin", CORS)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Filename, X-Detect")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE")

    def do_OPTIONS(self):               # the browser's question before a cross-site POST
        self.send_response(204)
        self.cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def file(self, path, root):
        path = os.path.realpath(path)
        if not path.startswith(os.path.realpath(root) + os.sep) or not os.path.isfile(path):
            return self.send(404, {"error": "not found"})
        ext = os.path.splitext(path)[1].lower()
        size = os.path.getsize(path)
        self.send_response(200)
        self.send_header("Content-Type", TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(size))
        # job outputs change on every rebuild: never let the browser show a stale house
        fresh = ext in (".json", ".html", ".js", ".css", ".png") or "/jobs/" in path.replace(os.sep, "/")
        self.send_header("Cache-Control", "no-cache" if fresh else "max-age=3600")
        self.cors()
        self.end_headers()
        with open(path, "rb") as fh:
            shutil.copyfileobj(fh, self.wfile)

    def do_GET(self):
        u = urlparse(self.path)
        p = unquote(u.path)
        if p in ("/", "/index.html"):
            return self.file(os.path.join(WEB, "index.html"), WEB)
        if p.startswith("/web/"):
            return self.file(os.path.join(WEB, p[5:]), WEB)
        if p.startswith("/examples/"):
            return self.file(os.path.join(HERE, "examples", p[10:]), os.path.join(HERE, "examples"))
        if p.startswith("/thumbs/"):
            return self.file(os.path.join(THUMBS, p[8:]), THUMBS)
        if p == "/api/areas":          # the area library (areaspec.py): specs of area types no builder knows
            return self.send(200, areaspec.load())
        if p == "/api/furniture":
            return self.send(200, furniture())
        if p.startswith("/three/"):
            return self.file(os.path.join(THREE, p[7:]), THREE)
        if p.startswith("/jobs/"):
            parts = p[6:].split("/", 1)
            if len(parts) == 2 and ID.match(parts[0]):
                return self.file(os.path.join(jdir(parts[0]), parts[1]), jdir(parts[0]))
            return self.send(404, {"error": "not found"})
        m = re.match(r"^/api/jobs/([a-f0-9]{12})$", p)
        if m:
            st = read_status(m.group(1))
            if st and st.get("stage") == "building" and st.get("started"):      # counted here: the viewer's clock may differ
                left = st["started"] + st["eta_total"] - time.time()
                st["eta_left"] = max(0, round(min(left, 15) if st.get("progress", 0) >= 92 else left))   # 92 = exporting, the last step
            if st and st.get("stage") == "queued" and m.group(1) in waiting:    # counted here: it changes as builds finish
                st["queue_position"] = waiting.index(m.group(1)) + 1
            if st:      # who made the plan ("" while there is none; jobs from before readers were recorded: the detector)
                st.setdefault("reader", "detector" if st.get("floors") else "")
                st.setdefault("notice", "")
            return self.send(200 if st else 404, st or {"error": "no such job"})
        if p == "/api/system":
            return self.send(200, system())
        if p == "/api/jobs":
            out = []
            for jid in sorted(os.listdir(JOBS), key=lambda j: -os.path.getmtime(jdir(j))):
                st = read_status(jid) if ID.match(jid) else None
                if st:
                    out.append(dict(id=jid, **{k: st.get(k) for k in ("name", "stage", "updated", "floors")}))
            return self.send(200, out[:30])
        self.send(404, {"error": "not found"})

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not 0 <= n <= MAX_UPLOAD:
            raise ValueError("file too large (200 MB max)")
        return self.rfile.read(n)

    def do_DELETE(self):
        p = urlparse(self.path).path
        m = re.match(r"^/api/jobs/([a-f0-9]{12})$", p)
        if m and os.path.isdir(jdir(m.group(1))):
            if (read_status(m.group(1)) or {}).get("stage") in ("building", "queued"):
                return self.send(409, {"error": "This plan is being built. Delete it when the build has finished."})
            shutil.rmtree(jdir(m.group(1)))
            return self.send(200, {"ok": True})
        m = re.match(r"^/api/furniture/(\w+)$", p)
        if m and m.group(1) in catalog.CATALOG:               # back to the built-in item
            for f in (os.path.join(CUSTOM, m.group(1) + ".glb"), os.path.join(THUMBS, m.group(1) + ".png")):
                if os.path.exists(f):
                    os.remove(f)
            refresh_thumbs()
            return self.send(200, {"ok": True})
        self.send(404, {"error": "not found"})

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            m = re.match(r"^/api/furniture/(\w+)$", p)
            if m and m.group(1) in catalog.CATALOG:           # your model for this item, as a .glb file
                data = self.body()
                if not data.startswith(b"glTF"):
                    return self.send(400, {"error": "Please upload a .glb file (binary glTF)."})
                os.makedirs(CUSTOM, exist_ok=True)
                with open(os.path.join(CUSTOM, m.group(1) + ".glb"), "wb") as fh:
                    fh.write(data)
                if os.path.exists(os.path.join(THUMBS, m.group(1) + ".png")):
                    os.remove(os.path.join(THUMBS, m.group(1) + ".png"))
                refresh_thumbs()
                return self.send(200, {"ok": True})
            if p == "/api/mp4":                               # a WebM recording in, the same video as MP4 out
                if not shutil.which("ffmpeg"):
                    return self.send(501, {"error": "ffmpeg is not installed on the server"})
                r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                                    "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-movflags", "frag_keyframe+empty_moov", "-f", "mp4", "pipe:1"],
                                   input=self.body(), capture_output=True, timeout=600)
                if r.returncode or not r.stdout:
                    return self.send(500, {"error": "the recording could not be converted"})
                return self.send(200, r.stdout, "video/mp4")
            if p == "/api/materials":            # start the Poly Haven download (the home page's button)
                with lock:
                    start = not assets_job["running"]
                    if start:
                        assets_job.update(running=True, done=0, total=0, failed=[])
                if start:
                    threading.Thread(target=fetch_materials, daemon=True).start()
                return self.send(200, {"ok": True})
            if (p == "/api/upload" or p.endswith("/build")) and not system()["ready"]:
                return self.send(503, {"error": "The server is not set up yet: open its home page to see what is missing."})
            if p == "/api/upload":
                data = self.body()
                name = os.path.basename(unquote(self.headers.get("X-Filename") or "plan.pdf"))[:120]
                if not data.startswith(b"%PDF"):
                    return self.send(400, {"error": "Please upload a PDF exported from your CAD tool "
                                                    "(images and DWG are not supported yet)."})
                jid = uuid.uuid4().hex[:12]
                os.makedirs(jdir(jid))
                with open(os.path.join(jdir(jid), "source.pdf"), "wb") as fh:
                    fh.write(data)
                # X-Detect: 0 = the plan will come from elsewhere (POST /api/jobs/{id}/import): only the pages are drawn
                detecting = (self.headers.get("X-Detect") or "").strip() != "0"
                status(jid, name=name, stage="uploaded", progress=0, created=time.time(),
                       message="Uploaded" if detecting else "Uploaded - waiting for the plan")
                if not detecting:
                    pages = render_pages(jid, PAGES_SECONDS)
                    return self.send(200, {"id": jid, "pages": len(pages)})
                reading.add(jid)
                threading.Thread(target=run_detect, args=(jid,), daemon=True).start()
                return self.send(200, {"id": jid})
            if p == "/api/areas":      # add a spec (from our backend's AI classifier, or a person): validated first
                body = json.loads(self.body() or b"null")
                if not isinstance(body, dict):
                    return self.send(400, {"error": "send {spec, source, reviewed}"})
                try:
                    clean = areaspec.save(body.get("spec"), source=str(body.get("source", "ai"))[:20],
                                          reviewed=body.get("reviewed") is True)
                except ValueError as e:
                    return self.send(400, {"error": str(e)[:500]})
                return self.send(200, {"ok": True, "type": clean["type"]})
            m = re.match(r"^/api/jobs/([a-f0-9]{12})/reference$", p)
            if m and TRUTH_DIR and os.path.isdir(jdir(m.group(1))):
                plan = json.loads(self.body() or b"null")
                if not isinstance(plan, dict) or not isinstance(plan.get("floors"), list) or not plan["floors"]:
                    return self.send(400, {"error": "invalid plan"})
                stem = os.path.splitext((read_status(m.group(1)) or {}).get("name") or m.group(1))[0]
                stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")[:100] or m.group(1)
                os.makedirs(TRUTH_DIR, exist_ok=True)
                with open(os.path.join(TRUTH_DIR, stem + ".json"), "w") as fh:
                    json.dump(plan, fh, indent=1)
                return self.send(200, {"ok": True, "name": stem + ".json"})
            m = re.match(r"^/api/jobs/([a-f0-9]{12})/import$", p)
            if m and os.path.isdir(jdir(m.group(1))):
                return self.import_plan(m.group(1))
            m = re.match(r"^/api/jobs/([a-f0-9]{12})/(plan|build|export)$", p)
            if m and os.path.isdir(jdir(m.group(1))):
                jid, what = m.groups()
                if what == "export":
                    return self.send(200, {"url": export_blend(jid)})
                body = self.body()
                with plan_lock:
                    st = read_status(jid) or {}
                    if st.get("stage") in ("building", "queued"):
                        return self.send(409, {"error": "a build is already running"})
                    if what == "plan":
                        plan = json.loads(body)
                        if not isinstance(plan, dict) or not isinstance(plan.get("floors"), list) or not plan["floors"]:
                            return self.send(400, {"error": "invalid plan"})
                        plan["checks"] = checks.plan_checks(plan)
                        checks.annotate(plan, "user")     # what the person added is theirs; the rest keeps its source
                        with open(os.path.join(jdir(jid), "plan.json"), "w") as fh:
                            json.dump(plan, fh)
                        return self.send(200, {"ok": True})
                    q = json.loads(body or b"{}").get("quality", "high")
                    q = q if q in ("draft", "high") else "high"
                    try:
                        with open(os.path.join(jdir(jid), "plan.json")) as fh:
                            why = unbuildable(json.load(fh))
                    except (OSError, ValueError):
                        why = "There is no plan to build yet."
                    if why:                 # a traced plan can be saved half done; Blender would only fail on it
                        return self.send(400, {"error": why})
                    status(jid, stage="queued", progress=0, message=f"Waiting for the 3D builder ({builds.qsize()} ahead)",
                           builds=(st.get("builds") or 0) + 1)
                    with lock:
                        waiting.append(jid)
                builds.put((jid, q))
                return self.send(200, {"ok": True})
            self.send(404, {"error": "not found"})
        except (ValueError, json.JSONDecodeError) as e:
            self.send(400, {"error": str(e)})
        except RecursionError:            # JSON nested deeper than Python's parser goes
            self.send(400, {"error": "the JSON is nested too deeply"})
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            traceback.print_exc()
            self.send(500, {"error": "Blender could not write the file"})

    def import_plan(self, jid):
        """POST /api/jobs/{id}/import {plan, reader, notice}: a plan read by another program takes the detector's
        place; plan null = an empty plan to trace the walls on. Only before the job's first build."""
        n = int(self.headers.get("Content-Length") or 0)
        if not 0 <= n <= MAX_PLAN:
            return self.send(413, {"error": "plan too large (10 MB max)"})
        req = _dict(json.loads(self.rfile.read(n) or b"null"), "the request body")
        if req.get("reader") not in READERS:
            raise ValueError(f"reader must be one of: {', '.join(READERS)}")
        notice = _text(req.get("notice") or "", "notice", 300)
        with plan_lock:
            st = read_status(jid) or {}
            if jid in reading or st.get("stage") in ("detecting", "queued", "building"):
                return self.send(409, {"error": "This plan is being read or built. Import a plan when that has finished."})
            if st.get("stage") not in ("uploaded", "detected", "failed") or st.get("builds") or st.get("started"):
                return self.send(409, {"error": "This plan has already been sent to the 3D builder. Upload the PDF again to import another plan."})
            if "pages" not in st:           # a job from before page sizes were recorded: its images are on disk
                pages = [dict(n=k, w=round(s[0] * 72 / PAGE_DPI, 2), h=round(s[1] * 72 / PAGE_DPI, 2))
                         for k in range(1, PAGES + 1) for s in [png_size(os.path.join(jdir(jid), f"page-{k}.png"))] if s]
                st = status(jid, pages=pages)
            count = st.get("page_count") or max([p["n"] for p in st["pages"]] or [1])
            name = st.get("name") or "plan.pdf"
            plan = empty_plan(name, st["pages"]) if req.get("plan") is None else clean_plan(req["plan"], name, count)
            have = {p["n"] for p in st["pages"]}
            for k in sorted(({f["page"] for f in plan["floors"]} | {f.get("bg", {}).get("page", 0) for f in plan["floors"]}) - have - {0}):
                pg = render_page(jid, k, PAGES_SECONDS)       # a storey on a page after the first six
                if pg:
                    st = status(jid, pages=st["pages"] + [pg])
            plan["checks"] = checks.plan_checks(plan)
            checks.annotate(plan, {"ai": "ai", "detector": "detector"}.get(req["reader"], "user"))
            with open(os.path.join(jdir(jid), "plan.json.part"), "w") as fh:
                json.dump(plan, fh)
            os.replace(os.path.join(jdir(jid), "plan.json.part"), os.path.join(jdir(jid), "plan.json"))
            status(jid, stage="detected", progress=100, floors=[f["name"] for f in plan["floors"]], scale_source=plan["scale_source"],
                   reader=req["reader"], notice=notice,
                   message="Plan imported - please review" if req.get("plan") is not None else "Nothing was read - trace the walls over the drawing")
        self.send(200, {"ok": True})


if __name__ == "__main__":
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8080
    host = sys.argv[sys.argv.index("--host") + 1] if "--host" in sys.argv else "127.0.0.1"
    for jid in os.listdir(JOBS):           # builds interrupted by a restart
        st = read_status(jid) if ID.match(jid) else None
        if st and st.get("stage") in ("building", "queued", "detecting"):
            status(jid, stage="failed", message="interrupted by a server restart - press Build again")
    threading.Thread(target=builder, daemon=True).start()
    print(f"PlanTo3D on http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), H).serve_forever()
