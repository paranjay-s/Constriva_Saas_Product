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
`fit.py` fits wall lines to the printed room sizes by least squares (wall thickness weighted, a global scale ratio
first, 0.1 ft tolerance) and reports the rest. On held-out vector plans, labelled rooms within 2 % of their label went
from 172/316 to 217/316; area error against the truth from 43.4 % to 42.4 %. **Not done:** dimension lines, the AI
scale estimate for undimensioned plans, the ceiling-height control. The 2 % target is not met (69 % of rooms).

## Stage 6: review page (partial)
Severity checklist with Fix and Dismiss and a count; critical items keep Build off; room names and ft-in sizes on
the plan; typed room sizes; spiral checkbox (§43). Screenshots: `docs/run3/review/`. **Not done:** rebuild in the
frontend's style, live 3D shell preview, autosave, split and merge, phone layout.

## Stage 7: assembly (partial)
Rooms are furnished from the library kits and the kit used for each room is recorded in the build's meta. **Not
done:** a style seeded by a plan hash.

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
  1,886 triangles, 6.00 × 4.00 × 0.85 m. Preview: `docs/run3/creator/koi_pond_preview.png`. The water reads very dark
  in the evening preview. A scripted helipad tested the pipeline without a model.

## Running totals
Live AI calls: 6 of 80. Render time: about 30 minutes. Free disk: about 299 GB.
