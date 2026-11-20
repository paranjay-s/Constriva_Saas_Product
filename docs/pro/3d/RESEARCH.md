# Reading uploaded plans: research (PART 2, B1)

Written 2026-11-20. Repositories were cloned into `tools/vendor-eval/` (git-ignored) to read their
licences; nothing from a non-commercial source is shipped.

## What works where

| Input | What works | Why |
|---|---|---|
| CAD-exported vector PDF | geometric reading of the vector paths: wall pairs of parallel lines or filled bands, door arcs at gaps, glazing lines in gaps, flood-filled rooms named by their text, scale from size labels | exact coordinates are in the file; no learning needed (PlanTo3D's `detect.py` does this) |
| Generated PDF from our generator | the signed building model attached to the PDF | exact (PART 1) |
| Scan, photo, image-only PDF | classic image processing for walls (thresholds, morphology, line runs) plus OCR for names and sizes, scale fitted to the size labels; a segmentation model where licensing allows | no vector data; text must be read from pixels |
| Anything | an AI vision model for meaning only: which page, room names and types, scale text, unknown areas, a second look | project rule 2 (AGENTS.md): the AI never supplies geometry; measured in PART 1 task 10, the AI reader returned no walls on half our generated plans |

## Open-source projects and licences

| Project | What it is | Licence | Usable by us |
|---|---|---|---|
| [art-programmer/FloorplanTransformation](https://github.com/art-programmer/FloorplanTransformation) (Raster-to-Vector, ICCV 2017) | CNN junction heatmaps + integer programming to vector walls | MIT (code); trained on a LIFULL dataset under its own terms; no shippable weights | ideas: junction-based wall graph, integer-programming clean-up (our CP-SAT experience applies) |
| [CubiCasa/CubiCasa5k](https://github.com/CubiCasa/CubiCasa5k) | 5,000 annotated plans and a multi-task segmentation model | CC BY-NC 4.0 | no (non-commercial); usable only as a private benchmark |
| [zlzeng/DeepFloorplan](https://github.com/zlzeng/DeepFloorplan) | room-boundary and room-type segmentation | GPL-3.0; trained on R2V and R3D data | no in the product; at most as a separate-process experiment |
| [MLSTRUCT/MLStructFP](https://github.com/MLSTRUCT/MLStructFP) | structural floor plan dataset tools | MIT, archived 2026-04-29 | dataset licence must be checked before any training |
| [RasterScan/Floor-Plan-Recognition](https://github.com/RasterScan/Floor-Plan-Recognition) | Docker service | not open source (licence sold) | no |
| [RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR) | PaddleOCR's detection and recognition models through ONNX Runtime | Apache-2.0 (models Apache-2.0) | **yes: chosen OCR** (installs on Python 3.14, no PaddlePaddle needed, 2.3 s on an A4 scan) |
| [mindee/doctr](https://github.com/mindee/doctr) | OCR (detection + recognition) | Apache-2.0 | yes, the alternative if RapidOCR falls short |
| Tesseract | classic OCR | Apache-2.0 | yes, weaker on rotated and small plan text |

## Pipeline built (B2)

1. A PDF from our generator with a valid signed model: the model is used, nothing is read.
2. A vector PDF: PlanTo3D's detector (unchanged path).
3. A scan: `backend/app/modules/plan3d/scan_reader.py` (deskew, OCR, text blanked, several wall
   masks for solid, line, hatched and filled drawing styles, the mask whose rooms hold the most
   OCR'd names wins, scale fitted to every labelled size, rooms more than 2 % from their label
   listed) and, when it does not read a plausible plan, the AI reader as before.
4. The gateway's AI steps for meaning: unknown labels classified once per plan (`areas.py`),
   the optional second look (`verify.py`), gap filling as suggestions (`gapfill.py`).
5. Everything uncertain goes to the review page notes.

## Measured (B4, B5)

Held-out generated plans (`docs/overnight/testplans`, 50 plans never used for tuning, 8 drawing
styles; `tools/testplans/score_all.py --set held --scan --ai 0`). Vector styles are read by the
detector and did not change; the raster (scanned) styles are what B2 is about.

**Before** (detector, then cached AI readings only): raster plans read 17-29%, wall recall 3-21%.
**Before, with an AI read of every raster plan** (16 live calls, 2026-11 overnight run): raster
wall recall 24-41%, precision 20-39%, room types 68-81%.

**After** (detector, then the scan reader; no AI call at all):

| style | plans | read | detector / scan / ai / none | wall recall | wall precision | doors found | windows found | room type | specials | storeys | building type |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fills | 6 | 100% | 6 / 0 / 0 / 0 | 100% | 99% | 99% | 99% | 86% | 47% | 100% | 50% |
| hatched | 6 | 100% | 6 / 0 / 0 / 0 | 100% | 99% | 99% | 100% | 82% | 55% | 100% | 50% |
| lines | 6 | 100% | 6 / 0 / 0 / 0 | 100% | 99% | 98% | 100% | 83% | 36% | 100% | 50% |
| raster_fills | 7 | 86% | 0 / 6 / 0 / 1 | 28% | 42% | 29% | 10% | 11% | 10% | 86% | 57% |
| raster_hatched | 7 | 86% | 0 / 6 / 0 / 1 | 21% | 20% | 16% | 3% | 27% | 10% | 86% | 86% |
| raster_lines | 6 | 67% | 0 / 4 / 0 / 2 | 37% | 65% | 20% | 0% | 21% | 18% | 67% | 50% |
| raster_solid | 6 | 83% | 0 / 5 / 0 / 1 | 64% | 70% | 80% | 37% | 52% | 20% | 67% | 50% |
| solid | 6 | 100% | 6 / 0 / 0 / 0 | 100% | 99% | 100% | 100% | 83% | 43% | 100% | 83% |
| ALL | 50 | 90% | 24 / 21 / 0 / 5 | 63% | 66% | 61% | 51% | 51% | 29% | 88% | 60% |

| raster style | wall recall before (AI) / after (scan) | wall precision before / after | storeys before / after |
|---|---|---|---|
| raster_fills | 38% / 28% | 35% / 42% | 86% / 86% |
| raster_hatched | 41% / 21% | 39% / 20% | 86% / 86% |
| raster_lines | 33% / 37% | 31% / 65% | 83% / 67% |
| raster_solid | 24% / 64% | 20% / 70% | 83% / 67% |

What this says, honestly:

- The scan reader is bimodal: on 9 of 25 raster plans it reads walls at 80-100% recall with
  60-99% precision; on the others it cuts rooms wrongly (hatched walls and coloured fills are the
  hard cases). The AI reader is more even but never as exact. Room types are worse with the scan
  reader (11-52% against 68-81%) because a wrongly cut room is a wrongly typed room; the names
  themselves are matched with near spellings (rooms.json).
- **Scale (B4)**: 161 rooms in the scan readings carry a size label. 59 (37%) are within 2% of
  their label after the fit, 62 (39%) within 5%: a room that is cut right is within 2%; the
  others are segmentation errors, not scale errors. Every room more than 2% from its label is
  listed on the review page ("Rooms more than 2% from their label").
- In the product the scan reader is used only when it finds at least 3 named rooms; otherwise the
  AI reader runs as before (fallback.py). It costs 2-12 s and no AI call.

## Model comparison (B3)

Not run. It needs the same raster plans read by the configured model (gemini-3.5-flash) and by the
strongest available one (Claude Opus 5.5, of which 72 cached readings exist, all of tuning plans);
no held-out raster plan has readings by both, and the configured Gemini key answered HTTP 429 to
every fresh call during this run. The default model is unchanged. To run it later:
`score_all.py --set held --ai 25` once with each `PLAN_PARSER_LLM_MODEL`.
