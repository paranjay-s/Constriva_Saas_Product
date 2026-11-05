# 04 Parsing module

Location: `backend/app/modules/parsing/`. This module converts an uploaded PDF into a **plan JSON**. It is the hardest part of the product, so it is built to work on PDFs in many formats instead of one.

## Design

```
PDF -> pdf_inspect -> extractors (several) -> geometry cleanup -> scale -> validate -> best result -> plan JSON
```

1. Every extractor implements the same interface and outputs the same plan JSON.
2. The pipeline runs the extractors that apply, scores each result, and keeps the best one.
3. No extractor is required to succeed. If all fail or confidence is low, the user fixes the plan in the editor, or traces walls manually.
4. The LLM is used for meaning only (page choice, room names, scale text). It never supplies coordinates.

## Files

| File | Purpose |
|---|---|
| `router.py` | Endpoints to start parsing a file and to read the result. Starting a parse creates a job and enqueues a Celery task. |
| `service.py` | Entry point used by the worker task and by other modules. Calls `pipeline.py`. |
| `schemas.py` | Request and response models (parse options, job info). The plan model itself lives in `modules/plans/schemas.py`. |
| `pdf_inspect.py` | Looks at the PDF: page count, whether a page is vector or scanned, and which page is the floor plan (with LLM help if there are several). |
| `pipeline.py` | Orchestrator. Chooses extractors, runs them, applies geometry cleanup, scale and validation, picks the best result, reports progress. |
| `scale.py` | Finds real-world scale: from scale text such as `1:100`, from dimension labels, or from a user-provided reference. Records `scale_source`. |
| `units.py` | Parses dimension strings such as `12'8 X 11'`, `3'4 WD.` and metric labels into metres. |
| `validate.py` | Scores a result: rooms closed, walls connected, measured room sizes versus printed sizes, plausible areas. Produces per-element `confidence`. |

## `extractors/`

| File | Purpose |
|---|---|
| `base.py` | The `Extractor` interface: `can_handle(pdf_info) -> score` and `extract(pdf, page) -> PlanJSON`. |
| `vector.py` | Reads vector drawing paths (PyMuPDF `get_drawings()`) and decides which are walls, doors and windows from how they look: stroke width, fill, length, orientation, parallel partners, connections. CAD layer names are one optional input feature, never a requirement. |
| `raster.py` | Renders the page to an image and finds walls, doors and windows with image processing and a segmentation model, then vectorises the masks. Works on scanned PDFs. |
| `semantics.py` | Uses a vision LLM to read room names, scale text and printed dimensions, and to sanity-check the result. Output is labels and numbers, not coordinates. |

To add a new extraction method, add a file implementing `Extractor` and register it in `pipeline.py`. Nothing else changes.

## `geometry/`

Deterministic helpers shared by all extractors, so cleanup does not depend on where the lines came from.

| File | Purpose |
|---|---|
| `snap.py` | Snaps nearly-touching endpoints together, straightens near-axis-aligned lines, removes duplicates. |
| `walls.py` | Pairs parallel lines into wall centrelines with thickness, merges collinear segments. |
| `rooms.py` | Builds closed room polygons from wall centrelines (Shapely `polygonize`) and attaches labels to the polygon that contains them. |
| `openings.py` | Finds gaps and door/window marks along walls and records them as openings with offset, width and height. |

## Output

A plan JSON (see [05-data-and-storage.md](05-data-and-storage.md)) with:

- `walls`, `openings`, `rooms` in metres,
- `scale_source` (`scale_text`, `dimension_label`, `user_reference` or `assumed`),
- `confidence` per element, which drives the highlighting in the editor.

The task saves it as a new plan version with `origin = "extracted"`.

## Testing

Put sample PDFs in `backend/tests/fixtures/pdfs/` with a hand-checked expected plan in `fixtures/plans/`. Tests compare room count, room areas and wall lengths within tolerances. When a real drawing fails, add it as a fixture before fixing the code.

