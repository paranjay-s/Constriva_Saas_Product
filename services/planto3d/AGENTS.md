# Guide for AI coding agents

PlanTo3D turns a CAD-exported floor plan PDF into a furnished 3D house you can walk through in a browser.
There is no AI model in the pipeline: detection is geometry, furniture is rules, the 3D is Blender. Keep it that way.

## Run it

```bash
./run.sh --port 8080              # npm install (three.js) + python3 server.py
python3 fetch_assets.py           # CC0 textures and models into assets/ (about 75 MB), once
```

Needs Python 3, Node 18+, Blender 4.2+ and poppler. If Blender is not on `PATH`, set `BLENDER` to its full path.
`GET /api/system` says what is missing. Try it with `examples/sample_plan.pdf`.

## Map

| File | Job |
|---|---|
| `server.py` | HTTP server (standard library only), one job folder per plan in `jobs/`, build queue (one Blender at a time) |
| `vector.py` | PDF page -> line segments, curves, fills, words (poppler) |
| `detect.py` | segments -> plan JSON: walls, openings, rooms, stairs, scale. Units: feet, y up |
| `furnish.py` | plan JSON -> furniture items `{fn, args, kw, box}`. Pure Python, no Blender |
| `catalog.py` | furniture that people may replace with their own `.glb` (`assets/custom/<name>.glb`) |
| `blender/gen.py` | plan JSON -> house (run inside Blender). `CALLS` maps item `fn` to the function that builds it |
| `blender/lib.py` | materials, box meshes, furniture parts. Feet in, metres out (`F = 0.3048`) |
| `blender/bake.py` | light maps (Cycles) and `house.glb` export |
| `web/` | `index.html` (upload), `edit.html` + `edit.js` (review), `view.html` + `view.js` (walkthrough), `walk.js` (collision, stairs, start point), `furniture.html` |
| `examples/` | `sample_plan.pdf`, its generator `make_sample.py`, `embed.html` |
| `tools/` | video and debugging helpers, not used by the server |

Flow: upload -> `run_detect` -> `plan.json` -> review page edits it -> `POST …/build` -> `gen.py` -> `bake.py` -> `house.glb`, `meta.json`, light maps -> `view.js`.

## Conventions

- **Units.** Plan JSON and all furniture code are in feet. `meta.json` and the browser are in metres.
- **Rotation.** `rot` 0 = the item's front faces -y and its back is on +y; 90 = front +x; 180 = +y; 270 = -x.
- **Rectangles** are `[x0, x1, y0, y1]`. A wall is `[x0, x1, y0, y1, low]` (`low` 1 = parapet height).
- **Stages** of a job: `uploaded`, `detecting`, `detected`, `queued`, `building`, `done`, `failed` (in `jobs/<id>/status.json`).
- Messages a person will read are raised as `detect.PlanError`. Anything else is logged and shown as a generic message.
- The server uses the standard library only. Do not add Python dependencies. The browser uses three.js and nothing else.
- Comments say why, not what. Match the style of the file you are in.

## Tests: run them before you finish

```bash
tests/run_all.sh                    # detector on the sample, furniture clashes, stair and wall walking
python3 tests/test_sample.py        # the sample must be read exactly
CHROME=/path/to/chromium node tests/test_site.mjs examples/sample_plan.pdf http://127.0.0.1:8080
```

`test_site.mjs` needs a running server and takes about 2 minutes (it builds a draft house in a real headless browser).
Run it after any change to `web/`, `server.py` or `blender/`.
If you change `examples/make_sample.py`, run it to rewrite the PDF and keep its `EXPECT` in step.

## How to change things

- **A new furniture item:** write the builder in `blender/gen.py` (or `lib.py`), add it to `CALLS`, place it from a rule in `furnish.py` with its footprint `box`. Add it to `catalog.py` only if people should be able to replace it.
- **A new room type:** add its keywords to `ROOM_TYPES` in `detect.py`, a rule in `furnish.py`, a floor material in `gen.py` (`FLOOR_MAT`, `INDOOR`), and a colour in `web/edit.js` (`TYPES`, `ZCOL`).
- **A detector fix:** make it general, not a special case for one drawing. Check the sample still passes. The scores on real drawings need private fixtures (`PLANTO3D_FIXTURES`) that are not in the repository.
- **A new API call:** add it in `server.py` (`do_GET` / `do_POST` / `do_DELETE`), and to the table in `README.md`.
- **A new texture or model:** add its Poly Haven name to `fetch_assets.py`; never commit asset files.

## Traps

- Blender is often installed as a snap: it cannot read `/tmp`. Give it paths inside the project.
- `gen.py` does `from lib import *`: do not name a global in `gen.py` after one in `lib.py`.
- Everything in a saved plan comes from a browser. Validate it before it reaches a file path or `innerHTML`.
- `jobs/`, `assets/` and `node_modules/` are not in git. Do not commit real client drawings or screenshots of them: use the sample plan.
- The walkthrough's lighting is baked. Hiding or moving objects in the browser leaves their shadows behind; change the build instead.
- High-poly models make the browser slow. Trees and plants are procedural for that reason.
- There is no login. Do not add features that assume the server is private unless you add the protection too.
