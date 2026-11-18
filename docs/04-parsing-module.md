# 04 Parsing module

Location: `backend/app/modules/parsing/`. This module turns an uploaded floor plan PDF into a **PlanJSON**. The same schema comes out whichever LLM is configured, and the same PDF always gives the same PlanJSON.

```python
from app.modules.parsing.llm_parser import parse_plan_pdf

plan = parse_plan_pdf(pdf_bytes)   # a validated PlanJSON 2.0 dict, or a PlanParseError
```

## Pipeline

```
PDF -> pdf_input -> LLM call -> JSON extraction -> draft validation -> repair (up to 2) -> normaliser -> PlanJSON validation
          |                                                                |                  |
          |                                                          reply cache              |
          |                                               (sha256, prompt, provider, model)   |
          +----------------- plan cache (the same, plus parser and schema versions) ----------+
```

1. **Input** (`pdf_input.py`). Each page is rendered to PNG at a fixed 300 DPI. Sheets larger than A3 are scaled down by a rule that depends only on the page size, so the long side stays within 5000 px. The PDF's own text is read too, one block per line in reading order. This input is the same for every provider. Scanned PDFs have no text layer and send images only. A PDF whose pages are all blank is rejected here and never reaches a model.
2. **Model call**. One `JSONLLMClient.generate_json(system_prompt, images, text, json_schema)` call. The prompt is the single versioned file `ai/prompts/parsing/plan_parser.md`. The schema is `WIRE_JSON_SCHEMA` (`llm_schema.py`): every field required, nine nullable, no length or range constraints, so a provider that enforces schemas with a grammar can enforce it.
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

`ai/llm/json_client.py` defines the interface `JSONLLMClient`, the typed errors, the retry policy and the adapter registry. Each provider has one adapter file:

| Provider | Adapter | Built on |
|---|---|---|
| `gemini` | `ai/llm/gemini_json.py` | HTTPS (`httpx`) |
| `anthropic` | `ai/llm/anthropic_json.py` | the official `anthropic` SDK |

Rules every adapter follows:

