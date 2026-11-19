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

## 24. A door goes through a wall that leaves no room to pass (detect.py)

What: `doors_through` covers the case where a wall parallel to a door's own wall lies within 2 ft of it and covers at
least half the door's width (a doubled line, a chase or a closet front read as a wall). The door's opening is then
extended through that wall, so there is passable space on both sides. A gap wider than 2 ft is a corridor and is left
alone. The SF plan's door 9 was the case: a wall 0.84 ft below it covered 92% of its width. Re-detected and rebuilt,
its openings test passes 82/82 (81/82 before). OPT 5 and paranjay-villa are unchanged (0 of 44 and 0 of 23 openings),
and no other SF opening changes. The stored SF job keeps its old plan until it is read again.

## 25. Source and confidence of every room and opening (checks.py, server.py, web/edit.js, tests/test_confidence.py)

What: `checks.annotate` sets `src` (detector, ai or user) and `conf` (0-1) on each room and opening, and
`wall_src` / `wall_conf` on each floor. Rooms score by how their label matched: exact 0.95, abbreviation 0.8, fuzzy
0.6, unknown 0.3, no label 0.5. An AI-typed room keeps the AI's confidence. Doors score 0.9 with a drawn leaf and 0.65
without; windows 0.8. An AI read is scaled by 0.85. A check about an element caps its score: an unknown label or a
blocked door at 0.3, an area mismatch at 0.5. The rules are fixed and stated here, not learned. Annotation runs on
detection, on import and on every save. On a save, elements without a source become the person's (1.0); the rest keep
their source. The review page shows "Read from the drawing · 72 % sure", and changing an element's type, label or
width makes it the person's. The plan also carries average confidences (`plan.confidence`).

## 26. Low light maps stop at 2048 px (blender/bake.py, server.py)

Where the time goes (dock house, Low, M1 Pro, with nice): model 2.5 s, light-map baking 192 s (93%), glTF export
10 s, 206 s in all. The 4096 px storey map alone took 97 s. With Low maps capped at 2048 px the same build takes 102 s
(-50%). The walkthrough looks the same from inside and outside at the same camera poses (compared side by side). High
keeps 4096. The server's default Low bake rates are now the measured ones (6.5 s per megapixel per storey map, 4 s for
the site).

## 27. Blueprint minimap, bottom left (web/view.js, web/view.html)

What: the map (M) moves to the bottom left and is drawn as a blueprint. It has a deep blue sheet, a grid every metre
(stronger every 5 m), white walls, thin room outlines (dashed outdoors, orange for custom areas), stair treads and a
5 m (or 1 m) scale bar, with lettering in monospace. Water, closed shafts and other large blocked areas are outlined
and hatched rather than filled white, so the pool and the dock show as such. A room name that does not fit is tried
two sizes smaller before it is left out. The orange "you are here" dot, the view cone and the room highlight are as
before.

## 28. Low first, then High (server.py; gateway and frontend)

