# 3D diagnosis (PART 2, A)

Done before any 3D change. Tools: `tools/diag/rooms_report.py` (per room: read type and size, the
size its label states, built size, builder and furniture source) over `build_report.json`, which
`blender/gen.py` now writes with every build (PlanTo3D patch 53). Builds below are draft builds
without light maps (`--no-bake`, 10-16 s each, `nice -n 10`, on AC power).

## Your last test

The latest 3D job is `88c31f1e3f0d` ("nandu", made from the floor plan generator, built at 03:24
with a High tour started at 06:21 that stopped at frame 820 of 7,132 when the server stopped). The
walkthrough you recorded at 03:30 (`~/Downloads/walkthrough-2026-11-20-03-30-58.mp4`) shows the
pool and, beside it, a long thin strip of water.

### Why the pool became a line of water

The old generator-to-3D path turned the pool and the gaps joined to it into a pool zone of three
rectangles, two of them slivers (0.2 x 0.4 ft and 9.5 x 0.4 ft). `water_parts` puts a 0.8 ft
coping round every rectangle and water inside it; inside a 0.4 ft sliver the "inside" is
inverted, which drew a thin line of water. **Fix (general):** a pool rectangle narrower than
3 ft is paved deck, never water; when the plan carries the model's water rectangle (PART 1's
direct export) the basin is built exactly there and the rest of the pool area is paved round it.
Rebuilt: one basin 29.1 x 11.8 ft, slivers paved.

### Why rooms looked smaller than the drawing