- The key is passed in from settings. An adapter never reads a key variable itself. The Anthropic adapter passes the key to the SDK explicitly, so `ANTHROPIC_API_KEY` in the environment is never used.
- Exactly the configured model answers. There is no fallback to another model or another provider.
- Only rate limits (429) and 5xx responses are retried, at most twice, with waits of 2 s and 6 s (a provider's `retry-after` hint is honoured up to 30 s). Authentication and billing errors are never retried. Network failures and timeouts are not retried either.
- Failures are raised as typed errors, which the parser turns into the `PlanParseError` codes below.

Provider specifics, checked against the vendors' current docs:

- **Anthropic**: no sampling parameter is sent, because the current API rejects `temperature`, `top_p` and `top_k` on every model. JSON comes back through structured outputs (`output_config.format`). Pages are scaled to 2576 px on the long edge, the largest the API processes, and sent before the text. The reply is streamed. `thinking` and `effort` stay at the model's defaults. Server-side refusal fallbacks are not enabled, since they would let a different model answer.
- **Gemini**: `temperature` is 0; if a model rejects the parameter the request is repeated without it. The schema is given as instructions in the system prompt.

Settings (`parsing/settings.py`, env prefix `PLAN_PARSER_`):

| Variable | Meaning |
|---|---|
| `PLAN_PARSER_LLM_PROVIDER` | `gemini` (default) or `anthropic`. |
| `PLAN_PARSER_LLM_MODEL` | The model name at that provider. Required. |
| `PLAN_PARSER_LLM_API_KEY` | The API key for that provider. Required. |
| `PLAN_PARSER_LLM_TIMEOUT_S` | Seconds to wait on one model call (default 300). |
| `PLAN_PARSER_MAX_PDF_MB` | Largest PDF accepted (default 20). |
| `PLAN_PARSER_MAX_PDF_PAGES` | Most pages a PDF may have (default 10). |
| `PLAN_PARSER_CACHE` | `off` disables both caches (model reply and plan). |
| `PLAN_PARSER_CACHE_DIR` | Cache folder (default `backend/.tmp/plan_cache`). |

No variable is named after a vendor. For Gemini only, when `PLAN_PARSER_LLM_API_KEY` is empty the key falls back to `LLM_API_KEY`, then `GEMINI_API_KEY`, so an existing Gemini setup keeps working.

The settings are validated when the API starts. An unknown provider, a missing model or a missing key stops startup with one error that names the variable, for example `PLAN_PARSER_LLM_MODEL is not set. Set it to the anthropic model that should read the drawings.`

## How to switch provider

Switching model or vendor is a change of values in `.env`. No variable name and no code changes.

1. Set the three values:

       PLAN_PARSER_LLM_PROVIDER=anthropic
       PLAN_PARSER_LLM_MODEL=<model id>
       PLAN_PARSER_LLM_API_KEY=<key for that provider>

2. Restart the API (and the Celery worker, if you run one). Startup fails with a clear message if a value is missing or the provider is unknown.
3. Upload a plan. PDFs parsed by the previous model are parsed again by the new one, because the provider and the model are part of the cache key. The log line of each parse shows which provider and model answered.

To go back, restore the previous three values. The earlier model's cached results are still there and are used again.

To add a provider that is not listed: write one adapter file in `ai/llm/` that implements `JSONLLMClient` (take `model`, `api_key` and `timeout_s`, raise the typed errors, wrap the call in `with_retries`), and add one entry to `_ADAPTERS` in `ai/llm/json_client.py`. Nothing in `parsing/` changes.

## Logging

Each parse writes one line, on the logger `construtiva.parsing.llm`:

    plan parse: provider=anthropic model=<model> input_tokens=6120 output_tokens=9800 attempts=1 duration_s=74.2 cache_hit=False outcome=ok

`attempts` counts model calls (the first try plus repairs) and the token counts are their sum. A plan-cache hit logs `cache_hit=True` with zero tokens, and a plan built again from the stored model reply logs `cache_hit=reply`, also with zero tokens. A failure logs its error code as `outcome`. File contents and keys are never logged. The same token counts are stored with the plan under `parser`.

## Cache

`plan_cache.py` keeps two things, in the same folder:

| Cache | Key | Holds |
|---|---|---|
| Reply cache | `sha256(pdf) + prompt version + provider + model` | The model's reply that passed the checks, as it was returned, with what the call cost. |
| Plan cache | the same, plus `parser version + schema version` | The normalised PlanJSON. |

What happens on an upload:

1. The plan is in the plan cache: it is returned. No model call.
2. Otherwise the reply is in the reply cache: the plan is built from it again (checks, normaliser, rules) and stored. No model call.
3. Otherwise the PDF is sent to the model, and both the reply and the plan are stored.

So **only a new PDF, prompt version, provider or model reaches a model.** A change to the normaliser or to a rule (room kinds and types, units, ids) needs a new `PARSER_VERSION` (in `llm_parser.py`) and nothing else: every PDF already seen is normalised again from its stored reply the next time it is uploaded.

Rules for the two version numbers:

- Raise `PARSER_VERSION` whenever the checks, the normaliser or a rule would change what a given reply turns into.
- Raise the prompt's `prompt_version` line whenever what is sent to the model changes: the prompt text, the wire schema (`WIRE_JSON_SCHEMA`) or the page rendering (`RENDER_DPI`, `MAX_IMAGE_SIDE_PX`). A test pins a fingerprint of those to the prompt version, so the change cannot be made without it.

Two cases still call the model for a PDF it has seen: the stored reply no longer passes the checks, or it has fewer rooms than the caller asks for (the BOQ asks for one). Only the reply and the plan are cached, never project, user or plan-row ids. A failed parse is not cached.

## Errors

All subclass `PlanParseError` (`errors.py`), which carries a stable `code`, a user-safe `message` and `details`.

| Error | `code` | When |
|---|---|---|
| `PdfInputError` | `invalid_pdf` | Empty, unreadable, password-protected or blank PDF |
| `NoFloorPlanError` | `no_floor_plan` | The model reports that no page shows a floor plan |
| `ParserNotConfiguredError` | `llm_not_configured` | Unknown provider, or no model or key |
| `ParserAuthError` | `llm_auth_failed` | The provider refused the key. Not retried |
| `ParserBillingError` | `llm_billing` | No credit, a billing problem or a spend cap. Not retried |
| `ParserRateLimitedError` | `llm_rate_limited` | Still rate limited after the bounded retries |
| `ParserRequestRejectedError` | `llm_request_rejected` | The provider rejected the request (unknown model, bad request, declined) |
| `ParserUnavailableError` | `llm_unavailable` | Provider unreachable, timed out, or 5xx after the bounded retries |
| `PlanOutputInvalidError` | `llm_output_invalid` | Reply still invalid after the repair attempts |
| `PlanNormalisationError` | `normalisation_failed` | Valid reply could not become a valid PlanJSON |

## Upload limits

Every plan upload (the BOQ, and the 3D gateway before a plan reaches PlanTo3D) goes through the same check, `read_plan_upload` in `service.py`, before anything else happens:

1. the file name ends in `.pdf`;
2. the size is within `PLAN_PARSER_MAX_PDF_MB` (default 20);
3. the content really is a PDF that opens, and is not password protected;
4. it has at most `PLAN_PARSER_MAX_PDF_PAGES` pages (default 10).

A rejected upload gets a clear message (`413` for size, `400` otherwise), creates no project, job or stored file, and never reaches a model. Pages are never silently dropped: a PDF over the page limit is rejected, not truncated. The parser applies the same limits itself (`load_plan_pdf`), so a caller that skips the endpoint check is still covered. `GET /api/v1/parsing/upload-limits` returns the two limits so the upload screens can state them.

## When parsing fails

No flow substitutes another plan for one that could not be read.

- **BOQ**: the job fails with the same error code and message.
- **Material finder plan upload**: the chat says the plan could not be read and asks for the room size.

## Files

| File | Purpose |
|---|---|
| `router.py` | `GET /parsing/upload-limits` (the limits, for the upload screens) and `POST /parsing/pdf-to-image` (one page as a PNG). |
| `service.py` | `read_plan_upload` and `upload_limits`: the one check every plan upload goes through. |
| `llm_parser.py` | The pipeline above. `parse_plan_pdf`, `parse_plan_images`, and the earlier entry points kept for existing callers. |
| `pdf_input.py` | The upload check (`check_plan_pdf`) and PDF to page images and text. |
| `llm_schema.py` | `WIRE_JSON_SCHEMA` (what the model is asked for), `LLMPlanDraft` (the validator) and the draft checks. |
| `normalise.py` | The deterministic normaliser and `upgrade_plan`. |
| `plan_cache.py` | The reply cache and the PlanJSON cache. |
| `errors.py` | Typed parser errors. |
| `settings.py` | `PLAN_PARSER_*` settings and their validation (`resolve_llm_config`). |
| `validate.py` | Geometric validators and the confidence score. |
| `pdf_to_image.py` | Single-page rasteriser, used by the material finder and `/parsing/pdf-to-image`. |

## Tests

`backend/tests/unit/test_plan_parser.py` drives the pipeline with a fake `JSONLLMClient` (valid output, invalid then repaired, unrecoverable output, old-schema JSON, cache behaviour, typed provider failures, the per-parse log line). `test_llm_clients.py` covers the settings, the registry, the retry policy and both adapters through mock HTTP transports. `test_plan_normalise.py` covers the normaliser and the room rules. No test calls a live model: `tests/conftest.py` makes any attempt to build the real client fail.

## Known limits

- `validate.py` scores `bounding_box_fidelity` and orientation against one specific plot size (36'6" x 55'). The score is therefore low for every other drawing. It affects `confidence` only, not geometry.
- How many walls and openings are found depends on the model. A lightweight model can return rooms only for a busy sheet; the normaliser then builds the walls from the room outlines (flagged `inferred`) and no doors or windows are counted. `PLAN_PARSER_LLM_MODEL` selects the model.
