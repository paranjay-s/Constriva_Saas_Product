# Part A report: accuracy (2026-11-19)

Hardware for every timing: Apple M1 Pro, 32 GB RAM, 14-core GPU (Cycles on Metal), macOS 27.0.1, Blender 5.3.0.
Pictures are local only, in `docs/overnight/shots/` (git-ignored).

## Your two new PDFs
| File | Contents | Reader |
|---|---|---|
| `antonovich-design-20250DjgFZYRphpj.pdf` | the **dock** (DOCK FOR YACHT), the long **pool**, lift, service lift, bar, breakfast, show / dirty kitchen, cold store, guest bedroom, entrance foyer, open-plan family living + dining + breakfast | AI (raster screenshot, no text layer) |
| `antonovich-design-2025fMhHtV8AHyLf.pdf` | the **pool** (FUTURE SWIMMING POOL), fountain, garage with two cars, open-plan kitchen (7) / dining (8) / living (9); rooms numbered, no names | AI; Opus's plan was implausible, so it went to tracing |

Which file had "about 65 % of walls": I could not tell from the message. Measured below.

## A0: missed walls by cause (before changes)
Both plans come from the AI reader (claude-opus-5-5). Lengths measured on the page by eye at the plan's own fit (+-10 %).

| File | Cause | Missed wall length |
|---|---|---|
| dock | slanted or curved (round lift / spiral stair core) | ~10 m |
| dock | thin single lines (store in bedroom 1) | ~4 m |
| dock | misplaced > 0.15 m (sitting / dock wall 1.1 m off) | ~7 m |
| dock | outside the main cluster (terrace and planter edges) | ~12 m |
| dock | openings: 4 of ~15 glazed bays read as windows | - |
| pool | geometry distorted: Opus plan 15.3 x 20.5 m, drawing ~0.55 wide per height; cannot be laid on the page | most interior walls |
| pool | thin grey partitions merged (living 9, rooms 11, 12) | - |
| pool | pool not found (read as "Outdoor Dining Terrace") | the pool |

## What changed (commits on feat/planto3d-integration, before this night branch)
- `8a4ad62` Save as reference (dev: `scripts/run_planto3d.sh --dev`, standalone review page) and `tools/score_plan.py`.
- `5f84a63`, `1ee852c` One room vocabulary (`services/planto3d/web/rooms.json`, `rooms.py`) used by the detector, converter, furniture, builder and review page; 30 types, synonyms, abbreviations, fuzzy spelling, Arabic labels; unknown labels -> unfurnished "multipurpose" + flag (never a silent guess); 209-label test. New furniture: breakfast, bar, foyer, store shelving, gym mat, cinema; garages get as many cars as fit (two in a double garage).
- `c0fc072`, `9a8c23d`, `4ddbb64` Pools, water bodies and docks are built (basin, tile, coping, steps, water; dock: water plus plank decks on posts); blue on the map; walker kept out of water and lift shafts; unlabelled blue-filled regions are pools.
- `6778a2b` Open plans: one function per zone (no sofa group in a dining zone unless its label also names a living room), 0.9 m passages between neighbouring indoor zones; open-plan test.
- `f4fb3ad` "Needs checking" list on the review page (unknown labels, multi-use labels, doors leading nowhere, area off its label by > 10 %, large unlabelled spaces), orange outlines.

## A1: model comparison (uncached runs, same prompt)
| Plan | Model | Walls | Openings | Rooms | Pool found | Plausible | Time | Tokens in / out | Cost |
|---|---|---|---|---|---|---|---|---|---|
| dock | claude-opus-5-5 | 31 | 17 | 30 | yes | yes | 58.9 s | 10,799 / 7,508 | $0.19 |
| dock | claude-fable-5-2 | 33 | 30 | 30 | **no** | no (47 % leak) | 144.1 s | 10,799 / 16,307 | $0.74 |
| pool | claude-opus-5-5 | 17 | 8 | 17 | **no** | no (36 % leak) | 49.9 s | 10,799 / 5,574 | $0.16 |
| pool | claude-fable-5-2 | 38 | 18 | 24 | yes | yes | 183.9 s | 10,799 / 19,374 | $0.86 |

Prices from the Claude API reference: Opus 5.5 $4 / $20, Fable 5.2 $8 / $40 per million tokens. Room type accuracy: dock, both models typed 30 of 30 named rooms correctly with the new vocabulary (Fable lost the pool, found the round lift); pool file, numbered rooms have no names on the sheet, so their types come from the model's own guess. Default not changed.

## A1: tracing and snapping
On the pool file with the Fable plan (laid on the page at 36.4 px/m on both axes), the AI walls cover **94 %** of the traced grey wall bands (85.3 of 90.4 m); 5.2 m missed. With the Opus plan the walls cannot be registered (distorted). On the thin-line dock drawing the band tracer picks text and furniture as bands, so it cannot be trusted. Snapping was **not** added to the backend: the possible gain is small and only exists when the AI's proportions are right.

## A6: 3D results (Low builds)
- Dock house (Opus read, gateway): built in 219 s; pool, dock, aquarium as water; water / walk / opening tests pass (5/5, 52/52). `sheet_water.jpg`, `sheet_dock.jpg`.
- Pool house (Fable read, imported): built in 137 s; pool and fountain as water; 4/4, 55/55. `sheet_pool.jpg`.
- Open plan (dock house): living, dining and breakfast each furnished once; sparse rather than cluttered.

## Still inaccurate
- Raster plans depend entirely on the AI reader; neither model is reliable on both files.
- Scale is assumed when no dimension is printed (dock file).
- Garage numbered "2" stays an unknown room (no legend), so no cars there.
- SF door 9 (dead-end recess read as a door) is still open: `run_all.sh` fails on it.
- Not done from A1-A5: orange "possible missed wall" marks with one-click add; per-element source and confidence; opt-in storing of corrections; kitchen island facing other zones; dragging zone cuts on the review page; AI classification of unknown labels.

## Tests at the end of Part A
Backend 1112 passed, 4 skipped; frontend 251 passed; PlanTo3D test_sample, test_doorway, test_reader (11 variants), test_rooms (209 labels), test_openplan, test_site, test_review pass; `run_all.sh` fails only on SF door 9.
