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

## 13. Drawings nested in forms, other SVG writers, metric and area labels (vector.py, detect.py, tests/test_reader.py)

Why: PDFs from other programs draw the plan inside a form or transparency group (poppler hands it over as `<use>`),
inside clip paths, or with transforms other than one `matrix()`; `vector.read_page` skipped `<use>` and stopped at any
other transform. Size labels in metres, centimetres or millimetres (4.20 x 3.60 m, 420X360, 4200 x 3600) and room
areas (15.1 m², 163 sq.ft) gave no scale, so the plan fell back to an assumed scale.

What: `read_page` follows `<use>` references (not glyphs: text comes from pdftotext), applies rectangular clip paths
(`_clip_seg`), reads every SVG transform (`_matrix`: matrix, translate, scale, rotate, skewX, skewY) and relative,
H, V and Q path commands, and keeps what it read of a truncated path. `parse_size` reads metric sizes, with or
without a unit; `scale_from_labels` settles unmarked units by the main wall's thickness (4 to 19 inches) and, with no
size label at all, takes the scale from two or more agreeing room areas (`parse_area`). `tests/test_reader.py` writes
the sample in eleven ways and reads each (in `tests/run_all.sh`). Known limit: a sheet that reads sideways (page
/Rotate 90 or 180, or drawn turned) is read as it lies: every wall, opening and room is found, but the house is a
quarter turn round and a sideways title is not found, so the floor is named "Floor 0". The sample, OPT 5, the SF plan
and paranjay-villa.pdf are read exactly as before.

## 14. Reference plans and a scorecard, for developers (server.py, web/edit.html, edit.js, tools/score_plan.py)

Why: accuracy has to be measured against plans corrected by hand before readers are changed.

What: with `PLAN3D_TRUTH_DIR` set (`scripts/run_planto3d.sh --dev` sets it to `docs/reference/truth/`, which git
ignores), `GET /api/system` says `truth: true`, the standalone review page shows "Save as reference", and
`POST /api/jobs/{id}/reference` writes the plan as `<drawing name>.json` there. Without the setting the endpoint is a
404 and the button stays hidden; it is never shown in embed mode. `tools/score_plan.py detected.json reference.json`
reports wall length recall and precision (within 0.15 m, parallel), doors and windows found (same type, centre within
0.5 m), room type accuracy and room area error, per floor.

## 15. One room vocabulary; new room types, water and more cars (web/rooms.json, rooms.py, detect.py, furnish.py, blender/gen.py, web/edit.js, tests/test_rooms.py)

