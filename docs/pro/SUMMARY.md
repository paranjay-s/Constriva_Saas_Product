# Pro run summary

Branch `feat/pro`, started 2026-11-20 from `feat/merged` (d08ad48). Nothing pushed. Updated after
every stage; the task-by-task record with commit hashes is [LOG.md](LOG.md).

## Status

| Part | State |
|---|---|
| PART 1, 2D generator | done (task 10 partial: the 98% drawing-only target is not met for doors and windows) |
| PART 2, 3D | in progress |
| PART 3, small items | not started |

Live AI calls used: about 35 of 100 (all in PART 1, task 10 and the live chat test; most were
retries against HTTP 429 rate limits).

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
5. **AI quota**: the Gemini key hit HTTP 429 rate limits during the run; the live nandu chat test
   could not run (the same request passes as a deterministic test).

## SQL to run

None yet in this run.