- The old generator printed **centre-line** sizes on the drawing but the 3D built **net** sizes
  (between wall faces): every room was 2-5% smaller than its label (LIVING 15.4 x 27.5 ft built vs
  15'9" x 28'1" printed; BAR 11.3 x 12.2 vs 11'10" x 12'10"). PART 1's drawing now prints net sizes
  and the 3D plan comes from the same model, so they agree.
- Read drawings: the builder builds exactly what was read (built area = read area for every
  room). The difference comes from reading: the AI reading of 1000206523.pdf is 1-4% under its
  labels for most rooms (and 12% for one bath); open-plan rooms that merge with a neighbour read
  far larger than their label (see below). Fix in B4: fit the scale to every labelled size.
- BAR, PUJA and GAMING ROOM reached the builder as the generic type `room`, so they were built
  empty on plain tile: part of "the look has not changed". Fixed in PART 1 (the model keeps
  `bar` and `puja`); GAMING has no kit yet.

### Are library kits and area builders used through the gateway?

Yes for kits: every build uses the asset library (`services/planto3d/library`, 46 pieces, served
when approved or team-made): bed, desk, wardrobe, nightstand, sofa, rug, tv_unit, vanity, wc2,
shower2, fridge2, dining_set, puja_mandir... Kitchens use built-in runs and cabinets. Area builders
(`areaspec`) are used only for zones typed `custom` (unknown areas classified by the AI); none of
the three plans below has one. Nothing needed wiring; the report now shows what was used.

## nandu (job 88c31f1e3f0d, rebuilt with the fix)

| Type | Label | Read (ft) | Label says (ft) | Diff | Built area (ft²) | Builder | Furniture (source) |
|---|---|---|---|---|---|---|---|
| bedroom | MASTER BED ROOM | 18.7 x 13.9 (259.3) |  |  | 259.3 | floor wood | bed (library kit), desk (library kit), wall_art (built-in), wardrobe (library kit) |
| toilet | BATH | 13.2 x 4.8 (64.1) |  |  | 64.06 | floor bathtile | geyser (built-in), shower2 (library kit), vanity (library kit), wc2 (library kit) |
| dress | DRESS | 12.3 x 4.8 (59.3) |  |  | 59.3 | floor wood | wardrobe (library kit) |
| bedroom | MASTER BED ROOM | 19.7 x 11.2 (221.0) |  |  | 220.99 | floor wood | bed (library kit), desk (library kit), wall_art (built-in), wardrobe (library kit) |
| toilet | BATH | 6.0 x 10.4 (63.0) |  |  | 62.98 | floor bathtile | geyser (built-in), shower2 (library kit), vanity (library kit), wc2 (library kit) |
| dress | DRESS | 4.8 x 10.4 (50.5) |  |  | 50.49 | floor wood | wardrobe (library kit) |
| room | GAMING ROOM | 19.7 x 10.7 (210.3) |  |  | 210.27 | floor tile |  |
| pool | SWIMMING POOL | 30.7 x 13.8 (415.5) |  |  | 74.27 (water 29.12 x 11.8) | water_parts |  |
| garden | GARDEN | 9.5 x 34.0 (322.5) |  |  | 322.52 | floor turf | plant (library kit) |
| garden | LAWN | 57.7 x 38.9 (2234.7) |  |  | 2234.69 | floor turf | plant (library kit) |
| stair | STAIR | 6.8 x 13.9 (94.5) |  |  | 94.47 | floor stair |  |
| room | PUJA | 8.0 x 10.4 (83.5) |  |  | 83.52 | floor tile |  |
| living | LIVING | 15.4 x 27.5 (422.6) |  |  | 422.58 | floor marble | armchair (library kit), coffee_table (library kit), floor_lamp (library kit), plant (library kit), rug (library kit), side_table (library kit) |
| kitchen | KITCHEN | 11.3 x 14.9 (167.5) |  |  | 167.49 | floor marble | chimney (built-in), fridge2 (library kit), kitchen_run (built-in), wall_cab2 (built-in) |
| room | BAR | 11.3 x 12.2 (137.7) |  |  | 137.72 | floor tile |  |

## 1000206523.pdf (AI reading of job 39b97cc78c2c, rebuilt)

| Type | Label | Read (ft) | Label says (ft) | Diff | Built area (ft²) | Builder | Furniture (source) |
|---|---|---|---|---|---|---|---|
| living | LIVING ROOM - 2 31'9" x 20'6 | 31.4 x 19.8 (619.8) | 31.8 x 20.5 | 3.4% | 619.81 | floor marble | armchair (library kit), coffee_table (library kit), floor_lamp (library kit), rug (library kit), side_table (library kit), sofa (library kit) |
| kitchen | KITCHEN-1 + DINNING 39'6" x  | 39.1 x 20.1 (778.2) | 39.5 x 20.5 | 2.0% | 778.16 | floor marble | bar_stool (built-in), chimney (built-in), fridge2 (library kit), kitchen_island (built-in), kitchen_run (built-in), wall_cab2 (built-in) |
| toilet | BATH - 1 10'3" x 8'3" | 10.5 x 8.2 (86.4) | 10.2 x 8.2 | 2.4% | 86.38 | floor bathtile | geyser (built-in), shower2 (library kit), vanity (library kit), wc2 (library kit) |
| passage | PASSAGE 15'0" x 33'3" | 15.6 x 32.7 (478.7) | 15.0 x 33.2 | 4.0% | 478.69 | floor tile |  |
| toilet | BATH 8'0" x 6'0" | 7.8 x 6.7 (52.2) | 8.0 x 6.0 | 11.7% | 52.22 | floor bathtile | geyser (built-in), shower2 (library kit), vanity (library kit), wc2 (library kit) |
| kitchen | KITCHEN -2 15'0" x 15'0" | 15.4 x 15.5 (238.3) | 15.0 x 15.0 | 3.3% | 238.29 | floor marble | bar_stool (built-in), chimney (built-in), fridge2 (library kit), kitchen_island (built-in), kitchen_run (built-in), wall_cab2 (built-in) |
| water | AQUARIUM 8'0" x 18'0" | 8.0 x 18.0 (144.2) | 8.0 x 18.0 | 0.0% | 26.02 (water 7.0 x 17.01) | water_parts |  |
| wash | WASH AREA 8'0" x 23'9" | 23.8 x 16.8 (254.1) | 8.0 x 23.8 | 110.0% | 254.14 | floor concrete | dryer (library kit), washer2 (library kit) |
| bedroom | BEDROOM-1 20'0" x 16'0" | 20.1 x 16.1 (322.3) | 20.0 x 16.0 | 0.6% | 322.28 | floor wood | bed (library kit), desk (library kit), nightstand (library kit), wall_art (built-in), wardrobe (library kit) |
| dress | DRESS 10'3" x 8'0" | 10.5 x 7.5 (79.1) | 10.2 x 8.0 | 6.2% | 79.12 | floor wood | wardrobe (library kit) |
| puja | POOJA ARYA 13'6" x 14'0" | 23.7 x 20.2 (472.9) | 13.5 x 14.0 | 69.3% | 472.9 | floor marble | puja_mandir (library kit) |
| living | LIVING ROOM -1 31'0" x 20'6" | 31.3 x 19.8 (614.1) | 31.0 x 20.5 | 3.4% | 614.11 | floor marble | armchair (library kit), coffee_table (library kit), floor_lamp (library kit), plant (library kit), rug (library kit), side_table (library kit) |
| passage | PASSAGE 15'0" x 11'9" | 15.0 x 11.7 (175.7) | 15.0 x 11.8 | 0.4% | 175.71 | floor tile |  |

## OPT 5 - GEETA JI GAUD.pdf (vector detector, new reading, rebuilt)

| Type | Label | Read (ft) | Label says (ft) | Diff | Built area (ft²) | Builder | Furniture (source) |
|---|---|---|---|---|---|---|---|
| open | OPEN | 23.5 x 2.8 (63.0) |  |  | 63.02 | floor pebbles |  |
| toilet | DRESS/TOI. 7'X11'6 | 7.3 x 11.7 (79.7) | 7.0 x 11.5 | 4.3% | 79.66 | floor bathtile | geyser (built-in), shower2 (library kit), vanity (library kit), wc2 (library kit) |
| wash | WASH | 12.2 x 4.7 (55.0) |  |  | 55.04 | floor concrete | dryer (library kit), washer2 (library kit) |
| bedroom | BEDROOM 15'9X11'6 | 15.7 x 11.4 (178.5) | 15.8 x 11.5 | 0.9% | 178.53 | floor wood | bed (library kit), desk (library kit), nightstand (library kit), wall_art (built-in), wardrobe (library kit) |
| kitchen | KIT. 12'6X10' | 12.3 x 9.8 (121.0) | 12.5 x 10.0 | 2.0% | 121.01 | floor marble | chimney (built-in), fridge2 (library kit), kitchen_run (built-in), wall_cab2 (built-in) |
| dining | DRG./DIN. 17'9 X 21' | 26.4 x 20.9 (412.3) | 17.8 x 21.0 | 25.7% | 412.25 | floor marble | armchair (library kit), coffee_table (library kit), dining_set (library kit), floor_lamp (library kit), plant (library kit), rug (library kit) |
| toilet | TOI. 9'X5' | 8.9 x 4.9 (44.0) | 9.0 x 5.0 | 2.0% | 44.01 | floor bathtile | geyser (built-in), shower2 (library kit), vanity (library kit), wc2 (library kit) |
| open | OPEN 4'6X10'4 | 4.1 x 10.2 (42.1) | 4.5 x 10.3 | 8.9% | 42.09 | floor pebbles |  |
| bedroom | BEDROOM 13'4X10'4 | 13.2 x 10.2 (134.2) | 13.3 x 10.3 | 1.3% | 134.24 | floor wood | bed (library kit), desk (library kit), nightstand (library kit), wall_art (built-in), wardrobe (library kit) |
| toilet | DRESS/TOI. 6'X15'4 | 6.0 x 15.3 (92.5) | 6.0 x 15.3 | 0.2% | 92.49 | floor bathtile | geyser (built-in), shower2 (library kit), vanity (library kit), wc2 (library kit) |
| bedroom | BEDROOM 11'4X15'4 | 11.2 x 15.3 (171.3) | 11.3 x 15.3 | 1.2% | 171.27 | floor wood | bed (library kit), desk (library kit), wall_art (built-in) |
| parking | PARKING 18X18'6 | 17.9 x 18.4 (328.9) | 18.0 x 18.5 | 0.6% | 328.85 | floor pavers + parking_parts | car (built-in) |
| stair |  | 11.5 x 7.7 (79.7) |  |  | 79.75 | floor stair |  |
| parking | PARKING 6'X8'2 | 6.5 x 8.1 (51.8) | 6.0 x 8.2 | 8.3% | 51.79 | floor pavers + parking_parts |  |
| yard |  | 10.3 x 2.8 (28.7) |  |  | 0.02 | floor pavers |  |
| yard |  | 10.1 x 2.8 (28.1) |  |  | 13.14 | floor pavers |  |
| wash | WASH 7'5X5' | 7.3 x 4.8 (34.4) | 7.4 x 5.0 | 4.0% | 34.44 | floor concrete | dryer (library kit), washer2 (library kit) |
| kitchen | KIT. 7'5X9'6 | 7.3 x 10.2 (72.4) | 7.4 x 9.5 | 7.4% | 72.44 | floor marble | chimney (built-in), kitchen_run (built-in), wall_cab2 (built-in) |
| dining | DRG./DIN. 13'4X21' | 13.2 x 21.0 (276.4) | 13.3 x 21.0 | 1.0% | 276.38 | floor marble | armchair (library kit), coffee_table (library kit), floor_lamp (library kit), plant (library kit), rug (library kit), side_table (library kit) |
| passage | ENT.LOBBY 5'X10'4 | 4.8 x 10.3 (49.5) | 5.0 x 10.3 | 4.0% | 49.46 | floor tile |  |
| wash | WASH 7'5X5' | 7.4 x 5.0 (34.8) | 7.4 x 5.0 | 0.2% | 34.77 | floor concrete | dryer (library kit), washer2 (library kit) |
| kitchen | KIT. 7'5X9'6 | 7.3 x 9.7 (69.2) | 7.4 x 9.5 | 2.1% | 69.23 | floor marble | chimney (built-in), kitchen_run (built-in), wall_cab2 (built-in) |
| bedroom | BEDROOM 10'X11'6 | 10.2 x 11.4 (112.3) | 10.0 x 11.5 | 2.0% | 112.29 | floor wood | bed (library kit), nightstand (library kit), wall_art (built-in), wardrobe (library kit) |
| bedroom | BEDROOM 10'X11'6 | 10.3 x 11.4 (113.6) | 10.0 x 11.5 | 3.0% | 113.57 | floor wood | bed (library kit), nightstand (library kit), wall_art (built-in), wardrobe (library kit) |
| toilet | TOI. 4'X7' | 3.9 x 6.9 (27.1) | 4.0 x 7.0 | 2.5% | 27.13 | floor bathtile | vanity (library kit), wc2 (library kit) |
| dining | DRG./DIN. 13'4X21' | 13.3 x 21.0 (278.7) | 13.3 x 21.0 | 0.2% | 278.72 | floor marble | armchair (library kit), coffee_table (library kit), floor_lamp (library kit), plant (library kit), rug (library kit), side_table (library kit) |
| passage | ENT.LOBBY 5'X10'4 | 4.8 x 10.3 (49.4) | 5.0 x 10.3 | 4.0% | 49.44 | floor tile |  |
| toilet | TOI. 4'X7' | 3.9 x 6.9 (27.1) | 4.0 x 7.0 | 2.5% | 27.12 | floor bathtile | vanity (library kit), wc2 (library kit) |
| open | OPEN 4'X6'4 | 4.2 x 6.5 (26.6) | 4.0 x 6.3 | 5.0% | 0 | floor pebbles |  |
| open | OPEN 4'X6'4 | 4.2 x 6.3 (26.6) | 4.0 x 6.3 | 5.0% | 0 | floor pebbles |  |
| toilet | TOI. 4'X7' | 3.9 x 6.8 (26.7) | 4.0 x 7.0 | 2.9% | 26.69 | floor bathtile | vanity (library kit), wc2 (library kit) |
| toilet | TOI. 4'X7' | 3.9 x 6.8 (26.7) | 4.0 x 7.0 | 2.9% | 26.69 | floor bathtile | vanity (library kit), wc2 (library kit) |
| bedroom | BEDROOM 12'6X10' | 12.3 x 10.0 (122.4) | 12.5 x 10.0 | 1.6% | 122.39 | floor wood | bed (library kit), desk (library kit), wall_art (built-in), wardrobe (library kit) |
| bedroom | BEDROOM 12'6X10' | 12.4 x 10.0 (123.5) | 12.5 x 10.0 | 0.8% | 123.49 | floor wood | bed (library kit), desk (library kit), wall_art (built-in), wardrobe (library kit) |
| stair |  | 10.1 x 3.4 (33.8) |  |  | 0 | floor stair |  |
| balcony | SITOUT 26' X 8' | 35.9 x 7.8 (237.0) | 26.0 x 8.0 | 38.1% | 209.18 | floor terracotta | outdoor_set (built-in), plant (library kit) |

