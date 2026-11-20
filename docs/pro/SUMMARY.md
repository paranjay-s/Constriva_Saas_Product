# Pro run summary

Branch `feat/pro`, started 2026-11-20 from `feat/merged` (d08ad48). Nothing pushed. Updated after
every stage; the task-by-task record with commit hashes is [LOG.md](LOG.md).

## Status

| Part | State |
|---|---|
| PART 1, 2D generator | tasks 1-5 done; 6-12 in progress |
| PART 2, 3D | not started |
| PART 3, small items | not started |

## PART 1 so far

- **Research** ([2d/RESEARCH.md](2d/RESEARCH.md)): Dubai Building Code 2021 Part K values read from
  the code's own tables (rooms 10.5 m² / 3.0 m, maid 5.5 m², kitchen 5.4 m², doors 915/710 mm,
  corridors 1.0 m, stairs: risers 100-180 mm, treads ≥ 280 mm, 1.0 m wide, headroom 2.3 m,
  glazing ≥ 10% of floor area, villa setbacks 3 m on all sides). HouseDiffusion, House-GAN++ and
  Graph2Plan are research-only or unlicensed: read for ideas, not shipped. Layers follow the US
  National CAD Standard names.
- **Architecture as found** ([2d/ARCHITECTURE.md](2d/ARCHITECTURE.md)) with the measured cause of
  each problem you reported.
- **Skill** `.claude/skills/drafting-standards/SKILL.md`.
- **Building model** (mm, 50 mm grid): typed walls, hosted doors and windows, fixtures, stairs, site
  elements; exact PlanJSON 2.0 round trip; PlanTo3D plan made from the model (pool and garden now
  inside the 3D floor; PUJA, BAR keep their types; stairs have flights). The 3D gateway uses it.
- **Areas**: a nandu-like brief (same plot, same rooms, no AI) now plans 3,338 sq ft built-up of
  5,001 sq ft (67%) instead of 1,987 sq ft with a 2,250 sq ft lawn.

## What you must decide (so far)

1. Setbacks: you asked for 3 m front and 1.5 m sides and rear; the Dubai Building Code table for a
   standalone villa says 3 m on every side (1.5 m is an Emirati "Home First" relaxation). The
   defaults follow your instruction; the checker warns below 3 m.
2. With 3 m / 1.5 m setbacks a 50 × 100 ft plot can only be 67% built up, and small plots (for
   example 30 × 45 ft, 2 bedrooms) no longer fit. The generator then says so and suggests smaller
   setbacks ("no setbacks" in the chat works). `FLOORPLAN_SITE_RULES=false` restores whole-plot
   layouts.
3. DWG converter licence (see DEPENDENCIES.md when task 8 is done).
