# 04 Parsing module

Location: `backend/app/modules/parsing/`. This module turns an uploaded floor plan PDF into a **PlanJSON**. The same schema comes out whichever LLM is configured, and the same PDF always gives the same PlanJSON.

```python
from app.modules.parsing.llm_parser import parse_plan_pdf

plan = parse_plan_pdf(pdf_bytes)   # a validated PlanJSON 2.0 dict, or a PlanParseError
```

## Pipeline

```
PDF -> pdf_input -> LLM call -> JSON extraction -> draft validation -> repair (up to 2) -> normaliser -> PlanJSON validation
          |                                                                                   |
          +------------------------- plan cache (sha256 + versions) --------------------------+
```

1. **Input** (`pdf_input.py`). Each page is rendered to PNG at a fixed 300 DPI. Sheets larger than A3 are scaled down by a rule that depends only on the page size, so the long side stays within 5000 px. The PDF's own text is read too, one block per line in reading order. This input is the same for every provider. Scanned PDFs have no text layer and send images only. A PDF whose pages are all blank is rejected here and never reaches a model.
2. **Model call**. One `JSONLLMClient.generate_json(system_prompt, images, text, json_schema)` call at temperature 0. The prompt is the single versioned file `ai/prompts/parsing/plan_parser.md`.
3. **JSON extraction**. The reply is parsed as one JSON object (a bare object, a fenced one, or one with prose around it).
4. **Draft validation** (`llm_schema.py`). The reply must fit `LLMPlanDraft` and pass the semantic checks: coordinates are real numbers, every opening sits on a wall that exists, every room outline encloses an area, the lowest floor has enough rooms, and no placeholder from the prompt was copied. Two scale checks follow, both against what the drawing prints: the extent of each level against the overall dimensions the model reported, and the drawn area of the rooms against the sizes in their labels.
5. **Repair**. On failure the model is called again, up to 2 more times, with its previous reply and the exact list of problems. A reply that is structurally valid but drawn at the wrong scale is also sent back while attempts remain. If it is still off after the last attempt it is kept, and the mismatch appears in the plan's `warnings`.
6. **Normaliser** (`normalise.py`). Pure Python, no model. See below.
7. **Validation again**, against `PlanJSON` (`modules/plans/schemas.py`).

A failure at any stage raises a typed error. Partial JSON is never returned.

## The normaliser

Everything that must not depend on the model happens in `normalise.py`:

