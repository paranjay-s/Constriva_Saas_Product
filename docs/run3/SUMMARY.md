# Run 3 summary (updated at the end of every stage)

Branch `feat/run3` from `feat/3d-night`; nothing pushed. Every task with its commit: LOG.md.
Hardware: Apple M1 Pro, 32 GB, 14-core GPU (Metal), macOS 27.0.1, Blender 5.3.0.
The run started on battery (35 %, discharging): no renders until it was charging again, as the rules require.

## Stage 0: the style handover
- **Reproduction:** `build.py` (bedroom, 26 samples) in a fresh Blender process took 56 s here, against 136 s on the
  handover's CPU. Against the delivered render the PSNR is 49.4 dB, with a mean difference of 0.37/255 and 0.17 % of
  pixels more than 8/255 off. The difference is only sampling noise on edges, the lattice and the leaves.
  stage0/README.md has the details and the image diff path.
- **Inventory:** style_inventory.md lists all 50 lights, 15 emitters and 68 materials with their builders, plus the
  generators, colour management, post-processing and tour.
- **Ported** to `services/planto3d/library/build/style.py`, with the handover's values as defaults: the stone tiles
  (Limestone, DarkStone), floor slabs, plaster, ceiling, concrete, walnut and oak, floor planks and deck, glass,
  fluted glass, brass, bronze and other metals, the fabrics (linen, clay, sage, charcoal, rug, towel), leather,
  curtain, ceramics, the jaali screen, water, leaves, gravel, every emitter (Cove 3100 K/34, Downlight 3000 K/30, Bulb
  2700 K/120, Shade, Lantern, MirrorRing) and art canvases. Also the room light (hidden from camera and glossy, with a
  visible disc), the wall washer (spot 62°, 3 cm), coves, a downlight grid, AgX Medium High Contrast with per-shot
  exposure and white balance, the handover's Cycles settings, an evening sky gradient, and the shape helpers (box,
  soft box, lathe, rod, disc, pillow, pleated curtain, potted plant with a leaf count for render or browser detail).
- **Added:** beige limestone, three marbles, large-format porcelain, terrazzo, outdoor stone, grass, velvet, white
  lacquer and pool tile.
- **Not ported yet:** the full sunset sky with its warm western band and the hills; the recursive olive tree and the
  palm (the library uses a simple potted crown); `post.py` (bloom, S-curve, vignette, grain, sharpening); and the
  still-plus-depth tour (Stage 10).

## Stage 1: the library (partial)
- 44 pieces: sofa, armchair, coffee and side tables, floor and table lamps, TV unit, rug, plant, dining set for 6 to
  10, sideboard, pendant cluster, bed, nightstand, wardrobe, dresser, desk, WC, vanity with a mirror halo, shower with
  fluted glass, bathtub, towel rail, fridge, oven and microwave tower, dishwasher, coffee machine, washer, dryer,
  mandir, puja mat, prayer rug, prayer niche, Quran stand, majlis seating, incense burner, chandelier, console, shoe
  cabinet, bookshelf, treadmill, weight bench, cinema seats, lounger, outdoor sofa and planter.
- Each piece has a detailed .blend (live procedural materials), a browser .glb (colours baked to a 1024 px atlas,
  metals and glow as flat glTF materials, Draco), a 1280 px preview and an index entry. All 44 build in about
  5.5 minutes.
- Contact sheet: `docs/run3/library/contact_sheet.png` (git-ignored).
- Index: `services/planto3d/library/index.json`. The `asset_library` table migration is written, not applied.
- The house is now assembled from these pieces (§38). Prayer rooms are no longer furnished as puja rooms.
- Parametric: spiral stairs (marked by label or the review page's checkbox), lift landing doors, call panels and
  cabin (§42). A metals-black bug in the house's light bake was fixed for every build (metalness is zeroed during
  the colour bake). **Not done:** circular rooms and curved walls (no reader finds curved walls yet), any-polygon room
  shells, pool/dock/exterior kits in the new style, the library tests (polygon budgets, clash-free placement in rooms
  of 6-80 m², determinism), a daylight preset, LOD foliage.

## Stage 2: readers (not done)
The scanned reader (OpenCV + OCR) and a reader router were not started this run. The existing vector reader,
AI plan reader and tracing fallbacks are unchanged.

## Stage 3: AI gap-filler (done, off by default)
One cached call per plan (`gapfill.py`, prompt `gapfill_v1.md`, fixed schema) fills names, types and legends. Walls
are added only where the drawing backs them (PlanTo3D `/support`: strokes on both faces, thin fills); everything
else becomes a suggestion in "Needs checking". On the drawing check, 20 of 32 real walls were supported and 0 of 25
made-up lines. Live test: with hints of the drawing's unused labels, the model proposed the lobby walls and doors,
which became 4 suggestions. Switch: `PLAN3D_AI_GAPFILL`.

## Stage 4: verifier (done)
`services/planto3d/verify.py`, pure code with severities (critical, warning, info): overlaps, open rooms, dangling
walls, doors that lead nowhere, windows inside the house, stairs without direction or landing, overhangs, area
totals, size mismatches, unknown scale. 0 warnings on 200 true generated plans.

