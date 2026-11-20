# 2D generator rules and engineering checks

**Every value on this page is to be confirmed against the Dubai Building Code by an engineer.**
Sources: Dubai Building Code 2021, Part K (villas), read from the code's own tables (see
[RESEARCH.md](RESEARCH.md)); where the code is silent, common practice is named as such.
Code: `backend/app/modules/ai/floorplan/model/checks.py` (`CHECKS`), `rules.py`, `settings.py`.

## Site and areas (settings)

| Setting | Default | Source / note |
|---|---|---|
| `FLOORPLAN_SETBACK_FRONT_M` | 3.0 m | your instruction; DBC Table K.1 road side 3 m |
| `FLOORPLAN_SETBACK_SIDE_M` | 1.5 m | your instruction; **DBC Table K.1 says 3 m** (1.5 m is a Home First relaxation for Emiratis). The check warns (SETBACK_DBC). |
| `FLOORPLAN_SETBACK_REAR_M` | 1.5 m | as above |
| `FLOORPLAN_BUILT_UP_SHARE` | 0.70 | your instruction; DBC sets no coverage cap for private villas (setbacks govern) |
| `FLOORPLAN_BUILT_UP_MIN` / `_MAX` | 0.65 / 0.75 | your instruction; COVERAGE warning outside the band |
| Built-up (gross) area | to the outer face of external walls | DBC K.5.2.7 plot coverage |
| Room gross area | the room on wall centre lines plus the outer half of its external walls | sums to the built-up area exactly |
| Room net area | inside the wall faces | DBC K.5.2.6 measures gross area inside external walls; we report both |
| Enclosed rooms | inside the setback line (SETBACK, critical) | DBC K.5.2.4 |
| Pool, garden, lawn, parking, driveway, deck | may use the setback strips, never leave the plot | assumption: they are not buildings |

## Walls, doors, windows

| Item | Value | Source |
|---|---|---|
| Exterior wall | 200 mm (`FLOORPLAN_WALL_EXTERIOR_MM`) | your instruction |
| Interior wall between rooms | 150 mm | your instruction (100-150) |
| Partition inside a suite (bath, WC, dress, store, utility) | 100 mm | your instruction |
| Door clear width, main entrance and rooms | ≥ 915 mm (doors drawn 950 or 1000 mm) | DBC K.5.4.1 Table K.4 |
| Door clear width, bathrooms and WCs | ≥ 710 mm (drawn 750 mm) | DBC K.5.4.1 Table K.4 |
| Door, stores, dressing rooms, utility | ≥ 710 mm (drawn 800 mm) | **assumption**: treated as non-habitable like WCs |
| Door height | 2100 mm, main door 2400 mm | practice |
| Window glazing | ≥ 10% of floor area for bedrooms, living spaces and kitchens; ≥ 8% for maid's and driver's rooms; sliding glass doors to the outside count | DBC K.5.4.2.1 |
| Window sill (openable) | 900 mm; bathroom high-level 1500 mm | DBC K.5.4.2 (900-1500 mm for operable parts) |
| Every habitable room has a window on an outside wall (onto the setback strip, a garden, pool or court) | NO_WINDOW, critical | DBC K.5.4.2 |
| Bathroom / WC without a window | VENTILATION warning: mechanical extract needed | DBC K.5.7.1 and K.10.1.6 |

## Rooms

| Room | Minimum net area | Least net dimension | Source |
|---|---|---|---|
| Bedroom, living, majlis, family hall, dining, study, gym, bar | 10.5 m² | 3.0 m | DBC K.5.3.1 Table K.2 "living spaces" |
| Maid's room, driver's room (single, no bath) | 5.5 m² | 2.1 m | DBC Table K.2 |
| Enclosed kitchen | 5.4 m² | 1.8 m | DBC Table K.2 |
| Kitchen aisle between counters | 1.2 m | | DBC K.5.3.1 (Figure K.18) |
| Bathroom | 2.5 m² | 1.2 m | practice (DBC defers to K.5.7) |
| WC | 1.1 m² | 0.85 m | practice |
| Corridor / lobby / passage | | 1.0 m clear | DBC K.5.5.1 |
| Clear heights | living and bedrooms 2.7 m; others 2.3 m | | DBC K.5.3.2 Table K.3 (storey 3.3 m floor to floor) |

## Stairs (STAIR, critical)

| Item | Value | Source |
|---|---|---|
| Riser | 100-180 mm, uniform | DBC K.5.5.2.3 |
| Going (tread) | ≥ 280 mm (drawn 290 mm) | DBC K.5.5.2.3 |
| Clear width | ≥ 1000 mm | DBC K.5.5.2.2 |
| Landing | ≥ stair width and ≥ 1000 mm | DBC K.5.5.2.4 |
| Headroom | ≥ 2300 mm | DBC K.5.5.2.10 |

## Fixtures and kitchens

| Item | Value | Source |
|---|---|---|
| WC or basin centre from a side wall | ≥ 400 mm (WC_CLEARANCE warning) | DBC K.5.7.2 |
| Clear space in front of WC / basin | 750 mm | DBC K.5.7.2 (not yet checked) |
| Kitchen work triangle sink-hob-fridge | each leg 1.2-2.7 m, total 4.0-7.9 m (warning) | NKBA kitchen planning guideline (not DBC) |
| Wardrobes | never in front of a window | drafting rule |

## Storeys

| Item | Value | Source |
|---|---|---|
| Wet areas stacked | a bath, WC, kitchen or utility on an upper storey overlaps a wet room below by ≥ 50% (warning) | practice (drainage) |

The generator draws one storey today, so this check reports "info" until upper storeys are
generated; the model and the check already support several storeys.

## How the checks are used

Every version is checked. The chat reply after generation lists the result; after an edit it
names any critical issue. The plan's notes panel lists all issues with their source. A plan
with a critical issue is never delivered without saying so.
