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

## Stage 1: the library (in progress)
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