## Stage 5: dimensions (partial)
`fit.py` fits wall lines to the printed room sizes by least squares and reports the rest. Stage 11 found it was
damaging plans once the scale was right and repaired it (one size convention per storey, each wall's own thickness,
rooms measured between walls from where the name is written). With the scale fixes, labelled rooms within 2 % of
their label: about 20 % -> 89 % (generated plans), 44-56 % on the two real vector drawings. **Not done:** dimension
lines, the AI scale estimate for undimensioned plans, the ceiling-height control. The target of every room within
2 % is not met.

## Stage 6: review page (partial)
Severity checklist with Fix and Dismiss and a count; critical items keep Build off; room names and ft-in sizes on
the plan; typed room sizes; spiral checkbox (§43). Screenshots: `docs/run3/review/`. **Not done:** rebuild in the
frontend's style, live 3D shell preview, autosave, split and merge, phone layout.

## Stage 7: assembly (partial)
Rooms are furnished from the library kits and the kit used for each room is recorded in the build's meta. A palette
(four warm-villa schemes) is chosen from a hash of the plan's walls and rooms (PLAN3D_STYLE overrides) and recorded in
meta; checked with one Low build (predicted "sand", built "sand", wall and exterior colours in the .blend match).
The schemes are deliberately close; the exterior and wood tints differ most.

## Stage 8: creator agent (done, off by default)
- `backend/app/modules/plan3d/creator.py`: a Messages API tool loop (claude-opus-5-5, medium effort, server-side
  fallbacks) with 11 client tools. Each call goes to a Blender worker on PlanTo3D that knows only fixed operations,
  runs in its own folder with an empty environment, a 10-minute limit and a triangle budget. The API key never
  leaves the gateway. Blender MCP was not used: a closed operation set is easier to sandbox than a general MCP server.
- Validation: fits the area, stands on the floor, preview + .blend + .glb present. Saved as **unreviewed** with its
  prompt, cost, turns and model; builds use it only after approval or with `PLAN3D_USE_UNREVIEWED`.
- Admin page: `web/library.html` (approve and reject in developer mode). Gateway endpoint `POST /api/v1/3d/creator`
  needs `PLAN3D_CREATOR_AGENT` and a user id in `PLAN3D_CREATOR_ADMINS`.
- **What it made:** for an invented area, "koi pond with deck" (6 × 4 m), the live agent built a sunken pond with a
  stone edge, a timber deck with a step, two lanterns, koi, lily pads and corner planting in 4 calls, 67 s and $0.29;
  1,886 triangles, 6.00 × 4.00 × 0.85 m. Preview: `docs/run3/creator/koi_pond_preview.png`. Its water was black in
  both presets; fixed (§50). A scripted helipad tested the pipeline without a model.

## Stage 9: Blender service and lighting (partial)
- Queue lanes (§49): Low builds and the Low step of a High build run before queued High bakes and tours;
  PLAN3D_BLENDER_SLOTS. Tested with Blender stubbed. A warm Blender between jobs: not built (3-5 s start-up).
- North arrow (§51): read by mirror symmetry of the symbol about its axis; checked on both vector reference drawings
  by eye (90.5 and 0 degrees). The day sun comes from PLAN3D_SUN_BEARING turned by it.
- Evening light maps with warm exterior wall-washers (§51): Low build 111 -> 199 s. Dockerfile and docs/deploy-3d.md
  exist but were never built (no Docker here).

## Stage 10: walkthrough (partial)
- Done: room list and measure tool, Day / Evening switch, a revocable view-only share link (gateway, migration
  written not applied, frontend button; §48), build emails (earlier run). Floor switcher already existed.
- Skipped: furniture on/off (furniture is baked into the storey mesh).
- Tour evaluation (`docs/run3/tour/README.md`): same house and cameras, EEVEE 4-6 s a frame and flat grey, Cycles
  31-34 s a still with warm bounce light. For a 421-frame tour, about 35 min (EEVEE) against about 6-7 min estimated
  for still-plus-depth. The warp was not built, so its artefacts are not measured. Recommendation in the file.

## Stage 11: accuracy (done for vector; raster classified)
Full tables: `docs/run3/accuracy.md`. All numbers below are walls scored centre line against centre line, with
door and window spans neutral (scorer fix: the truth stops walls at openings, the readers run them through).
- **Scorer fix** (same readings): overall precision 45 -> 48 %, recall 50 -> 49 %; vector moved about 1 point.
- **Vector fixes** (detect.py §45-47, fit.py): 10 of 24 held-out vector plans had been read at twice the true scale
  (label rays through door gaps found no wall, and the fallback took the 9" outer wall for a 4.5" one). Then: per-axis
  label votes, the size convention chosen by agreeing labels, and the nearest wall beside a gap.
- **Clean check** (150 tuning plans, not looked at during the fixes; vector, readers only):

