# Pro run summary

Branch `feat/pro`, started 2026-11-20 from `feat/merged` (d08ad48). Nothing pushed. Updated after
every stage; the task-by-task record with commit hashes is [LOG.md](LOG.md).

## Status

| Part | State |
|---|---|
| PART 1, 2D generator | done (task 10 partial: the 98% drawing-only target is not met for doors and windows) |
| PART 2, 3D | done, with B3 skipped, D partial (curved rooms) and the Unreal stills not made (see below) |
| PART 3, small items | done |

Live AI calls used: about 50 of 100 (PART 1 task 10 and chat tests about 35, most of them retries
against HTTP 429; about 12 in a PART 2 held-set run through a stale cache check, since fixed; about 3
for the opt-in live chat test at the end, which now passes). No AI video service was used.

Rendering (laptop rules): about 42 minutes of Blender rendering and baking in total (limit 3 hours),
every render under 10 minutes (longest still 119 s), 2 minutes between stills, `nice -n 10`, only on
AC power (checked before each batch and by `--ac-only` inside it). Unreal ran twice, 4 minutes each,
without producing a render.

## PART 1: professional 2D generator

### What changed (your problems -> what now happens)

| Your problem | Now |
|---|---|
| Too bright | Black and greys on white; colour only as light hatches for water, lawn, garden and paving; no room fills. |
| Not like a CAD drawing, unprofessional font | ISO 128 pen weights (exterior walls 0.70 mm with dark poché, interior 0.50 mm grey, fixtures 0.18 mm, hatches 0.13 mm), hinged/double/sliding door symbols, windows with frame and glazing lines, stairs with treads, walking line, UP and cut line; one font, Jost (SIL OFL), in ISO 3098 sizes. |
| Too much area to the garden | Built-up area aimed at 70% of the plot (kept within 65-75%), rooms sized to it with per-type caps; nandu-like brief: 3,201 sq ft built-up of 5,001 (64%) instead of 1,987 sq ft. Setbacks are settings (3 m front, 1.5 m sides and rear). |
| Pool next to kitchen, living and bar "not supported" | A rule language (touches several rooms with doors, door between two spaces, front/rear/left/right, zone, size and aspect bounds, daylight) enforced by the CP-SAT solver; outdoor areas take part and get doors. Spatial requests are never "not supported"; an edit that does not fit triggers a full re-solve (30 s budget, progress in chat); "break the plan" always re-solves; conflicts are named with two working layouts offered ("use option 1"). The nandu request now solves in about 14 s without the AI. |
| No fixtures, scale bar, revision info, layered CAD, DWG | Fixtures as blocks (WC, basin, shower, bath, counter with sink and hob, fridge, wardrobes, beds...), furniture switchable; graphic scale bar, north arrow, legend, title block with project, client, drawing number, version, scale, date, setbacks, revision table, area schedule, logo placeholder and "For design purposes only, not for construction"; DXF in mm with US NCS layers, blocks, DIMENSION and HATCH entities; IFC4; DWG (AutoCAD 2018). |
| 3D does not read generated plans properly | One building model (mm, 50 mm grid) is the source of every export; its PlanTo3D plan is made directly (pool and garden inside the 3D floor, PUJA/BAR keep their types, stairs have flights). Every PDF carries the model, signed: 3D and BOQ use it exactly, for any user. |

### Measured

- **Round trip** ([2d/ROUNDTRIP.md](2d/ROUNDTRIP.md)), 20 generated plans: with the embedded
  model, 3D and BOQ equal the model exactly on 18/18 (two small briefs do not fit the default
  setbacks with the DBC room minimums). With the attachment removed: vector detector walls
  95.9% / 96.2%, doors 82.6% / 89.4%, windows 91.5% / 95.6%, rooms 100% / 97.5%, room types
  100%; the new OpenCV reader walls 84.8% / 74.2%, doors 45%, rooms 66%; the AI reader returned
  no walls on half the plans and was rate-limited. **Not 98%** for doors and windows.