What: a High build first builds Low into the job folder (status `preview: true`, "Low quality ready to walk through;
building High"), then builds High into `.next/`. Its files replace the preview's only when High succeeds; a failed High
leaves the Low house, marked done at Low. `run_blender` is the single build step both passes use. The gateway passes
`preview` on, and the job page shows the Low walkthrough under the progress bar while High builds. When the build is
done, the walkthrough step loads the finished house in a new frame. Checked on paranjay-villa: preview walkable at
77 s, High swapped in at 594 s with 4096 px maps, and `.next/` removed.

## 29. Furniture models per person (server.py, blender/gen.py; gateway)

What: furniture models are kept per set: `assets/custom/<set>/` and `assets/thumbs/<set>/`, where a set is 16 hex
characters. The furniture API takes `?set=`, a build request takes `furniture_set`, and gen.py takes `--furniture-set`.
With no set, the shared models are used as before. The gateway derives each person's set from their id with the embed
secret, puts it on every furniture request and build itself (any `set` a page sends is replaced), and serves item
pictures from the set's folder. PlanTo3D never sees a user id. Checked live: a model uploaded to set A is listed for A
only (not B, not shared), an invalid set is refused, and a villa built with set A imports it (43 MB house against
11.9 MB). `PLAN3D_ALLOW_FURNITURE_CHANGES` stays false by default: turning it on is the owner's decision.

## 30. A real potted plant; asset manifest with licences (blender/gen.py, fetch_assets.py, tests/test_assets.py)

What: the potted plant is Poly Haven's potted_plant_02 (CC0, 2.6 MB) at about 1.1 m. Before, it was a faceted blob,
which was the problem in docs/reference/issues/. The blob stays only as a fallback when the model is not downloaded.
fetch_assets.py writes `assets/manifest.json` (kind, source, licence, page) for each asset. Sources are allowed only with
a licence that permits redistribution (`SOURCES`, `ALLOWED_LICENCES`). tests/test_assets.py fails if an asset on disk is
missing from the manifest or has another licence: 35 assets, all CC0.

## 31. Kitchen island; the potted plant is lit in real time (furnish.py, blender/lib.py, blender/gen.py)

What: a kitchen gets an island parallel to its main run when the room allows it. The island is 5-8 ft long and 3 ft
deep, with a 3.5 ft working aisle to the run, at least 3 ft free behind it, and no clash with anything already placed.
It has base cabinets, a marble top that overhangs on the stools' side, and three pendant lights. When 2 ft more are
free behind it, counter stools go on that side. On 63 plans (stored jobs and generated plans) 19 of 77 kitchens get an
island, with 0 clashes. The dock house's kitchen was checked by screenshot.
Fix: the Poly Haven plant from §30 turned the whole ground-floor light map black (mean 0.0, against 39.5 without it).
The plant's objects are now marked unbaked and exported with the trees, which the walkthrough lights in real time.
The map is back to 39.9.

## 32. Wall art (furnish.py, blender/lib.py, blender/gen.py)

What: living rooms, bedrooms and dining rooms get one framed colour-field canvas, centred on their longest wall
stretch that has no window or door (at least 4 ft) and 5.3 ft up. It is up to 5 ft wide and never placed behind a
wardrobe, a TV unit, a kitchen run, a desk or anything else tall against that wall. It has a teak frame, a warm ground
and two colour blocks from a fixed six-colour palette, chosen by the room's position so a house always gets the same
pictures. On 64 plans: 637 pictures in 689 such rooms, 0 clashes. Checked by screenshot, over the sofa in the dock
house's living room.

## 33. Recessed downlights (blender/lib.py, blender/gen.py)

What: living, dining, kitchen, bedroom, study, foyer, breakfast, bar and cinema rooms whose shorter side is at least
9 ft get a grid of recessed downlights about 5.5 ft apart (a glowing square in a white trim), in place of the single
central panel. Smaller rooms keep the panel. The bake still uses one area lamp per room, so how bright a room is does
not change. Checked by screenshot in the dock house's living room. The first version's steel trims baked nearly black,
so they are white now.

## 34. The AI's second look stays in Needs checking (server.py, web/edit.js)

What: a save keeps the checks of kind `ai_review` (at most 25) that the 3D gateway's AI second look added (backend
plan3d/verify.py), and works out the rest again as before. These items name a whole plan rather than one room or
opening (`item: ["plan", 0]`). The review page lists them without outlining anything, and clicking one only switches to
its storey.

## 35. Rendered tours: the chunked pipeline, and EEVEE without the blue cast (server.py, blender/cinema.py, tools/tour_cinema.mjs)

