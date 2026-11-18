# Patches to the vendored PlanTo3D

This folder is a `git subtree` of https://github.com/23f2005639/planTo3D (branch `main`).
Every change made here, and not yet upstream, is listed below so it can be re-checked after a pull:

    git subtree pull --prefix=services/planto3d https://github.com/23f2005639/planTo3D.git main --squash

Vendored from upstream commit `5456ab8`. Upstream has no licence file.

## 1. Page URLs are relative (web/edit.html, edit.js, view.html, view.js, furniture.html)

Why: the pages are served behind our backend at `/api/v1/3d/embed/<token>/web/...`. Their requests used
root paths (`/api/...`, `/jobs/...`, `/three/...`, `/thumbs/...`, `/web/...`), which would leave that prefix
and lose the token.

What: every such path is now relative to the page (`../api/...`, `../jobs/...`, `../three/...`,
`../thumbs/...`, `style.css`, `edit.js`, `./walk.js`, `view.html?job=...`), including the import map in
`view.html` and the Draco decoder path. `view.js` prefixes the export URL the server returns (`/jobs/...`)
with `..`. The Home links point to `../`.

Standalone use is unchanged: from `/web/edit.html`, `../api/x` is `/api/x`. `web/index.html` is served at
`/` and is not embedded, so it is untouched.

## 2. Review page embed mode (web/edit.html, web/edit.js)

Why: in our product the options (furniture, quality) and the build progress belong to the page that frames
the review page, so the review page must not show a second set of build controls.

What: with `?embed` and a parent window, the body gets class `embed`, which hides the Home link, the
quality list, the Build button, the Furnish checkbox and the build box. The page posts
`{source: 'planto3d', job, type: 'ready' | 'failed' | 'saved', ...}` to its parent, and saves the plan when
the parent posts `{source: 'planto3d-host', type: 'save', furnish: true | false}` (only messages from the
framing window are accepted). Without `?embed` nothing changes.

## 3. Live queue position (server.py)

Why: our build screen shows where a job is in the queue. Upstream writes "N ahead" once, when the job is
queued, and it never changes.

What: `waiting` lists the queued job ids in order. `GET /api/jobs/{id}` adds `queue_position` (1 = next)
while the job's stage is `queued`.

## 4. The browser test finds itself in a folder with a space (tests/test_site.mjs)

Why: the test uploads its own source file as the "not a PDF" case and took its path from
`new URL(import.meta.url).pathname`, which keeps `%20` for a space. In a checkout such as
`.../constriva saas/...` the browser was handed a file that does not exist and the first
assertion failed with "Failed to fetch".

What: the path now comes from `fileURLToPath(import.meta.url)`.

## 5. Headless WebGL backend follows the platform (tests/test_site.mjs, tools/record.mjs)

Why: both start Chromium with `--use-angle=gl-egl`, which exists on Linux only. On macOS
WebGL then never starts, the walkthrough stays on "Loading…" and the test fails at the
recording step.

What: the backend is `gl-egl` on Linux and `metal` on macOS, or whatever `ANGLE` is set to.

## 6. A plan whose build failed can be opened for review again (web/edit.js)

Why: a freshly loaded review page treated every failed job as a failed detection and never
loaded the plan. After a failed build, or a build interrupted by a server restart (whose
message is "press Build again"), the plan could not be opened to build it again.

What: the page stops with the failure message only when the job has no detected floors
(`status.floors` is set when detection succeeds and is kept afterwards). Otherwise it loads
the plan as usual.

## 7. Doorways in coloured floors are not windows; windows stop the walker (detect.py, blender/gen.py, tests)

Why: drawings that colour their floors stroke each colour fill with its own pale pen. Where the floor colour runs
into a doorway, the fill's edges gave two parallel "glass" lines across the gap, and the doorway was built as a
window (four doorways in a real drawing; the map, drawn from the plan, still showed a gap or a door). Separately,
the walker's colliders left out every opening, so it could walk straight through a window.

What: `detect.py` drops strokes that run exactly along the edge of a pale colour fill in that fill's own colour
(`fill_outlines`, `is_outline`) before it looks for window glass. `gen.py` adds the wall under each window's sill to
the walker's colliders, and writes what it built at every opening to `meta.json` (`floors[k].openings`: type, built
as window or doorway, rect, sill, head). `tests/test_doorway.py` (detector) and `tests/test_openings.mjs` (every
opening of a built house against `plan.json`: type, position, sill, and whether the walker can pass) are in
`tests/run_all.sh`. The sample plan and OPT 5 are read exactly as before.

## 8. Stairs climb from their UP mark, and the floor above a stair is cut only where it must be (blender/gen.py, web/walk.js, tests/test_walk.mjs)

Why: two defects. (a) Stairs ran in reverse. The detector marks every flight near an UP word as `up`, and the two
flights of a dog-leg lie side by side, so both got it; `stair_parts` started the climb on whichever flight was listed
first, which in OPT 5 and the SF plan was the flight that holds DN, so the bottom step was built at the top end.
(b) The walker could not climb from the first floor to the roof. The floor above a stair was cut over the whole stair
of the storey below, including over its first steps, which is exactly the strip in front of the next storey's own
first step; with no floor there the walker could not reach it. The roof slab had no opening for the top stair.

What: `stair_parts` starts on the flight nearest the UP word (falls back to the old rule when there is none). The
floor and slab above a stair are cut only over landings and steps that come within 7 ft (2.1 m) of the storey above,
in `gen.py` (`well_prev`, `HEADROOM`) and in `walk.js` (`heights`, `HEADROOM`, `stepHeight`), and the roof slab is cut
over the top storey's stair (its parapet stays whole). `tests/test_walk.mjs` also walks back down every stair and
checks that each climb starts on the flight and at the end where the plan writes UP.

