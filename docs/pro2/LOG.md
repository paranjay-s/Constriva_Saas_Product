# feat/pro_2 run log

One line per task: section | task | status | commit | note. Live AI calls and render minutes are
counted at the end of the lines that used them.

| Section | Task | Status | Commit | Note |
|---|---|---|---|---|
| A1 | 1 diagnose both failures (FAILURES.md) | done | 6311705 | 10 live AI calls (recorded) |
| A1 | 2 the person's numbers win over the band | done | 22eb0f5 | |
| A1 | 3 setbacks default 0, set_setbacks chat edit | done | b2da802 | floorplan suite 527/528 before the one test fix, then green |
| A1 | 4 weighted soft constraints in CP-SAT | done | fd5f8ec | hard mode unchanged (golden test) |
| A1 | 5 relaxation ladder (weighted, a-f) | done | b61d03c | ladder steps logged per run (relax_log) |
| A1 | 6 a plan is always delivered; adjustments listed in chat | done | b61d03c | feasibility shortfall no longer refuses |
| A1 | 7 brief understanding (spoken words, unclear numbers, rule binding) | done | 1e13b22 | 4 live AI calls (total 14) |
| A2 | 1 presentation renderer | done | f3fb60c | |
| A2 | 2 view toggle, downloads follow it, presentation PDF signed | done | f3fb60c | |
| A2 | 3 engineering snapshot byte-identical (PDF, SVG, PNG, DXF) | done | ef0faba+f3fb60c | 20 files, run stamps blanked |
| A2 | 4 side-by-side samples | done | f3fb60c | docs/pro2/2d/presentation |
| A1 | 8 tests: both briefs, golden working brief, 50 random briefs | done | 8be4942 | 50/50 plans; first pass 42, weighted 5, b 1, fallback 2 |
| B | 1 cause of the loop fixed | done | 821a971 | names are not unique; picks now carry the room's position |
| B | 2 clickable labelled choices + All of them | done | 821a971 | |
| B | 3 typed answers by number, size, name, several | done | 821a971 | |
| B | 4 never the same question twice; unmatched -> buttons + why | done | 821a971 | |
| B | 5 tests incl. the exact looping sequence | done | 821a971 | material suite 69 passed |
| A | end-of-section suites: backend 1350 passed / 1 failed (fixed in b3431c3) / 3 skipped; floorplan 564 passed after the fix | done | b3431c3 | coverage band without setbacks |
| C2 | 1 hollow-wall (two thin lines) mask for low-resolution scans | skipped | - | two attempts: lines at 72 dpi too faint and broken; beds and stairs close into blocks; no closed rooms. Reverted. Fresh plan stays on the AI reader's walls |
| C3 | 1 curved walls, round rooms, spiral stairs | done | 2c7c2e0 | DXF/IFC export of arcs not done; the AI reader (PlanJSON) has no arcs |
| C1 | 1 measure space (SPACE.md) | done | b37f2f2 | fresh plan 2/13 rooms within 5% of labels (reading); OPT 5 18/30 |
| C1 | 2 heights, FOV toggle, lens, furniture, finishes, light, mirrors | done | fddcac2 | taller living/majlis as a separate height not done |
| C1 | 3 before/after three rooms Low and High | done | b37f2f2 | render 15.8 min so far |
| C2 | 4 drawing-only round trip to 98% doors and windows | partial | 03734b8 | doors 85.2% (was 82.6%), windows 96.4% (was 91.5%), walls 99.9%; 98% not met; missed doors sit at wall ends beside cross walls; swing-door attempt x2 reverted; engineering drawing unchanged |
| C3 | 2 design details in the room kits | done | 1ba08c5 | chandelier hanging fixed in a later commit |
| C3 | 4 reference vs Low vs High sheets | done | 3a12afa | sheets on disk only |
| C3 | 3 Unreal stills via MRQ command line | done | 4fce861 | 2 stills in 2.5 min of the 15-min cap; picture mirrored (camera Y flip) and overexposed; server still uses the old capture; Blender stays default |
| C2 | 2 scans: scan reader walls + AI names/types | done | 81ac7ca | room types 11-52% -> 32-61%; AI alone 85-92% |
| C2 | 3 model comparison opus-5-5 vs fable-5-2 | done | 81ac7ca | fable walls 95%/89%, doors 90%, windows 93% vs opus 69/63/65/67; $0.84 vs $0.22 per plan; 33 live calls |
| C2 | 1 wrong doors and walls on the fresh plan | partial | - | causes listed in SPACE.md/ACCURACY.md (72 dpi hollow walls; AI walls rough); hollow-wall fix reverted after 2 attempts |