Why: room types lived in five places (detect.py, furnish.py, gen.py, edit.js and our backend's converter) with a short
keyword list each. Labels such as SERVICE LIFT, BAR AREA, ENTRANCE FOYER, BREAKFAST AREA, SHOW KITCHEN, COLD STORE,
DOCK FOR YACHT or SWIMMING POOL either matched nothing and fell back silently to a type guessed from where the room
was (a pool became a garden, a dock a balcony) or matched the wrong word.

What: `web/rooms.json` holds every type (label, kind, floor material, map colour, furniture rule) and the phrases,
abbreviations and Arabic labels that name it; `rooms.classify` matches whole words, longest phrase first (SERVICE LIFT
before LIFT), then abbreviations, then near spellings, and returns nothing rather than guess. New types: breakfast,
bar, foyer, gym, cinema, lift, pool, water, dock, and multipurpose (an unknown label, built unfurnished and flagged).
Guest, maid's and driver's rooms are bedrooms; show, dirty and wet kitchens are kitchens; cold and hot stores and
pantries are stores; majlis and family living are living rooms; terraces are balconies; garages and car porches are
parking. `furnish.py` has rules for breakfast (small table), bar (counter), foyer (console and plant, no bed), store
(shelving), gym (mat) and cinema (sofa facing a screen), and fills a garage with as many cars as fit side by side.
`gen.py` takes floor materials, ceilings and open-to-sky rooms from the file; builds a pool as a basin sunk 4.5 ft
with tile lining, coping, steps and a water plane (a raised basin on an upper storey), a water body or fountain as a
shallow basin, and a dock as water with a plank deck on posts along its long sides; and closes water (except the dock
decks) and lift and duct shafts to the walker. The review page lists every type by name. `tests/test_rooms.py`: 202
labels. The four vector test plans are read exactly as before.

## 16. Open plans: one function per zone and passages between zones (furnish.py, rooms.py, tests/test_openplan.py)

Why: in an open plan (kitchen, dining and living in one space, read as zones side by side with no wall between them)
the furniture of neighbouring zones crowded together, and every dining zone of more than 150 sq ft also got a sofa
group (the rule meant for "DRG./DIN." rooms), next to the living zone's own.

What: a dining room gets a sofa group only when its label also names a living room (`rooms.names`). Along an open
edge between two indoor zones (at least 4 ft long, no wall, no window, no door) each zone keeps a 1.5 ft strip clear,
so neighbouring zones leave 0.9 m between their furniture. Rooms with walls, outdoor rooms and doorways are not
affected; on the test plans the only change is one fridge in OPT 5's first-floor kitchen, which opens onto the dining
room. `tests/test_openplan.py` (in `run_all.sh`): every zone furnished, no overlaps, no second sofa group, 0.9 m
between zones, every zone reachable from the door. Not done: an island or peninsula facing the other zones, and
dragging zone cuts on the review page (a zone's type can be changed there, as for any room).

## 17. "Needs checking" on the review page (checks.py, server.py, rooms.py, web/edit.html, edit.js, style.css)

Why: a person should see, before the first build, what the readers were unsure of.

What: whenever plan.json is written (detection, import, save) the server adds `checks`: rooms with a label no rule
knows, labels that name two or more functions (read as whole phrases, longest first: `rooms.functions`), doors with no
room on either side (or, on an upper storey, on one side), rooms whose area is more than 10 % off the size in their
label (as a clear size or as a size between wall centre lines), and unlabelled indoor spaces over 150 sq ft. The review
page lists them under "Needs checking" with the rooms and doors outlined in orange; a click selects the item, and the
list is refreshed after every save. Not done yet: possible missed walls (no wall-band tracing inside PlanTo3D) and a
per-element source and confidence (the plan records its reader as a whole).

## 18. Pieces of one wall line belong to one plan (detect.py)

Why: where doors and windows are drawn with a different pen from the walls, the wall faces stop at every opening,
and the pieces between two openings touched no other wall: the plan fell apart into many small wall groups and only
the largest one with two room names became the floor, so most interior walls and doors were lost (measured on
generated test plans: tools/testplans).

What: wall groups whose walls lie in the same band end to end across a gap of at most 14 wall thicknesses (a door or a
window) are merged (`same_line`), unless both groups already hold a plan's room names (two storeys drawn side by
side). Held-out generated plans, vector styles: wall recall 21-40 % -> 35-63 %, doors found 2-14 % -> 58-75 %. The
sample, OPT 5, the SF plan and paranjay-villa.pdf are read as before.

## 19. Area specs, guided tour, fresh embed tokens, time left from light maps (areaspec.py, server.py, web/tour.js, view.js, view.html, edit.js, blender/gen.py, blender/bake.py)

What:
- Area library: `areaspec.py` validates specs for areas no builder knows (helipad, koi pond...): a fixed schema of
  surface, edge, height, walkable, markings and objects. `GET /api/areas` lists them and `POST /api/areas` adds one, but only
  after validation. A room of type "custom" is built from its spec, and a refused or missing spec builds a generic zone.
- Walkthrough: a "Guided tour" button walks the route from `tour.js` at 1 m/s with eased turns and pauses. Any
  movement key, mouse button or touch takes control back.
- Embedded pages (edit.js, view.js) take a fresh token posted by the framing page (`{source:'planto3d-host',
  type:'token', base}`, checked against the parent window and the path pattern) and swap it into their own address
  without reloading.
- Before the first bake, `bake.py` prints `MAPS name=size ...`. The server then estimates the build from the light
  maps' megapixels (`maps_estimate`) and corrects the factor after each finished build (`jobs/.eta_calibration.json`).
  Checked against builds on this M1 Pro: the sample (Low and Medium) and OPT 5 (Low) are within 5%. The dock and pool
  houses are 33-52% over, with their map sizes estimated, not read; the calibration corrects the factor.

## 20. Raised areas can be walked on; the tour reaches areas far out on the site (blender/gen.py, web/walk.js, web/tour.js)

What: a walkable custom area that is raised (a helipad 0.3 m high) is written to meta.json as a floor `platform`
(rect and top height). `walk.heights` stands the walker on it instead of on the floor under it (on a one-storey plan
as well: the closed-stairs rule does not apply to platforms). The tour's grid covers every room's rects, not only the
house bounds plus 6 m. Checked on a generated plan with five AI-specified areas (helipad, koi pond, putting green,
archery range, horse stable): the walker steps up onto the helipad (0.306 m), is kept out of the recessed koi pond,
and the tour visits 14 of 14 rooms and areas (11 before the grid change). No stored job's tour changed.

## 21. The tour starts at the real front door and jumps to parts it cannot walk to (web/tour.js, web/view.js, tests/test_tour.mjs)

What: the front door is a door whose side without a room lies beyond the house's bounds, and of those the lowest. Before,
it was the first door with a room on only one side, which could open on an unlabelled inner hall or court. When the
remaining rooms cannot be walked to from where the tour is (a wing reached only through a closed court, or a door the
reader missed), the route jumps to the nearest of them (`jump: true`), and the Guided tour moves the walker there at
once. The test allows at most one jump per three rooms and does not walk a leg that ends in a jump. On the 8 stored jobs,
unvisited rooms went from 19 / 23 / 1 / 1 to 0, with 0-4 jumps per plan (dock house 4, 25f602b2a296 4).

## 22. Room types "court" and "custom" (web/rooms.json)

What: "court" (outdoor) covers tennis, padel, basketball, badminton and volleyball courts, in English and Arabic.
"COURT" alone and "LANDSCAPE COURT" stay a garden (a courtyard). "custom" (outdoor, orange on the maps) is given only
by the backend's AI classifier, for areas built from an area spec. The review page and the import accept both. The
room label test still passes 209/209.

## 23. The tour climbs from any part; stair records without words build (web/tour.js, blender/gen.py)

What: when the stairs cannot be walked to from where the tour is, it jumps to their foot instead of ending on the
ground floor. `stair_parts` reads a flight's `words` with `.get`, as the line before it did; plans imported through
the server always have them, but plans written by other tools may not. Checked on 20 generated plans of 1 to 3
storeys (model-only builds, 9-14 s each) and 8 stored jobs: 28 of 28 pass tests/test_tour.mjs.
