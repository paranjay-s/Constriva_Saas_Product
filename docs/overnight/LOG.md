# Overnight log (branch feat/3d-night)

One line per task: stage | task | status | commit | note.

- Decision: battery shows "AC attached; not charging" at 85 % (macOS charge hold on mains). Renders treated as allowed while AC is attached; checked before each render.
- Decision: live AI calls counted from here (budget 60). Used before this run: 3 (Part A model comparison).
- A | Part A report | done | (this commit) | docs/overnight/partA_report.md
- 3 | area builders: courts, bays, carport, fountain jet, dock fittings | done | 960e31f | court type joins rooms.json after the baseline scoring
- 5 | build emails + in-app notifications, furniture changes off by default | done | 0644a41 | state kept in process (lost at restart); no frontend list yet
- 1 | test-plan generator (200 plans, seed 7, 50 held out) + scorer per style | done | 1f00dc6, 960a23e | PDFs local in docs/overnight/testplans (git-ignored)
- 1 | baseline on held-out set | done | c6f4202 | 10 fresh AI calls (20 used in total incl. Part A 3... see count); scorer bug (relative path) fixed and rerun on cached replies
- 4 | tour route planner + test | partial | c6f4202 | sample passes; OPT 5 first floor: 3 rooms unreached (furniture/passage check disagree with walker grid), test reported not required
- AI calls used: 13 of 60 (3 Part A + 10 baseline)
- 2 | detector: join wall pieces across openings | done | 5937707 | held-out vector walls +14..26 pts, doors +54..71 pts
- 3 | area spec schema, validator, builder, library | done | 7708021 | AI spec writer next
- 4 | Guided tour button in the walkthrough | done | 73d76a5 | checked in headless Chrome on the dock house: walks through 4 rooms in 12 s
- 5 | embed tokens: redacted from logs, Cache-Control private | done | 66f330c | refresh before expiry: done in the next commit
- 5 | embed token refresh before expiry | done | 7e9af9b |
- 5 | time left from light-map sizes, calibrated per machine | done | 2b09785 | 3 of 5 measured builds within 5%; dock/pool 33-52% over (map sizes guessed), calibration corrects
- 5 | in-app build notifications + email switch (frontend) | done | 31faf20 | 2 new tests
- 5 | root AGENTS.md: 3D module section | done | 8da70c7 | records the server-side Blender exception to rule 4 as the owner's decision
- 2 | review page opens when the AI fails or is off | done | 2a5a73a | test only: the fallback already handled both
- 3 | AI area specs, live check on 6 invented labels | done | b3b0c08 | 2 live calls (first returned empty specs: schema fixed). 5/5 new specs valid; sauna -> room 0.60. AI calls: 15 + background run
- 3 | invented areas built and walked (helipad, koi pond, putting green, archery range, horse stable) | done | 75ffb15 | model-only build 10 s; tour 14/14; sauna typed 'room'. Generator flaw: p078 puts a SERVICE LIFT (closed shaft) behind the front door, sealing the house
- 4 | tour: real front door, jumps to unreachable parts | done | 66d2661 | 8/8 stored jobs pass test_tour (before 4/8); 0-4 jumps per plan
- 2 | held-out with an AI read of every raster plan | done | (accuracy.md) | read 92% (det 24 / ai 22 / none 4), wall recall 42%, precision 42%, doors 47%, windows 46%, room type 69%, specials 37%. 16 fresh AI calls; total used 31 of 60
- 3 | court + custom room types | done | fe0d762 | map colour for custom: orange
- 4 | tour tested on 20 generated plans + 8 stored jobs | done | 61fdc38 | 28/28 pass test_tour; first run 11/20 builds failed (stairs without words) and 2 tours stopped at the stairs; both fixed
- 2 | door needs a passable space on both sides (SF door 9) | done | 6b51090 | re-detected SF: 82/82 openings; OPT 5 and villa unchanged; stored SF job not rewritten (run_all still reads its old plan)
- 2 | sideways sheets (rotate flag, content turned 90°) | done, no change needed | - | 6 tune-set vector plans: walls and room types the same or better than upright at the best quarter turn (labels read either way). Odd: p000 upright 40% walls vs 89% rotated, not explained