- **Samples** ([2d/samples/](2d/samples/), samples.json): 1,500 sq ft (one bedroom: two
  bedrooms do not fit a 30 x 50 ft plot inside the default setbacks), 3,000, 5,000 and
  8,000 sq ft villas and the nandu request, each as PDF (A3, model attached), DXF, DWG, IFC, SVG
  and PNG; contact sheet beside the references (`contact_sheet.pdf/png`). No sample has a
  critical check issue. The nandu files and the contact sheet stay on disk only (client name and
  your reference drawings).
- **CAD checks**: DXF passes `ezdxf.audit`; FreeCAD 1.1.4 opens it headless. IFC passes
  `ifcopenshell.validate` with EXPRESS rules; FreeCAD NativeIFC opens walls, doors, windows,
  spaces and slab. DWG read back with identical entity counts and layers (ODA and LibreDWG).
- **Suites**: backend 1,239 passed, 3 skipped; frontend 294 passed; type-check and build clean.

### Research findings (PART 1)

Dubai Building Code 2021 Part K values were read from the code's own tables (official link is
dead; an archive.org copy was used): living spaces 10.5 m² / 3.0 m net, maid's room 5.5 m² /
2.1 m, kitchen 5.4 m² / 1.8 m, doors 915 mm (710 mm for bathrooms), corridors 1.0 m, stairs
risers 100-180 mm, treads at least 280 mm, width 1.0 m, headroom 2.3 m, glazing at least 10% of
the floor, standalone villa setbacks 3 m on every side, parking 3.0 x 5.5 m open. Every value is
in [2d/RULES.md](2d/RULES.md), marked to be confirmed by an engineer. HouseDiffusion, House-GAN++
and Graph2Plan are research-only or unlicensed; ideas only.

### New dependencies (details in [DEPENDENCIES.md](DEPENDENCIES.md))

ifcopenshell 0.9 (LGPL-3.0, library); Jost font (OFL); ODA File Converter (proprietary freeware,
DWG writer, only where installed); GNU LibreDWG 0.14 (GPL, check tool only); FreeCAD 1.1.4
(LGPL, test-time checker only).

## PART 2: 3D

### A. Diagnosis ([3d/DIAGNOSIS.md](3d/DIAGNOSIS.md))

- The pool "line of water" came from sliver rectangles in the old generator export: pool pieces
  narrower than 3 ft are now deck, and the model's water rectangle is built exactly.
- Rooms looked smaller because the old drawing printed centre-line sizes while the 3D built net sizes
  (2-5 %), and AI-read scales ran 1-4 % under. PART 1's drawing and the 3D now come from one model.
- Kits and area builders are used through the gateway; rooms typed generically (e.g. BAR and PUJA read
  as "room" in older jobs) are built empty.

### B. Reading uploaded plans ([3d/RESEARCH.md](3d/RESEARCH.md))

- New scan reader (`plan3d/scan_reader.py`): OpenCV walls with several masks per drawing style,
  RapidOCR (Apache-2.0) for names, sizes and floor titles, storeys split by their titles, scale fitted to
  every size label, rooms more than 2 % from their label listed for review. No AI call; the AI reader
  runs only when it finds fewer than 3 named rooms.
- Held-out generated plans (50, never used for tuning), **before -> after** (no AI calls after):
  raster plans read 17-29 % (cached AI readings only) -> 67-86 %; raster wall precision with an AI
  read of every plan 20-39 % -> 20-70 % per style, all 50 plans 42 % -> 66 %; wall recall per raster style 24-41 % (AI) -> 21-64 % (solid drawings
  64 %); storeys right 83-86 % -> 67-86 %; room types 68-81 % (AI) -> 11-52 %. The scan reader is
  bimodal: 9 of 25 raster plans at 80-100 % walls, the others cut wrongly.
- Scale (B4): 59 of 161 labelled rooms (37 %) within 2 % of their label; when a room is cut right it is
  within 2 %, the rest are segmentation errors (listed on the review page). **Not 2 % for every room.**