- converts every length to metres with one drawing-wide scale and sets `units: "m"`;
- moves every level to its own origin, so the top-left of what is drawn is (0, 0) wherever the model placed it;
- cleans room polygons: no repeated or closing point, at least 3 points, non-zero area, counter-clockwise, rounded to 3 decimals, canonical start vertex;
- sorts rooms, walls, openings and columns by their geometry and assigns stable ids (`L0-R01`, `L0-W01`, `L0-O01`, `L0-C01`), so the order the model listed things in does not matter;
- sets room `kind` by rule (`modules/plans/room_kind.py`) and room `boq_type` by rule (`modules/plans/room_types.py`; the model's answer is used only when the rules return `OTHER`), wall `kind` / `is_exterior`, and opening `type` (always `door` or `window`). `room.type` is the 3D adapter's key and is never read or written;
- merges duplicate walls and adds missing partition walls (flagged `inferred`);
- orders levels from the lowest floor up and fills `index`, `name`, `elevation`, `wall_height_source`;
- adds `warnings` for implausible scale: a room under 1 m2 or over 500 m2, and a room whose printed size differs from its drawn area by more than 10%.

`upgrade_plan()` is the lighter path for PlanJSON stored before schema 2.0: it fills the new fields and leaves ids, order and geometry untouched.

## LLM interface

`ai/llm/json_client.py` defines `JSONLLMClient` and the factory `get_json_llm(provider, ...)`. `ai/llm/gemini_json.py` is the Gemini adapter and the only file that knows Gemini's URL, payload, model names and key variables. To use another model, add one adapter module and register it in `_ADAPTERS`. Nothing in `parsing/` changes.

Settings (`parsing/settings.py`, env prefix `PLAN_PARSER_`):

| Variable | Meaning |
|---|---|
| `PLAN_PARSER_LLM_PROVIDER` | Provider name. Default: `LLM_PROVIDER`, else `gemini`. |
| `PLAN_PARSER_LLM_MODEL` | Model name. Default: the adapter's default. |
| `PLAN_PARSER_LLM_FALLBACK_MODELS` | Comma-separated models tried when the main one is down. `none` disables fallback. |
| `PLAN_PARSER_LLM_TIMEOUT_S` | Seconds to wait for one reply (default 120). |
| `PLAN_PARSER_MAX_PAGES` | PDF pages sent to the model (default 4). |
| `PLAN_PARSER_CACHE` | `off` disables the plan cache. |
| `PLAN_PARSER_CACHE_DIR` | Cache folder (default `backend/.tmp/plan_cache`). |

The API key is read by the adapter from the existing variables (`GEMINI_API_KEY` or `LLM_API_KEY`).

## Cache

`plan_cache.py` stores the normalised PlanJSON under `sha256(pdf) + parser version + prompt version + schema version`. A second upload of the same bytes reads the stored plan and does not call a model. Changing `PARSER_VERSION` (in `llm_parser.py`), the prompt's `prompt_version` line or `SCHEMA_VERSION` starts fresh entries. Only the plan is cached, never project, user or plan-row ids. A failed parse is not cached.

Bump `PARSER_VERSION` whenever the pipeline or the normaliser would change what a given PDF parses to.

## Errors

All subclass `PlanParseError` (`errors.py`), which carries a stable `code`, a user-safe `message` and `details`.

| Error | `code` | When |
|---|---|---|
| `PdfInputError` | `invalid_pdf` | Empty, unreadable, password-protected or blank PDF |
| `NoFloorPlanError` | `no_floor_plan` | The model reports that no page shows a floor plan |
| `ParserNotConfiguredError` | `llm_not_configured` | Unknown provider or no API key |
| `ParserUnavailableError` | `llm_unavailable` | Provider unreachable or refusing after retries |
| `PlanOutputInvalidError` | `llm_output_invalid` | Reply still invalid after the repair attempts |
| `PlanNormalisationError` | `normalisation_failed` | Valid reply could not become a valid PlanJSON |

## When parsing fails

No flow substitutes another plan for one that could not be read.

- **2D-to-3D import**: the job ends as `failed`, `step` holds the user-facing message and `result.error` the typed error. The import screen shows the message with "Try again" and "Choose another file". Nothing is saved to the project. A Celery worker does not retry a typed parse failure, because a retry would repeat the model calls.
- **BOQ**: the job fails with the same error code and message.
- **Material finder plan upload**: the chat says the plan could not be read and asks for the room size.

## Files

| File | Purpose |
|---|---|
| `router.py` | `POST /parsing/process` (upload and start), `GET /parsing/stream/{task_id}` (SSE progress), `GET /parsing/{project_id}/plan`. |
| `service.py` | The blueprint import used by the 2D-to-3D flow: stores the PDF and its raster, calls `parse_plan_pdf`, saves the plan row, reports job progress. When the parser fails the job is marked `failed` with the typed error (`result.error.code` and message) and no plan row is written. |
| `llm_parser.py` | The pipeline above. `parse_plan_pdf`, `parse_plan_images`, and the earlier entry points kept for existing callers. |
| `pdf_input.py` | PDF to page images and positioned text. |
| `llm_schema.py` | `LLMPlanDraft` and the draft checks. |
| `normalise.py` | The deterministic normaliser and `upgrade_plan`. |
| `plan_cache.py` | The PlanJSON cache. |
| `errors.py` | Typed parser errors. |
| `settings.py` | `PLAN_PARSER_*` settings. |
| `validate.py` | Geometric validators and the confidence score. |
| `pdf_to_image.py` | Single-page rasteriser used for the stored preview image. |

## Tests

`backend/tests/unit/test_plan_parser.py` drives the pipeline with a fake `JSONLLMClient` (valid output, invalid then repaired, unrecoverable output, old-schema JSON, cache behaviour) and the Gemini adapter with a mock HTTP transport. `test_plan_normalise.py` covers the normaliser and the room-kind rules. No test uses the network.

## Known limits

- `validate.py` scores `bounding_box_fidelity` and orientation against one specific plot size (36'6" x 55'). The score is therefore low for every other drawing. It affects `confidence` only, not geometry.
- How many walls and openings are found depends on the model. With the default lightweight models a busy sheet can come back with rooms only; the normaliser then builds the walls from the room outlines (flagged `inferred`) and no doors or windows are counted. `PLAN_PARSER_LLM_MODEL` selects a stronger model.
