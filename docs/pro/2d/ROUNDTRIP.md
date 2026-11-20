# Round trip: generated plans read back by our 3D and BOQ readers

Script: `tools/roundtrip/run_roundtrip.py`. Scoring: `backend/app/modules/plan3d/compare.py`.
Raw results: [roundtrip_results.json](roundtrip_results.json). Run 2026-11-20 on the final
PART 1 code, 20 briefs from 1,500 to 12,000 sq ft (1-6 bedrooms, every road side, feet and
metres, pools, majlis, maid's rooms...), generated without the AI.

## With the embedded model (signed building model in the PDF)

| Reader | Result |
|---|---|
| 3D gateway (`signed_plan_for_pdf` -> PlanTo3D plan) | **exactly equal** to the model on 18 of 18 plans |
| BOQ (`default_pdf_parser` -> PlanJSON 2.0) | **exactly equal** to the model on 18 of 18 plans |

Two of the 20 briefs (30 x 50 ft and 35 x 60 ft with two bedrooms) did not generate: with the
default setbacks (3 m front, 1.5 m sides and rear) and the Dubai Building Code minimum of 3.0 m
net for bedrooms and living spaces they do not fit. The generator says so and suggests smaller
setbacks.

## With the attachment removed (the drawing only)

Recall = share of the truth found; precision = share of what was found that is true. Walls are
scored by area (truth openings left out); doors and windows by matched centres (within 0.5 m);
rooms by a read room's centre inside the true room.

| Reader | Plans | Walls R / P | Doors R / P | Windows R / P | Rooms R / P | Room types |
|---|---|---|---|---|---|---|
| Vector detector (PlanTo3D `detect.py`) | 18 | 95.9% / 96.2% | 82.6% / 89.4% | 91.5% / 95.6% | 100.0% / 97.5% | 100.0% |
| OpenCV reader (new, `plan3d/raster_reader.py`) | 18 | 84.8% / 74.2% | 45.4% / 37.4% | 62.1% / 62.3% | 65.6% / 89.7% | 52.4% |
| AI reader (plan parser, gemini-3.5-flash) | 8 of 16 tried | 26-72% on 4 plans, no walls on 4 | 0-43% | 0-22% | 71-100% where walls came back | 57-100% |

**The 98% target is not met** for doors and windows by any reader, nor for walls by the OpenCV
and AI readers. Measured findings:

- Vector detector: walls, rooms and room types are at or near target. The doors it misses sit
  in tight spots (doors into a narrow lobby, doors beside the stair, suite doors in 100 mm
  partitions). Two drawing-convention changes were tried and measured, and neither helped:
  150 mm partitions (no change) and a 20 cm nib beside every door (doors 82.2%, walls fell to
  97.2%); both were reverted. Hiding furniture made no difference either. The next step is in
  the detector's door logic (PART 2, B).
- OpenCV reader: written in this task (no raster reader existed). It finds walls from the poché,
  openings as breaks along each wall band with drawn evidence (window lines, a door arc or
  sliding panels), rooms by flood fill, names from the text layer. Door classification and
  rooms that merge through a missed door are its weak points.
- AI reader: the plan parser asks the model for geometry, which project rule 2 (AGENTS.md)
  says it should not be trusted for; on our drawings it returned no walls for half the plans.
  The AI service also rate-limited the run (HTTP 429): 8 of 16 attempts failed after retries,
  and the run was stopped to protect the 100-call budget.

Because the embedded model makes generated PDFs exact for both readers, the drawing-only path
matters only when someone strips the attachment or re-saves the PDF through another program.
