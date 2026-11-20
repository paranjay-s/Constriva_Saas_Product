# Reading accuracy on the held-out plans (C2.2, C2.3)

Set: the 50 held-out generated plans of `docs/overnight/testplans` (26 scans in four drawing styles, 24 vector
plans read by PlanTo3D's detector), scored by `tools/testplans/score_all.py` (wall recall and precision by length,
doors and windows found, room types, specials, storeys, building type). Never tuned on. Measured 2026-11-20.

## C2.3: claude-opus-5-5 against claude-fable-5-2 as the AI reader (scans read by the AI alone)

Fable 5.2 is the most capable model this account can call (Anthropic's model list); the default stays
claude-opus-5-5 as asked. Rows for the scans; the vector rows are the detector's and identical in both runs.

| Scan style (plans) | Model | Wall recall | Wall precision | Doors found | Windows found | Room type |
|---|---|---|---|---|---|---|
| raster_fills (7) | opus-5-5 | 51% | 44% | 29% | 41% | 88% |
|  | fable-5-2 | **93%** | **83%** | **76%** | **90%** | 89% |
| raster_hatched (7) | opus-5-5 | 46% | 42% | 43% | 29% | **92%** |
|  | fable-5-2 | **92%** | **87%** | **90%** | **88%** | 87% |
| raster_lines (6) | opus-5-5 | 46% | 38% | 55% | 43% | **85%** |
|  | fable-5-2 | **78%** | **69%** | **72%** | **77%** | 76% |
| raster_solid (6) | opus-5-5 | 25% | 20% | 42% | 58% | 88% |
|  | fable-5-2 | **100%** | **85%** | **95%** | **93%** | 88% |
| All 50 plans | opus-5-5 | 69% | 63% | 65% | 67% | 87% |
|  | fable-5-2 | **95%** | **89%** | **90%** | **93%** | 85% |

Cost per scanned plan (from the token counts the parser stores with each reply; list prices $4 / $20 per million
tokens for Opus 5.5, $8 / $40 for Fable 5.2):

| Model | Plans | Mean input tokens | Mean output tokens | Calls (with repairs) | Cost per plan | Total |
|---|---|---|---|---|---|---|
| claude-opus-5-5 | 26 | 10,799 | 8,731 | 26 | **$0.22** | $5.66 |
| claude-fable-5-2 | 26 | 12,980 | 18,474 | 29 | **$0.84** | $21.07 (25 plans) |

Fable 5.2 also takes several minutes per plan (Opus 5.5 under a minute in the cached runs' logs). Live calls for
this comparison: 4 (Opus, plans not yet cached) + 29 (Fable).

## C2.2: scans read by the scan reader for walls and the AI (opus-5-5) for room names and types

Now the gateway's behaviour (`plan3d/scan_names.py`, `PLAN3D_SCAN_AI_NAMES=true`): when the scan reader reads a
scan, the AI reader also reads it (one cached call) and each scan room takes the type, and the name when OCR found
none, of the AI room with the same label, else the nearest one in relative position. Geometry never comes from the
AI. Measured with the Opus readings above (no new calls):

| Scan style | Scan reader alone (feat/pro, B) room type | Scan walls + AI names room type | Wall recall / precision | AI alone (opus) room type |
|---|---|---|---|---|
| raster_fills | 11% | **32%** | 48% / 53% | 88% |
| raster_hatched | 27% | **47%** | 28% / 22% | 92% |
| raster_lines | 21% | **61%** | 55% / 52% | 85% |
| raster_solid | 52% | **61%** | 67% / 66% | 88% |

Room types improve by 9-40 points over the scan reader alone, as asked, but stay below the AI reader alone: a room
type counts only when the room itself is found, and the scan reader cuts rooms differently (merged or split
rooms take no type). Walls: the scan reader beats Opus 5.5's walls on three of four styles, but Fable 5.2's walls
beat both by far (78-100 % recall).

**For the owner to decide**: with Fable 5.2 as the plan reader, scans would be read best by the AI alone (walls
95 %, doors 90 %, windows 93 % on these 26 scans) at about $0.84 a plan; with Opus 5.5 the scan-walls-plus-AI-names
path is the better wall reading at $0.22. The default was not changed.

## The fresh plan (C2.1)

`~/Downloads/1000207168.pdf` is a 72 dpi scan with hollow walls (two thin lines). The scan reader traces no walls
on it, so it goes to the AI reader, whose walls were rough: 2 of 13 labelled rooms within 5 % of their labels, the
outer walls on the dimension lines (see 3d/SPACE.md). A hollow-wall mask for low-resolution scans was tried twice
and reverted (LOG.md). On the held-out scans Fable 5.2 reads walls far better than Opus 5.5 (above); the fresh plan
itself was not re-read with Fable (the default model was to stay).