| style | wall recall before -> after | wall precision before -> after |
|---|---|---|
| fills | 35 -> 100 % | 44 -> 99 % |
| hatched | 49 -> 97 % | 56 -> 96 % |
| lines | 47 -> 100 % | 62 -> 98 % |
| solid | 34 -> 100 % | 42 -> 99 % |

  Held-out vector plans: 100 % recall, 99 % precision, but the fixes were found on held-out plans, so the tuning set
  is the honest figure. Labelled rooms within 2 % of their label: about 20 % -> 89 % (Stage 5 target of 100 % not met).
- **Size fit:** once the scale was right it was damaging plans (held-out recall 100 -> 70-86 %); repaired (one
  convention per storey, real wall thicknesses, measured between walls). It now leaves correct readings alone.
- **Raster** (26 AI reads, unchanged by these fixes): recall 28-58 %, precision 23-48 % by style. Mostly wall-by-wall
  position error of the AI reader, plus a ~1.1 ft plan-wide shift on solid walls. Fix: a deterministic scanned reader
  (Stage 2, not done).
- **Reference plans** (no truth, nothing tuned): the 2 vector ones read the same walls and rooms throughout; 44-56 % of
  their labelled rooms within 2 %. The 5 scanned ones go to the AI reader, which does not carry label sizes, so the
  size fit cannot act on them.

## Your five follow-ups (in the order you gave them)
1. Scorer bias fixed (openings neutral on both sides): same readings, precision 45 -> 48 %, recall 50 -> 49 %.
2. Vector causes found with overlays and `tools/testplans/causes.py`; four general fixes (§45-47); clean tuning-set
   numbers in the Stage 11 table. Raster plans: classified, not fixed (AI reader position error).
3. Size-fit pass and reference PDFs: run; the size fit was repaired; the reference results are in accuracy.md.
4. Palette: one Low build, matches the prediction (Stage 7).
5. Creator water: now reads as water by day and evening; the koi pond was updated (§50).

## Screenshots (`docs/run3/`, all git-ignored)
- Review page: `review/review_villa.png`, `review/review_opt5.png`, `review/review_opt5_phone.png`.
- Rooms: `rooms/rooms_grid.png`: living, kitchen, bedroom, bathroom, dock, puja, spiral stair, from Low builds.
  What it shows plainly: kitchen, bedroom and dock read well; the spiral stair turns round its pole; the puja room
  (13'6" x 14') is nearly empty (a small piece in one corner): under-furnished. The pool jump and the lift jump did not
  reach their rooms (the walker will not stand in water; the lift entry lands at the stair), so there is no pool or
  lift-cabin view; the bathroom shot faces a tiled wall.
- Not made: a prayer room and a circular room (no built house has one; nothing reads curved walls), master bedroom
  (no room so named in the built houses), and the side-by-side with the reference photos in docs/reference/rooms/
  (left for you: I did not copy reference images anywhere).
- Also: `palette/`, `lighting/` (day and evening), `creator/` (helipad, koi pond, water before/after, admin page),
  `library/contact_sheet.png`, `tour/eevee_vs_cycles_interiors.png`, `accuracy_overlays/` (ten worst plans).

## Timings and hardware
Apple M1 Pro, 32 GB, Metal GPU, Blender 5.3.0. Low build of the dock house: 111 s (199 s with evening maps); puja
house 188 s; two-storey spiral/lift house 275 s. Library: 44 pieces in about 5.5 min. Creator agent: koi pond in 67 s,
4 calls, $0.29. Full backend suite 4 min. Render time this run: about 65 minutes in all (limit 3 h), with
cooldowns; renders paused while the laptop ran on battery.

## What is inaccurate, not verified, or yours to decide
- **Inaccurate:** scanned (raster) plans: wall recall 28-58 %, precision 23-48 % (AI reader position error; needs the
  Stage 2 scanned reader). Real CAD drawings: 44-56 % of labelled rooms within 2 %. Room segmentation on real
  drawings (the villa's LOBBY and BATH). The puja room is under-furnished. The day preset looks overcast.
- **Not verified:** the Docker image; the still-plus-depth warp; the share link and the creator endpoint against a
  real database (the migrations are written, not applied); the evening interior differs little from the day one.
- **Known failure in the suite:** test_openings on job 0bdaca14d7bf (a reading from before this run with a door onto a
  wall 0.84 ft behind it; the verifier now marks it critical). test_tour on cb07bf88a61e is reported, not required.
- **Yours to decide:** (1) apply the two migrations (asset_library, plan3d_jobs.share_id); (2) whether to build the
  still-plus-depth tour for High (shorter render, better light, but short dollies with dissolves); (3) turning on
  PLAN3D_CREATOR_AGENT and listing admins; approving or rejecting the helipad and koi pond in the library page;
  (4) PLAN3D_SUN_BEARING for your region (225 assumes north of the tropics); (5) whether the evening maps' extra
  ~90 s per Low build is worth it (PLAN3D_EVENING=0 turns them off); (6) Stage 2 (a deterministic scanned reader)
  is the biggest accuracy gap left.

## Running totals
Live AI calls: 32 of 80. Render time: about 65 minutes. Free disk: about 297 GB.