## 9. Upper storeys end at their slab edge (blender/gen.py, web/walk.js, web/view.js, tests/test_storeys.mjs)

Why: on an upper storey the walker could walk out of a balcony, yard or open shaft and on into the air, at that
storey's height, well past the building: the walker gave every storey a floor everywhere. The slab under an upper
storey was its own outline minus the open-to-sky zones of both storeys, so a yard of the storey above had a hole
where it stood on the roof of a room below, and nothing guarded an edge that dropped to the storey below.

What: `upper_slab` builds the slab under storey k from both outlines, open only where nothing stands on it (a
shaft / cutout of this storey, a yard over an open area below or over no storey, an open area below with no room of
this storey over it, the stairwell). `edge_guards` puts a parapet (wall thickness, 3.5 ft) along every slab edge that
drops away and has no wall or opening on it, and ignores rounding slivers between slab pieces. `meta.json` gets
`floors[k].floor` (the slab, metres) for k >= 1 and the parapets as colliders; `walk.js` (`onFloor`) gives an upper
storey a floor only there (houses built earlier keep the old rule); the map in `view.js` draws an upper storey only
where it has a floor, and `walk.roomAt` names the room. `tests/test_storeys.mjs` walks from every outdoor room of
every upper storey in four directions and fails if the walker leaves that storey's height or its rooms; it is in
`tests/run_all.sh`. `tests/test_openings.mjs` asks an opening to be passable only where there is floor on both sides.

## 10. A plan of an upper storey alone is built at its own height (blender/gen.py, web/walk.js, tests/test_storeys.mjs)

Why: a drawing of one upper storey (for example a plan titled SECOND FLOOR) was built on the ground. Its terraces
and lawns became real ground with garden furniture, and the walker named "Second Floor" walked out onto the site.

What: when the lowest storey's title says FIRST, SECOND, THIRD, FOURTH or FIFTH, `gen.py` raises the whole house by
that many storeys (`BASE`), builds a plain block under the outline for the storeys that are not drawn, puts the storey
on a slab with parapets at its open edges, and writes its `floor` to `meta.json`, so `walk.js` (`onFloor`, now keyed
on `floor` alone) keeps the walker on it. `tests/test_storeys.mjs` covers every storey that has a `floor`.

## 11. Any plan opens in the review page: imports, tracing and the page as background (server.py, web/edit.html, edit.js, style.css, tests/test_review.mjs)

Why: a plan reached the review page only when the detector read it; a scan or a drawing in another style ended on
an error. Our backend now reads such PDFs with other readers (an AI plan reader, the floor plan generator's stored
plan), and as a last resort the person traces the walls over the page.

What: `POST /api/upload` with `X-Detect: 0` draws the page images of any PDF (vector or scanned; `render_pages`) and
leaves the job at `uploaded`. `POST /api/jobs/{id}/import` takes `{plan | null, reader, notice}`, checks every value
(types, finite numbers, ranges, list lengths, text without control characters, no hand-placed furniture), writes
`plan.json` afresh and sets `reader` and `notice` in the status (409 while the detector or a build runs; an import and
a build of the same job are serialised by `plan_lock`). `plan: null` makes an empty floor over page 1 for tracing.
A build refuses a plan with no walls. The review page shows the PDF page behind every plan, with a toggle, page
choice and quarter turns; a floor's `bg` (page, rot, pt_per_ft, origin_pt, fit) places a plan that is not in the PDF's
own coordinates, and "Line up drawing" fits it by matching two points. New tools: Draw wall (snapped, the plan's wall
thickness), Add door / window / stairs, Set scale (two points and a typed distance: 12'6", 3.8 m, 380 cm), Undo,
rooms that follow the walls. A notice says which reader made the plan; in embed mode the 'ready' message carries
`reader`, `notice`, `buildable` and `problem`, a new 'buildable' message follows edits, and the page's own notice bar
is hidden. The detector flow, patch 2's messages and patch 6 are unchanged.

## 12. Walls drawn as solid bands (detect.py, vector.py)

Why: presentation drawings, including the PDFs of our own floor plan generator, draw each wall as a solid dark
filled band with no outline pen, colour the room floors, draw door swings as coloured arcs (flattened into many short
lines) and windows as striped bands. The detector looks for walls as pairs of parallel stroked lines, found none, and
the upload ended with "This drawing could not be read".

What: `band_segs` turns the outlines of the dark fills that carry a good share of the dark area into line segments,
which pair up like double-line walls; they are used when they give clearly more wall than the strokes do (1.5 times),
so a CAD drawing is read as before. Solid walls are cut at every door and window, so `opening_links` ties the pieces
of one house together across gaps that hold a door swing or window glass. `close_corners` reaches across a thicker
perpendicular wall; `scale_from_labels` also measures between wall centre lines (generated plans write sizes that
way) and keeps the reading more labels agree on, the clear size on a tie; a door leaf drawn from the hinge of the
neighbouring wall is recognised; an open passage parts the rooms either side of it. `vector.polyline_arc` turns an
arc flattened into a polyline back into a curve. The sample is read exactly as before; OPT 5 and the SF plan keep
their openings and rooms (the SF plan's outer corners now close; four 4-inch stubs on OPT 5's first floor are full
height instead of parapet height). `paranjay-villa.pdf` (generator style): 53 walls, 10 doors, 12 windows, 12 rooms.