- B3 model comparison: not run (no held-out scan has readings by both models; 429s). Default unchanged.
- Repositories read for ideas only: CubiCasa5k (CC BY-NC), DeepFloorplan (GPL-3), FloorplanTransformation
  (MIT code, other data terms); OCR candidates RapidOCR and docTR (Apache-2.0).

### C. Low quality

Medium removed (API, app, emails; old "medium" jobs read as High); Low is the default; "Coming soon"
removed. After every build each room is compared with the plan (area, and the size its label states):
more than 5 % is listed in `build_report.json` and shown as an error in the walkthrough (1000206523.pdf:
6 rooms flagged, 6-66 %). Walkthrough features unchanged.

### D. Room kits

Added: integrated dishwasher, oven under the hob and an oven/microwave tower (from the references in
`docs/reference/appliances`), passenger lift cabins (teak, mirror, handrail, button panel) and service
lifts (steel, bumper rails), a pool ladder. Kept: puja mandir and the prayer room facing the qibla
(`PLAN3D_QIBLA_BEARING`). **Not done: curved and circular rooms** (plan rooms are rectangles; needs an
arc shape in the plan format, your decision).

### E. High quality

- The friend's look (docs/reference/style) is ported into `blender/look.py`: the evening sky with the
  band of last light, limestone, paving, plaster, water and glass, warm facade wall washers, the Cycles
  settings and the finishing pass; the handover's texture-cache gotcha is handled. `scripts/history`
  was not run.
- High stills of every room and the four elevations (front, rear, left, right, named by compass), in
  the evening (default) or by day; gallery and downloads in the app; email when ready; progress, stills
  done and time left while rendering.
- A 1080p fast tour from the stills (depth by ray casting, parallax push-ins, crossfades, titles,
  minimap): 51.5 s from 17 stills in 5.6 min on the CPU. Rendered tours are now 1080p (High was 720p),
  with daylight, room titles and a minimap.
- Modern UAE front on the road side: bronze window fins and a cantilevered entrance canopy.
- Optional `PLAN3D_AI_POLISH` (off): one AI look per set of stills, validated exposure/white-balance
  re-renders only.
- Samples on disk: `docs/pro/3d/high/` (17 evening and 6 day stills, `contact_sheet.jpg`,
  `tour_fast_evening.mp4`; git-ignored).
- Unreal Engine 5.8: research ([3d/REALTIME_ENGINES.md](3d/REALTIME_ENGINES.md)), glTF/USD export,
  project and import/render script, `PLAN3D_RENDERER=unreal`, Pixel Streaming documented and off.
  **The Unreal stills were not made**: the import and scene work (523 assets in 20 s), but the editor
  quit before the capture in both attempts. Twinmotion: research only.

#### Renderer measured (Apple M1 Pro, 32 GB, Metal)

| Renderer | Time |
|---|---|
| Blender Cycles, room still 1920 x 1080, 96 adaptive samples, evening | 98-119 s (108 s average, 13 rooms) |
| same, elevation | 21-27 s evening, 17-22 s day |
| same, room still by day | 73-78 s |
| Low build of the nandu villa with its light bake | 160 s |
| Unreal 5.8 | no still (see above) |
| NVIDIA T4 (estimate, assumed 1.5-2x faster, not measured) | 55-75 s per room still; `scripts/benchmark_high.sh` measures it |

**Default renderer: Blender** (measured, headless, same machine as the builds, the reference look).

### F. Reference vs Low vs High

Eight sheets in `docs/pro/3d/compare/` (index committed, sheets on disk). Low and High show the same
furnished house; against your references the gap is design detail (feature ceilings, chandeliers,
stone and wood feature walls), not light.

### G. Suites

See "Final suites" below.

## PART 3

- **Saved BOQs**: every finished bill is saved for its owner (`GET/DELETE /api/v1/sheets/boq/history`),
  listed on the dashboard ("Saved BOQs") and opened at `/boq?bill=<id>`. Needs the migration below; a
  failed save never fails a bill.
