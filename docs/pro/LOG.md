# Pro run log

One line per task: part, task, status (done, partial, skipped), commit, reason if not done.
Started 2026-11-20 on branch `feat/pro` (from `feat/merged` d08ad48).

| Part | Task | Status | Commit | Note |
|---|---|---|---|---|
| 0 | Branch, log, summary | done | (this commit) | |
| 1 | 1 Research | done | e6bd10d | |
| 1 | 2 Architecture | done | 4389671 | |
| 1 | 3 Skill drafting-standards | done | 1f8d2d8 | written with skill-creator's guidance; its eval loop skipped (needs parallel subagents and owner review) |
| 1 | 4 Building model, PlanJSON 2.0 and PlanTo3D exports | done | 2fe5e23 | OR-Tools CP-SAT already the solver; 417 generator tests pass |
| 1 | 5 Areas, setbacks, built-up band | done | 2f66a65 | nandu-like brief: 1,987 -> 3,338 sq ft built-up (67%); 50x100 ft plots reach 67% max with 3/1.5 m setbacks |
| 1 | 6 Chat and solver (rules, re-solve, conflicts, neutral model) | done | e518b4b | one older edit test is timing-sensitive under load (passed on rerun) |
| 1 | 7 CAD drawing, muted, A3/A1 | done | eb888f2 | old svg_renderer kept only for the old DXF until task 8 |
| 1 | 8 PDF/SVG/PNG, DXF, IFC, DWG, signed model | done | 6dd1058 | DWG writer is the ODA converter (licence: owner decision); 518 tests pass |
| 1 | 9 Engineering checks, RULES.md | done | adaa7e9 | nandu brief: 0 critical, warnings for glazing, triangle, coverage 64.5%, DBC setbacks |
| 1 | 10 Round trip 3D/BOQ, 20 plans | partial | 6ec246b | exact with model 18/18; drawing-only detector doors 82.6%, windows 91.5%, OpenCV and AI below 98%; AI run rate-limited (about 32 live calls used) |
| 1 | 11 Samples 1,500-8,000 sq ft + nandu | done | 6ec246b | 1,500 sq ft sample is 1 bedroom (2 do not fit the default setbacks); nandu and contact sheet kept local (client content) |
| 1 | 12 All suites and build | done | 0289d48 | backend 1239 passed / 3 skipped; frontend 294 passed; build ok. Live nandu chat test blocked by HTTP 429 (deterministic test passes) |
| 2 | A1-A3 Diagnosis, pool line, kits | done | e41fc2d | Blender time so far about 1 min (diagnostic builds without bake) |
| 2 | B1-B2, B4-B5 Scan reader, research, measured | done | 1c00527 | held-out raster: precision 17% -> 66%, recall 21-64% per style with no AI call; 37% of labelled rooms within 2% (the rest are cut wrongly, listed on the review page). A held-set run made about 12 rate-limited live AI calls through a stale cache check (fixed): about 47 of 100 used |
| 2 | B3 Model comparison | skipped | - | no held-out raster plan has readings by both models and the Gemini key answered 429 to fresh calls; default unchanged; command written in RESEARCH.md |
| 2 | C Low quality, Medium removed, size errors >5% | done | 993a8d5 | draft builds 10 s; 1000206523: 6 rooms flagged 6-66%. PlanTo3D suite: tour (not required) and one opening check on an old saved build (0bdaca14d7bf) fail, as before this run |
| 2 | D Room kits | partial | cc7905c | dishwasher, ovens, lift cabins (passenger/service), pool ladder added; puja and qibla-facing prayer kept; curved/circular rooms need an arc shape in the plan format (owner decision). Blender time so far about 3 min |
| 2 | E High quality (look, stills, elevations, fast tour, 1080p tours, UAE front, gallery, email, AI polish, engines) | partial | 7f0c796, b2feea7, db4b2d2, 2ec22c4 | Blender stills measured (108 s per room on the M1 Pro); Unreal import works but no still after two attempts (editor quits before the capture); Twinmotion research only; render time used about 42 min |
| 2 | F Reference vs Low vs High | done | 27de1f0 | 8 room types; sheets on disk only (your reference pictures) |
| 3 | Saved BOQ history + dashboard | done | 22d5cb8 | migration written, not applied (SQL in SUMMARY) |
| 3 | Landing images | done | 93bc621 | auth hero -38 %; tour frames left (2-7 % only) |
| 3 | Dockerfiles, deploy-3d.md, asset library script | done | e22f965 | images not built here (no Docker on this Mac) |
| 2 | G Suites and SUMMARY | done | - | backend 1263 passed / 3 skipped; frontend 298 passed, build ok; PlanTo3D as before |