What: `POST /api/jobs/{id}/tour {quality: high|ultra, seconds?, res?}` queues a video tour of a built house on the
build queue, so only one Blender job runs at a time. High is EEVEE at 1280x720; Ultra is Cycles at 1920x1080 with 64
samples. `run_tour` turns the guided tour's route into cinema keys (tools/tour_cinema.mjs, which needs Node on the
server), then renders in chunks of about `PLAN3D_TOUR_CHUNK_S` seconds (default 480), sized from the measured time per
frame. Done frames are skipped, so a stopped tour resumes. Chunks are `PLAN3D_TOUR_COOL_S` apart (default 30), ffmpeg
joins the frames into `tour_<quality>.mp4`, and the job lists it under `tours`. Checked live with an 8 s, 480p High
tour: 3 chunks (80, 104 and 13 frames, 2 minutes apart), 197 frames, 6.6 s of video, done in 647 s.
EEVEE lit walls with the whole dusk sky, unoccluded, and turned white plaster blue. The sky's light on surfaces is now
greyed (saturation 0.25) and scaled (0.8), while the camera still sees the sky as it is. A still at the same time now
matches Cycles' light grey wall. Cycles is unchanged.

## 36. A stone plinth on the outer walls (blender/gen.py)

What: the ground storey's full-height walls get a stone base (granite tile) 2.5 ft high and 0.08 ft proud on every outer
face. A face counts as outer when there is no indoor room 1 ft beyond it at three points along it. The base is cut
away where a door or a floor-level opening is. It breaks up the long plain sides that the four-side stills showed
(style_compare/), but it does not replace real facade design: the side walls are still mostly blank.

## 37. The plan verifier (verify.py, checks.py, server.py)

What: pure-code checks with a severity (critical, warning or info) and a location. Rooms that overlap (stairs, lifts
and voids drawn inside another room are allowed) and rooms without a type are critical. Doors that open onto a wall
across their whole width are also critical. Warnings cover windows between two rooms, a stair with nothing above it
on the next storey, upper-storey rooms outside the storey below, and a room total more than 10 % off a stated total.
Wall ends with nothing within 6 ft and rooms closed on fewer than 2 sides are info. The checks from §17 get a severity
too. `checks.all_checks` merges both lists, most severe first, wherever a plan is written. On all 200 generated (true)
plans it raises nothing critical and no warning. On the stored, read plans it finds 9 windows between rooms and 2
overlaps.

## 38. The house is assembled from the asset library (blender/gen.py, furnish.py, web/rooms.json, library/)