- **Landing images**: the auth page hero 427 KB -> 264 KB (block SSIM 0.991). The 40 MB of tour frames
  were left as they are: re-encoding saved only 2-7 % (SSIM 0.989-0.993).
- **Deployment**: `backend/Dockerfile` (libGL for OpenCV/RapidOCR, optional ODA converter),
  `services/planto3d/Dockerfile` (whole library built, still settings), `docs/deploy-3d.md`,
  `scripts/asset_library.sh` (rebuild, pack, unpack, copy, check: 35 CC0 assets, 46 library entries).

## What you must decide (so far)

1. **Setbacks**: your defaults (3 m front, 1.5 m sides and rear) are below the DBC table for a
   standalone villa (3 m all round; 1.5 m is an Emirati Home First relaxation). The checker warns.
2. **Small plots**: with setbacks and the DBC minimums, a 30 x 50 ft plot fits one bedroom and
   30 x 50 / 35 x 60 ft two-bedroom briefs fail with a message suggesting smaller setbacks
   ("no setbacks" in the chat works). `FLOORPLAN_SITE_RULES=false` restores whole-plot layouts
   with the earlier, smaller room minimums.
3. **DWG**: the ODA File Converter writes good DWG but ships no licence text; confirm its use on a
   commercial server with ODA. Without it DWG returns 503 and DXF remains.
4. **Signing key**: set `FLOORPLAN_MODEL_SIGNING_KEY` in production (otherwise a key derived from
   `PLAN3D_EMBED_SECRET` or `SUPABASE_JWT_SECRET` is used; with neither, PDFs carry the model
   unsigned and our readers fall back to reading the drawing).
5. **AI quota**: the Gemini key hit HTTP 429 rate limits during the run (the opt-in live chat test
   passed at the end).
6. **Curved rooms**: the plan format has rectangles only; curved and circular rooms need an arc shape.
7. **Unreal**: whether to pursue it (seat subscription above USD 1 M revenue; a GPU machine with a
   window for the editor); the capture step is not yet verified.
8. **Pixel Streaming**: off; it needs a GPU per viewer session and is royalty-bearing if Engine code
   ships to clients.
9. **Scan reader**: it beats the AI reader on wall precision without AI cost, but its room types are
   worse; keep it on (`PLAN3D_SCAN_READER=true`, default) or off.
10. **AI polish** (`PLAN3D_AI_POLISH`) and the Unreal renderer are off until you turn them on.

## SQL to run

One migration, written and not applied (`backend/migrations/versions/20261120_0001_boq_history.py`):
`uv --directory backend run alembic upgrade head`, or paste this into the Supabase SQL editor, then set
`BOQ_HISTORY_STORE=supabase` (the default outside tests).

```sql
CREATE TABLE boq_history (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    user_id UUID NOT NULL,
    name TEXT DEFAULT '' NOT NULL,
    source TEXT DEFAULT 'upload' NOT NULL,
    summary JSONB DEFAULT '{}'::jsonb NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT boq_history_source CHECK (source in ('upload', 'floorplan', '3d'))
);
CREATE INDEX boq_history_user_created ON boq_history (user_id, created_at desc);
alter table boq_history enable row level security;
create policy boq_history_owner on boq_history for all
    using (auth.uid() = user_id) with check (auth.uid() = user_id);
```

## Final suites (2026-11-20, end of the run)

| Suite | Result |
|---|---|
| Backend (`TESTING=1 uv run pytest`) | 1,263 passed, 3 skipped (6 min) |
| Frontend (`vitest run`) | 298 passed; `tsc -b` clean; `vite build` passes |
| PlanTo3D Python tests (14 files) | all pass |
| PlanTo3D `tests/run_all.sh` | as before this run: the tour check (reported, not required) and one doorway in an old saved build (`jobs/0bdaca14d7bf`) fail; no new failures |
| Opt-in live chat test (`FLOORPLAN_LIVE_LLM=1`) | passes |

Never claimed: 100 % accuracy anywhere. Generated and parsed plans carry "For design purposes only, not
for construction".
