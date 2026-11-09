# 04 Parsing module

Location: `backend/app/modules/parsing/`. This module converts an uploaded architectural floor plan (PDF or image) into a **plan JSON** using a multimodal Vision LLM.

## Architecture

```
PDF/Image -> pdf_to_image.py -> llm_parser.py (Vision LLM) -> validate.py -> PlanJSON
```

1. **Direct Vision Extraction**: Instead of fragile OpenCV edge detection or heavy ML segmentation models, the page is rendered as a high-resolution image and parsed directly by a multimodal LLM (Gemini / GPT-4o / Claude).
2. **Single Structured Output**: The LLM is instructed with a strict prompt and JSON schema to extract wall coordinates, thickness, door/window openings, room names, and dimensions.
3. **Validation & Sanitation**: `validate.py` verifies the LLM output against the Pydantic `PlanJSON` schema, ensures coordinates are numeric, and calculates room floor areas.
4. **Feeds 3D & Estimation**: The validated `PlanJSON` is stored in the database (`plan_versions.plan_json`), where Three.js uses it to render the 3D scene, and `sheets/calculator.py` uses room areas and wall dimensions to compute material costs.

## Files

| File | Purpose |
|---|---|
| `router.py` | HTTP endpoints (`POST /parsing/start`, `GET /parsing/{job_id}/status`) to initiate and track parsing jobs. |
| `service.py` | Orchestrator called by Celery workers or other modules: loads the file, renders the image, calls the LLM, validates, and saves. |
| `schemas.py` | Pydantic request and response models (`ParseRequest`, `ParseResponse`). |
| `models.py` | Database models owned by the parsing module (if needed). |
| `pdf_to_image.py` | Uses PyMuPDF (`fitz`) to convert the uploaded PDF page into an optimized, high-resolution image for multimodal LLM processing. |
| `llm_parser.py` | Prompts the multimodal LLM with the floor-plan image and architectural instructions to output the structured JSON. |
| `validate.py` | Validates and sanitizes the LLM output against `PlanJSON`, fixing missing fields or incomplete polygons. |

## Output

A standard `PlanJSON` (see [05-data-and-storage.md](05-data-and-storage.md)) with:
- `walls`: start and end coordinates `[x, y]` and thickness in meters.
- `openings`: doors and windows with wall ID, offset, width, and height.
- `rooms`: closed room polygons and room labels (e.g. "Living Room", "Kitchen").
- `confidence`: confidence scores per element.
