# Overnight summary (final)

Branch `feat/3d-night`, 45+ commits, nothing pushed or merged. LOG.md has every task with its commit. PlanTo3D changes
are numbered in `services/planto3d/PATCHES.md` (§18-§36 tonight).
Hardware: Apple M1 Pro, 32 GB, 14-core GPU (Metal), macOS 27.0.1, Blender 5.3.0, on AC power.

Budgets used:
- AI calls: 32 of 60. That is 3 for Part A, 26 for the held-out AI reads, 2 for the invented area labels and 1 for the
  AI second look. Cached calls were free.
- Asset downloads: about 5 MB of 3 GB (one CC0 plant model and its textures).
- Render time: about 70 minutes of the 3 hours allowed. No single render ran past 10 minutes (one Cycles benchmark was
  stopped at the cap), with 2-minute cooldowns between renders, all with `nice -n 10`.
- Free disk: 301 GB.

## Stages
| Stage | Status |
|---|---|
| Part A | done (partA_report.md) |
| 1 Measure | done: 200 generated plans (50 held out, never tuned on), scorer, baseline |
| 2 Raise accuracy | mostly done (see below); building type is only a hint |
| 3 Areas | done |
| 4 Guided tour | done |
| 5 Platform | done |
| 6 Speed | done |
| 7 Visual quality | partial: the side facades are still plain |
| 8 Minimap / browser look | minimap done; the enhanced look was tried twice and reverted |
| 9 Rendered tours | done for the pipeline and a test clip; full tours are too slow for this laptop |

## Accuracy on the 50 held-out plans (accuracy.md has every run)
| style | read, before -> now | wall recall | doors found | windows found | room type |
|---|---|---|---|---|---|
| lines (vector) | 100% -> 100% | 37% -> 63% | 4% -> 75% | 71% -> 71% | 73% -> 73% |
| solid (vector) | 100% -> 100% | 30% -> 51% | 4% -> 67% | 59% -> 59% | 59% -> 58% |
| fills (vector) | 100% -> 100% | 40% -> 56% | 14% -> 74% | 67% -> 67% | 68% -> 68% |
| hatched (vector) | 100% -> 100% | 21% -> 35% | 2% -> 58% | 49% -> 49% | 47% -> 46% |
| scans (4 raster styles) | 17-29% -> 83-86% | 3-21% -> 24-41% | 4-8% -> 15-49% | 7-10% -> 23-50% | 6-22% -> 68-81% |
| **all 50** | **60% -> 92%** | **19% -> 42%** | **6% -> 47%** | **31% -> 46%** | **36% -> 69%** |

Wall precision went from 52% to 42%, because the AI reads of scans add walls the reference does not have. Special
areas found went from 21% to 37%, and the building-type guess is right on 58% of plans. These are measured numbers on
held-out plans, not claims about any one drawing.

## What is still inaccurate
- **Scans** depend on the AI reader. Their walls are 24-41% found, and the AI gives no door leaves, so their doors score
  low confidence.
- **Hatched vector walls** are 35% found.
- **OPT 5:** the two ENT.LOBBY rooms are not read. The lobby partitions are missed, so both labels fall into DRG./DIN.
  The AI second look found this.
- **antonovich …fMhH:** its rooms are labelled with numbers that refer to a legend. 12 rooms are built as generic rooms.
- **SF plan:** door 9 is fixed in the detector (82/82 openings when re-read), but the stored job keeps its old plan. That
  is the only failure left in run_all.
- **Building type:** the guess is right on 79% of plans when the reading is perfect, but only about 54% on real reads,
  the same as always answering villa. It is shown, never used.
- **Exteriors:** the side facades are mostly blank walls. The stone plinth helps, but they need real facade design.
- **Test plans:** the generator sometimes puts a lift behind the front door, which seals the house. I left it so the
  held-out set stays fixed.
- reference_review.md lists each reference PDF's checks and confidence.

## Area library (services/planto3d/areas/library.json, git-ignored). **None of these has been reviewed.**
helipad, archery_range, koi_pond, putting_green, horse_stable. They were written by the AI from the labels alone and
passed validation. They are built and walkable: the helipad is raised 0.3 m and the koi pond is kept out of.

## Screenshots and videos (git-ignored, on this machine)
- `docs/overnight/style_compare/`: before/after pairs of the dock house (living room, kitchen, four sides), the four
  sides on one sheet, and the tour engines side by side.
- `docs/overnight/tour_eevee_8s_480p.mp4` and `tour_cycles_3s_480p.mp4`: the benchmark clips.
- The 8 s High tour made by the server pipeline is `services/planto3d/jobs/cccc000000a3/tour_high.mp4`.

## Timings (M1 Pro)
- **Low build of the dock house:** 206 s before, 102 s now, because Low light maps stop at 2048 px. Baking was 93% of
  the time.
- **Low first, then High:** on paranjay-villa you can walk the Low house at 77 s, and High replaces it at 594 s.
- **Model-only build:** 9-14 s for generated plans of 1-3 storeys.
- **AI area classification:** one call, 22 s. **AI second look:** one call, 10 s.

## Renderer benchmark (tour_benchmark.md)
EEVEE takes 2.07 s per frame and Cycles 5.82 s per frame at 480p, so a full 245 s tour needs about 4.2 h with EEVEE
and about 11.9 h with Cycles. The pipeline renders in resumable chunks with cooldowns, and an 8 s, 480p High clip went
through the server in 647 s. EEVEE used to turn white walls blue; that is fixed and now matches Cycles.

## Not verified
- An Ultra (Cycles 1080p) tour through the server. It would take hours; only the 480p benchmark ran.
- A High tour at its real 720p and length.
- Tours on a GPU server, and Node on the server, which the route conversion needs.
- The furniture page with per-person sets inside the real app, as opposed to the gateway tests and the API directly.
- Build emails over real SMTP: only the logging mailer and a fake mailer were tested.
- Any plan outside the 200 generated plans, the reference PDFs and the stored jobs.

## For you to decide
1. **AGENTS.md rule 4** says the backend never builds meshes, but PlanTo3D builds them in Blender. I wrote this down as
   your Phase 1 decision. Please confirm.
2. **Per-person furniture** works. Should `PLAN3D_ALLOW_FURNITURE_CHANGES` be turned on?
3. **The AI second look** (`PLAN3D_AI_VERIFY`) costs one call per plan, about $0.03-0.05 with Opus 5.5. It found real
   misses on OPT 5. Should it be on by default?
4. **AI area specs:** may they be used before review? They are used now and marked unreviewed.
5. **Rendered tours:** a short default (about 60 s of the main rooms), a GPU server for full tours, or both?
6. **Numbered room legends:** may the AI reader's prompt change to map legend numbers to names? That needs a prompt
   change and live calls.
7. **The browser look:** ambient occlusion did not help on baked light. Do you want another enhancement, such as bloom
   on lamps or a better sky?
8. **Test job folders:** I created cccc000000a3 (the dock house copy) and f03a155f32ec (villa High test) under
   `services/planto3d/jobs`. They can be deleted when you no longer need them; I did not delete anything.