What: gen.py reads `library/index.json` (`PLAN3D_LIBRARY=0` turns it off) and places library pieces through the
same fitting as custom models. The order is the person's own model first, then a library piece, then the built-in
builder. A piece only the library has (armchair, console, prayer rug…) is skipped with a log line when the library
is missing. Chandeliers and pendants hang at their own size. meta.json records which piece served how many items
(`kits`). New room types: `prayer` (musalla) and `majlis`. Prayer labels (PRAYER, MUSALLA, مصلى) used to be typed
puja and got a Hindu mandir; now they get a niche on the wall facing the qibla (bearing `PLAN3D_QIBLA_BEARING`,
default 258° for Dubai, turned by the floor's `north_deg`), rugs in rows turned to the qibla, and a Quran stand.
Living, dining, foyer, laundry, gym, cinema and study rooms get the extra pieces where they fit.
Browser models keep metal parts as flat metallic glTF materials, because a colour bake turns metals black.

## 39. Rooms sized to their labels (fit.py, server.py, verify.py)

What: after reading (detector and AI reads; traced and stored plans are taken as drawn), each storey is fitted to its
room labels. First comes the scale: when the labelled rooms agree on one ratio of label to drawing (the median, with
half of them within 3 %), the whole storey is rescaled. Then each room within 10 % of its label is fitted by least
squares. Wall lines are the unknowns, a wall's two faces keep its thickness, a weak pull keeps unlabelled lines where
they were drawn, and everything is remapped piecewise-linearly between lines, so shared walls move together. Rooms
further off are left alone and reported (`size_mismatch`), and a plan with an assumed scale gets a critical
`scale_unknown` item asking for one known length. On the 24 held-out vector plans, labelled rooms within 2 % of their
label went from 172/316 to 217/316 (54 % to 69 %). The room area error against the truth went from 43.4 % to 42.4 %;
it is dominated by rooms the reader merged or split, which no size fit can mend. On stored plans: OPT 5 went from 9 to
11 of 14, the villa from 1 to 8 of 9, SF stayed at 6 of 8 (mean 2.1 % to 1.6 %).

## 40. Walkthrough: go to any room, and measure (web/view.js, web/view.html)

What: a "Go to a room" list with every room on every storey. Choosing one puts the walker on the walkable spot nearest
the room's middle, facing it. A Measure button: two clicks on any surface (or G at the crosshair while walking) draw
a line and show the distance and its horizontal part in metres. `window.__measure` is there for tests. Checked
headless on the dock house: 30 rooms listed, a jump to BREAKFAST AREA, a 4.10 m measurement.
Not done: hiding furniture (it is baked into each storey's mesh, so it would need its own bake group).

## 41. Does the drawing support a line? (server.py: POST /api/jobs/{id}/support)

What: for proposed wall centre lines in plan feet (from the AI gap-filler), the share of 20 points along each where
the PDF shows a wall. A point counts when a thin, wall-shaped fill covers it (floor fills cover whole rooms and do not
count), or when pen strokes run the same way on both sides of it within 0.75 of the wall thickness. Measured on the
stored vector plans: 20 of 32 real long walls score 0.6 or more, and 0 of 25 made-up lines across rooms do. A line
the drawing does not support is never built; the gateway turns it into a suggestion. Scans have no pen strokes, so
there every AI wall is a suggestion.

## 42. Spiral stairs, lift landings, and metals that bake right (detect.py, blender/gen.py, blender/lib.py, blender/bake.py)

What: a stair with a SPIRAL, CIRCULAR or HELICAL label on it or within 6 ft of it is marked `shape: "spiral"`; the
review page can set it too. It is built as wedge treads round a steel column inside the stair's footprint, climbing
the storey height in 0.85 of a turn, with a helical handrail, and the floor above opens over its whole footprint. The
walker still climbs along the stair's rectangle. A lift gets a brushed-steel landing door on every storey, on the side
facing a walkable neighbour, with a lintel and a call panel with a lit button, plus a cabin standing in the shaft on
the lowest storey. The shaft stays closed to the walker.
Bake: metal surfaces have no diffuse light, so they baked black and showed black in the walkthrough (the built-in
steel and chrome as well as library pieces). Materials are baked as non-metal and their metalness is put back after
the bake. Checked by screenshot on a generated two-storey plan with a spiral stair and a lift.
Not done: circular rooms. The readers do not find curved walls yet, so nothing would produce one.

## 43. Review page: a checklist with severities, room names and sizes, typed sizes, spiral stairs (web/edit.js, style.css)

What: "Needs checking" is sorted by severity, with a badge and a count ("5 to check · 1 critical"). Each item has Fix
(go to it) and Dismiss (kept in `plan.dismissed` and saved with the plan). Build stays off while a critical item is
open; the scale item counts as done as soon as a scale is set. Every room shows its name (its label without the size)
and its built size in feet and inches. A one-rectangle room's width and depth can be typed: the plan stretches along
the room's far edge, so walls, openings, rooms and stairs past it move too and shared walls stay shared. Stairs get a
"Spiral stair" checkbox. tests/test_review.mjs passes (it caught the scale item blocking a freshly traced plan).
Not done from Stage 6: a rebuild in the frontend's own style, a live 3D preview of the shell, autosave, split and
merge of rooms, and a phone layout.

## 44. The creator agent's Blender sessions, the asset review page, and a shared browser bake (server.py, library/build/, web/library.html, blender/gen.py)

What: `POST /api/creator/start` opens a Blender worker (`library/build/creator_worker.py`) in its own folder under
`jobs/.creator/`, with an empty environment (no secrets, no network use), a 10-minute limit and a triangle budget.
The worker knows only fixed operations (boxes, cylinders, lathes, rods, materials from the style, small lights,
transform, delete, scene listing, a 640 px preview, export); there is no code evaluation and every file it writes has a
fixed name in its folder. `POST /api/creator/{id}/op` forwards one operation; a preview comes back with the image, so
the agent can look at it. `/finish` checks the asset fits the area (2% + 5 cm), stands on the floor and has its
preview, .blend and .glb, then adds it to `library/creator/<area>/` as **unreviewed**, with its prompt, cost, turns and
model. `web/library.html` lists the library with previews; Approve and Reject (`/api/library/<dir>/<id>/review`) work
only in developer mode. Builds (gen.py) use AI-made assets once approved, or with `PLAN3D_USE_UNREVIEWED`; a
`custom` area whose `area_type` names a creator asset gets that asset fitted to it. The browser bake moved from
make_library.py to `browser_bake.py`, shared by both (it also zeroes metalness during the colour bake).
Measured: a scripted (no model) helipad session ran in 4.6 s (1476 triangles, preview checked by eye); an oversized
asset was refused with "6.00 x 6.00 x 0.20 m does not fit the area (4.00 x 4.00 x 1.00 m)".

## 45. Scale: label rays across openings, and 9" outer walls (detect.py); scorer: openings neutral (tools/score_plan.py)

What: a ray from a room-size label that finds no wall (it went through a door or window gap) now looks for the
nearest wall running the right way within 8 wall thicknesses either side. With no measurable label, the main wall is
taken as 9" (not 4.5") when 15 % or more of the wall length is about half as thick. The scorer now leaves wall
samples inside a door or window opening (either plan's) out of both counts.
Measured (held-out generated plans, readers only, openings neutral): wall recall fills 56 -> 98 %, lines 63 -> 100 %,
solid 50 -> 84 %, hatched 34 -> 64 %; precision fills 62 -> 97 %, lines 66 -> 99 %, solid 63 -> 83 %, hatched 45 ->
74 %. Before, 10 of 24 vector plans were read at twice the true scale. Reference plans: the two vector ones read the
same walls and rooms as before (scale moved 0.03 %).

## 46. Scale: each label axis votes; agreeing labels choose between clear and centre-line sizes (detect.py)

What: a label whose width and depth agree is two votes, a single axis half a vote per orientation (a missed
partition spoils the width ray, not the depth). Between the clear and the centre-line readings: more labels that agree
with each other, then 1.5x the support, then the reading nearer the scale from the wall thickness.
tests/test_scale.py (synthetic walls; fails on the detector before §45).
Measured on the 150 tuning plans, which were not looked at for §45-46 (vector, readers only, openings neutral): wall
recall fills 35 -> 93 %, hatched 49 -> 99 %, lines 47 -> 92 %, solid 34 -> 91 %; precision 44 -> 92, 56 -> 98,
62 -> 95, 42 -> 96 %. Held-out vector plans: 100 % recall, 99 % precision in every style (but §45-46 were found on
held-out plans, so the tuning set is the clean measure). Reference plans: same walls and rooms as before.

## 47. Scale convention by agreeing labels; nearest wall beside a gap; the size fit measures between walls (detect.py, fit.py)

What: detect.py chooses the clear or centre-line reading of the size labels by how many labels agree at its scale,
then how tightly; a label ray takes the nearest of the walls on its line and the right-way walls within the band (a
ray through a door no longer keeps the next room's wall); rooms carry `label_at` (plan feet). fit.py chooses one size
convention per storey, adds each bounding wall's own half thickness for centre-line sizes, rescales only beyond 1.5 %,
and measures rooms between the walls from `label_at` (a reader's room rectangle can span two rooms). tests/test_fit.py
adds a case (a room rectangle spanning two rooms moves no wall; it also passes on the old fit, so it guards rather
than reproduces: the measured regression is on generated plans).
Measured, tuning set (not looked at), vector wall recall / precision: fills 100/99, hatched 97/96, lines 100/98,
solid 100/99 %. Labelled rooms within 2 % of their label: about 20 % -> 89 %. Before this, with the scale right, the
size fit lowered held-out recall to 70-86 %; now it changes nothing on correct readings. Reference plans: same walls
and rooms; OPT 5's scale moved 0.24 % (no ground truth to say which is closer).

## 48. Shared walkthroughs view only (web/view.js)

What: a walkthrough opened from a share link (`&shared`, made by the gateway's POST /api/v1/3d/jobs/{id}/share) has no
Record, Blender file or Home button and ignores the R key: the share token reaches only the files the walkthrough
loads (meta.json, house.glb, lm_*.webp, tour_*.mp4, the page's scripts), so those would fail. The gateway checks the
job's current share id on every request; revoking or making a new link ends older links at once (410).

## 49. The Blender queue has lanes (server.py)

What: a priority queue with a fast lane (Low builds, the Low step of a High build) and a heavy lane (High bakes,
tours); fast work never waits behind queued heavy work. A High build now runs its Low step, then queues the High bake
in the heavy lane, so another person's Low build can run between them. PLAN3D_BLENDER_SLOTS builder threads (default
1). tests/test_lanes.py (Blender stubbed) checks the order. Not done: a warm Blender between jobs (gen.py builds into
one scene per process).

## 50. Water reads as water by day and evening; a day preset; creator previews in both (library/build/)

What: style.py's "Water" now has a body colour (deep green-teal #1c4643 for ponds and fountains), "PoolWater" a
brighter one (#3f9db0, pools over pale tile), and the handover's near-black mirror is kept as "MirrorWater" for hero
shots across water. The browser bake exports water as a flat glossy material in its colour (a colour bake turned it
black). `style.day_sky` is a day preset (pale sky gradient and a sun lamp). The creator worker's render_preview renders
evening (preview.png) and day (preview_day.png); the agent sees both, and its prompt asks that water read as water in
both. Checked by re-rendering the koi pond: its water was black in both presets and is now clearly water in both
(docs/run3/creator/, git-ignored); the library's koi pond asset was updated (new water, both previews, rebaked .glb).
Note: the day preset still looks overcast (soft sun shadows); the house builder's day lighting is Stage 9 work.

## 51. North arrow, sun from it, day and evening light maps, exterior lighting (detect.py, blender/, web/view.js)

What: detect.py reads a north arrow (a lone N or NORTH with strokes, fills and curves around it): the symbol is
symmetric about its north axis with the letter on it, so the axis is the line through the letter that mirrors the
nearby strokes best; the body lies behind the letter. Each storey gets `north_deg` (clockwise from up the page),
which imported plans keep too. gen.py aims the day sun from PLAN3D_SUN_BEARING (225) turned by north_deg, and bakes a
second set of light maps for the evening (bake.py variants): the sky darkened to deep blue, a low warm sun from the
west, lamps up 40 %, and warm wall-washers on the ground around the house about every 4 m (exterior lighting, off by
day). meta: lightmaps_evening, lightmap_max_evening, north_deg, sun_bearing. The walkthrough has a Day / Evening
button that loads the evening maps on first use and dims the live light on unbaked trees.
Measured: tests/test_north.py (arrows at 0-315 degrees, a dart with a stray tick, no arrow) passes; on the two vector
reference plans the reader gives 90.5 (a compass rose pointing right) and 0 (an arrow straight up), checked by eye
(the first version gave 14.9 on the second: it averaged stray strokes). The dock house's Low build took 199 s
against 111 s without the evening maps. Not done: the evening interior differs little from the day one (the lamps
dominate both); a darker interior would need the lamps' day level lowered, which changes the day look.

## 52. The verifier finds a wall close behind a door (verify.py)

What: door_no_way tried only a point 1.5 ft beyond each side of a door; a wall closer than that was missed. It now
tries every quarter foot from 0.25 to 1.5 ft. Found by the full suite: on job 0bdaca14d7bf (a reading from before this
run) a door opens onto a parallel wall 0.84 ft behind it, which test_openings reports (the walker cannot pass) and the
verifier did not; it is now a critical item, so Build stays off on the review page until it is fixed or dismissed.
tests/test_verify.py: still no warning on the 200 true plans.
