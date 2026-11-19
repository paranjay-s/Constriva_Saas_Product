# Overnight summary (updated at the end of every stage)

Hardware: Apple M1 Pro, 32 GB RAM, 14-core GPU (Metal), macOS 27.0.1, Blender 5.3.0.
Branch `feat/3d-night`, nothing pushed. Task-by-task record with commit hashes: LOG.md. AI calls used: 31 of 60.

## Part A (done)
See partA_report.md. Pools, docks, water and 30 room types are built. There is one room vocabulary. Open plans are
furnished per zone, and a "Needs checking" list shows what to verify. Raster plans still depend on the AI reader.

## Stages
| Stage | Status |
|---|---|
| 1 Measure | done: 200 generated plans (50 held out), scorer, baseline in accuracy.md |
| 2 Raise accuracy | partial (see below) |
| 3 Areas | done (the AI spec library is unreviewed) |
| 4 Guided tour | done |
| 5 Platform | partial: per-user furniture not started |
| 6 Speed | not started |
| 7 Visual quality | not started |
| 8 Minimap / browser | not started |
| 9 Rendered tours | not started |

## Accuracy on the 50 held-out plans (never used for tuning)
| | baseline | now |
|---|---|---|
| plans read | 60% | 92% (detector 24, AI 22, none 4) |
| wall recall / precision | 19% / 52% | 42% / 42% |
| doors found | 6% | 47% |
| windows found | 31% | 46% |
| room type right | 36% | 69% |
| special areas found | 21% | 37% |

The table by drawing style is in accuracy.md. The vector styles score best (walls 35-63%, doors 58-75%). The scanned
styles depend on the AI reader (walls 24-41%, doors 15-49%). Two things changed the numbers: wall pieces on one line
now belong to one plan, and every raster plan got an AI read (16 of the 31 calls). These are measured numbers, not
accuracy claims. Precision fell from 52% to 42% because the AI reads add walls the reference does not have.

Also checked in Stage 2:
- A door with a parallel wall less than 2 ft beside it is now extended through that wall. This fixed SF door 9 (82/82
  opening checks on the re-detected plan); OPT 5 and paranjay-villa are unchanged.
- Sideways sheets (a rotate flag, or the drawing turned 90°) read as well as upright ones on 6 vector plans. No change
  was needed.
- When the AI is off or the reader breaks, the review page still opens with the plan for tracing (tested).
- Still to do: building type and storey count checks, a verification pass, source and confidence per element, and a
  run over all reference PDFs listing what is still wrong.

## Stage 3: areas
- Built-in builders: pool, plunge pool, jacuzzi, fountain with jet, water body, dock and jetty (deck, posts, cleats,
  edge lights), parking bays and carport with cars, tennis, padel and basketball courts, garden and lift.
- Unknown areas: one cached AI call per plan picks one of our room types (applied at confidence 0.6 or more) or writes
  a spec in a fixed schema (surface, edge, height, walkable, markings, objects). PlanTo3D validates every spec before
  keeping it; a refused spec builds a generic zone. These areas are orange on the maps.
- Live check with invented labels (2 calls; the first returned empty specs until the schema was written out in full):
  helipad, archery range, koi pond, putting green and horse stable all got valid specs. Sauna was typed "room" (0.60).
  Built model-only in 10 s: the walker steps up onto the 0.3 m helipad, is kept out of the recessed koi pond, and the
  tour visits 14 of 14 rooms and areas.
- **Library entries not yet reviewed** (services/planto3d/areas/library.json, git-ignored): helipad, archery_range,
  koi_pond, putting_green, horse_stable.

## Stage 4: guided tour
- A "Guided tour" button in the walkthrough walks at 1 m/s with eased turns and pauses. Any key, mouse button or touch
  takes control back.
- The tour starts at the door that opens outside the house. When part of the house cannot be walked to (a wing reached
  only through a closed court, or a door the reader missed), it jumps there instead of skipping it.
- tests/test_tour.mjs passes on 28 of 28 plans (20 generated plans of 1-3 storeys and 8 stored jobs). The 20 generated
  plans needed 5 jumps for 362 room visits. The stored jobs needed 0-4 jumps each (the dock house 4).

## Stage 5: platform
- Time left: the build now announces its light-map sizes, and the estimate comes from them. It is calibrated per
  machine after every build. Three of five measured builds were within 5%. The dock and pool houses were 33-52% over,
  but their map sizes were guessed, not read.
- Emails: one per finished or failed long build. Settings are `EMAIL_SMTP_*` and `EMAIL_FROM`; while unset, emails
  are only logged. There is an on/off switch, and the 3D home page lists finished builds with links.
- Embed tokens: read-only and for one job. They are redacted from access logs, sent with `Cache-Control: private` and
  no-referrer, and refreshed at 75% of their lifetime without reloading the page.
- AGENTS.md has a section on the 3D module.
- Not started: per-user custom furniture (`PLAN3D_ALLOW_FURNITURE_CHANGES` stays false).

## Tests at the end of stages 3-5
Backend 1127 passed, 3 skipped. Frontend 254 passed. PlanTo3D 56 checks ok. The only failure is SF door 9 in the
stored job, which still holds the plan detected before the fix.

## For you to decide
- AGENTS.md rule 4 says the backend never builds meshes, but PlanTo3D builds them in Blender. I wrote this down as your
  decision from Phase 1. Please confirm.
- Whether the AI-written area specs may be used before someone reviews them (they are used now and marked unreviewed).
- The test-plan generator sometimes puts a lift right behind the front door, which seals the house. This is a flaw in
  the test data, not in the reader. I have not changed the generator, so the held-out set stays fixed.
