# 2D Floor Plan Generator: Implementation Plan

Status: **APPROVED with changes (2026-11-15).** See "Decisions" below; they override anything else in this file.

## Decisions (from review)

1. **Scope is the 2D floor plan generator only.** Do not change PDF import (`parsing`), the plans API (`plans`), BOQ/materials sheets (`sheets`), the 3D default plan (`frontend/src/lib/defaultPlan.ts`, `ProjectContext`), the 3D viewer fixtures, shared libs (`frontend/src/lib/*`, `backend/app/core/*`, `main.py`) or docs outside `docs/plans/`. Sample content found there is reported as **"found, not touched"**.
2. **No migrations.** Supabase is connected directly from the cloud through env vars. Floor plans are stored in the **existing `plans` table**, with no schema change (see R4).
3. **Only production-safe dependencies.** Every new package must ship prebuilt wheels for Linux (`python:3.12-slim`, used by the Dockerfile) and Windows. PNG/PDF export uses **PyMuPDF, which is already installed** (verified: SVG with `<symbol>`, arcs and text converts to PDF and PNG). **CairoSVG and svglib are dropped.**
4. `floorplan_generator.py` is **not deleted** in Phase 7, because `parsing/service.py` and `plans/router.py` import its functions. The new pipeline never calls it. Its functions stay importable with the same signatures.
Branch: `2D-floor_generater_Image-anaylsis` (working tree clean at the time of writing).
Baseline: `uv run pytest` in `backend/` gives **34 passed**.

---

## 1. Findings: how the current feature works

### 1.1 Files that belong to this feature

| Layer | File | What it does today |
|---|---|---|
| Backend | `backend/app/modules/ai/floorplan_generator.py` (1,807 lines) | Everything: keyword "intent" parsing, 3 hard-coded room tables, PIL PNG renderer, legacy PlanJSON builder, Gemini call, Supabase insert |
| Backend | `backend/app/modules/ai/router.py` | `POST /api/v1/ai/generate-plan`, `POST /api/v1/ai/chat`, `GET /api/v1/ai/plans/{id}/png` (plus the out-of-scope `/analyze-materials`) |
| Backend | `backend/app/modules/ai/llm_client.py` | Gemini over raw `httpx`: `call_gemini_text`, `call_gemini_vision` (**shared**, see section 3) |
| Backend | `backend/app/modules/ai/{chat,edit_ops,models,schemas,service,__init__}.py` | Empty one-line `TODO` stubs |
| Backend | `backend/app/modules/ai/prompts/` | Empty (only `.gitkeep`) |
| Backend | `backend/tests/unit/test_ai_floorplan.py` | Tests for the template, PNG render and endpoints |
| Frontend | `frontend/src/features/chat/AiGeneratorPage.tsx` (44 KB) | Form + chat + PNG viewer, route `/projects/ai-generator` (`frontend/src/app/router.tsx:52`) |
| Frontend | `frontend/src/features/chat/api.ts`, `chatApi.test.ts`, `index.ts` | API client and test |
| Frontend | `frontend/src/lib/sse.ts` | Empty `TODO` stub (can be reused for SSE) |

### 1.2 Why the output is not accurate

The LLM does not design anything. The "generator" is a lookup:

1. **No layout is computed.** `create_architectural_template()` (`floorplan_generator.py:150`) picks one of **three hard-coded room tables** with keyword matching:
   - `rental` / "dual" in text → a dual 2-BHK rental table (`:179`)
   - `2_bhk` → a 2-BHK table (`:441`)
   - anything else (3 BHK, 4 BHK, unknown) → **one and the same** "luxury residence" table (`:651`). A 4 BHK request gets the same rooms as 3 BHK.
2. **The tables are the digitised sample drawing.** Coordinates are in feet for a fixed **36'6" x 55'** plot. For any other plot they are stretched with `scale_w = W/36.5`, `scale_l = L/55` (`:864`). Rooms get distorted unevenly, and the `dimensions` label text (for example `"11' X 11'"`) is the **old sample text, never recomputed**, so labels do not match the drawn size.
3. **The free-text prompt is mostly ignored.** It is only scanned for substrings such as `"2 bhk"`, `"rent"`, `"30x50"`, `"north"` (`extract_user_architectural_intent`, `:91`). Requests like "kitchen next to dining", "attached bath for every bedroom", "study" have no effect.
4. **The Gemini call only writes a title and commentary** (`:1681`). It never sees the plan, so its commentary can describe rooms that do not exist. Its system prompt (`ARCHITECTURAL_KNOWLEDGE_PROMPT`, `:40`) names the sample drawing and its client, and the JSON example asks for a title like `"SMT. GEETA GAUD 36'6\" X 55' DUAL 2-BHK RENTAL WORKING PLAN"`, so generated titles copy the sample. When there is no key, the commentary is **fixed text with the sample's room sizes** regardless of the plot (`:1703-1732`).
5. **No validation at all**: no overlap, inside-plot, area, minimum size, reachability or attached-bath checks. Doors come from a hard-coded list of room-id pairs that only exist in the rental table (`:1481`); other layouts get arbitrary fallback doors.
6. **Raster only**: Pillow draws a fixed 1600x2400 PNG with Windows-only font paths (`:24`). No SVG, PDF or DXF.
7. Vastu is baked into the prompt (`:54`) and the UI (`AiGeneratorPage.tsx:136, 501, 885-901`).
8. Dead code: the `area_sqft` branch in `router.py` never runs because `plot_width`/`plot_length` have `ge=10`.

### 1.3 Why edits do not work

- `POST /api/v1/ai/chat` re-runs the same keyword extractor and then **regenerates the whole plan from scratch** with a **new `plan_id`** every time (`router.py:146-185`).
- The incoming `plan_id` is accepted and **ignored**; no plan state is loaded.
- Only plot size, BHK count, goal and facing can change. "Make bedroom 2 bigger", "move kitchen", "add store" do nothing.
- `chat` hard-codes `client_name="SMT. GEETA GAUD"` (`router.py:174`).
- `edit_ops.py` and `chat.py` are empty stubs. There are no room ids that survive between requests.

### 1.4 How plans are stored, returned and shown

- Stored in the Supabase table `plans` (`plan_json` = legacy PlanJSON in metres, `generation_metadata` jsonb, `origin` with a check constraint, retried as `'extracted'` if `'chat'` is rejected; `floorplan_generator.py:1750-1789`). There are **no Alembic migrations** in `backend/migrations/`; the schema lives in Supabase (docs: `docs/05-data-and-storage.md`).
- Returned inline as `png_base64` plus `plan_json`; the frontend shows `data:image/png;base64,...` and can send the plan to the 3D workspace.
- **Bug:** `GET /api/v1/plans/{id}/download-png` (`backend/app/modules/plans/router.py:166`) looks for `generation_metadata.png_base64`, but the generator only stores `png_bytes_size`. So the download endpoint **always falls back to rendering the hard-coded sample** with "SMT. GEETA GAUD" (`plans/router.py:201-203`).
- Jobs: Celery + Redis exist (`backend/app/workers/celery_app.py`) for parsing/reports/loan, not for floor plans. Generation is synchronous today.
- No voice input exists anywhere (no `SpeechRecognition` usage).

### 1.5 Stack check against section 4 of the spec

| Spec | Repo | Fit |
|---|---|---|
| React + TS + Tailwind | React 19, Vite, TS 7, Tailwind 4 | Same |
| React Hook Form + Zod | Zod 4 present, **no React Hook Form** | Add `react-hook-form` + `@hookform/resolvers` |
| FastAPI + Pydantic v2 | Same, Python **3.13.7**, managed with `uv` | Same |
| Shapely / NetworkX / OR-Tools | Shapely present; NetworkX, OR-Tools missing | Add |
| CairoSVG, ezdxf | Missing; `reportlab` and `pillow` present | See risk R1 |
| Postgres | Supabase Postgres (via `supabase` client, not SQLAlchemy) | Use the Supabase client like the rest of the app |
| Object storage | Supabase Storage / S3 | Not needed at first: exports are rendered on demand from plan JSON |
| Celery + Redis + SSE | Celery + Redis + `sse-starlette` present | Start with a FastAPI background task + SSE, as the spec allows |
| Lint/test | Backend: `ruff`, `pytest`, `mypy`. Frontend: `oxlint`, `vitest`, `tsc` | Use these |

---

## 2. Gap analysis

| Spec section | Today | Gap | Reuse |
|---|---|---|---|
| 2.1 Form | Width/length (ft only), goal, BHK preset, facing, client name, prompt | Unit choice (ft/m), separate bed/bath counts, extras checkboxes, road side, area-only with assumed ratio, project/owner fields | Layout/styling of the "details" tab in `AiGeneratorPage.tsx` |
| 2.2 Mic | None | Web Speech API button, hidden when unsupported | — |
| 2.3 Brief + confirmation | None | Brief schema, LLM parser, conflict detection (prompt wins, per owner decision), confirmation card | — |
| 2.4 Feasibility, progress | Fake staged spinner text | Real feasibility check; real progress events over SSE | Spinner UI pattern |
| 2.5 Edit chat | Full regeneration | Typed edit ops, locking, change summary | Chat bubble UI in `AiGeneratorPage.tsx` |
| 2.6 View/export | PNG `<img>` with zoom buttons | SVG zoom/pan; SVG, PDF, PNG, DXF exports | Zoom controls, download button pattern |
| 3 Golden rules | Broken: image is the output, no ids, no validator | Whole pipeline | — |
| 5 Plan JSON | Legacy PlanJSON (metres, walls/openings) for 3D viewer and BOQ | New cm-based `FloorPlan` as source of truth; **adapter** converts it to legacy PlanJSON so "Open in 3D" and BOQ sheets keep working | `build_plan_json_from_template` wall-extraction idea (rewritten, tested) |
| 6 Pipeline | None | Brief parser, feasibility, room program, templates + CP-SAT, validator, openings/fixtures placement | — |
| 7 Edit ops | None | 9 operations + engine | — |
| 8 Renderer | PIL raster | Python SVG renderer with symbol library | Colour/line-weight choices only (visually), not code |
| 9 Exports | PNG only | PDF, PNG, DXF | — |
| 10 API | `/api/v1/ai/generate-plan`, `/chat` | New `/api/v1/ai/floorplans/...` routes | Auth dependency `get_current_user`, existing `/api/v1/ai` mount |
| 12 Tests | 6 template/render tests | Validator, solver, property, snapshot, edit, guard tests, eval set | `tests/conftest.py`, `TESTING=1` convention |

---

## 3. Shared code

| Shared piece | Used by | Plan |
|---|---|---|
| `backend/app/modules/ai/llm_client.py` | out-of-scope `material_vision.py`, `parsing/llm_parser.py`, old generator | **Not modified.** The new wrapper lives in a new file `app/modules/ai/llm/client.py` and only *reads* `get_gemini_api_key()` from the old one. Material analysis and PDF parsing keep calling the old functions unchanged. |
| `backend/app/modules/ai/router.py` | floor plan routes **and** `/analyze-materials` | Only floor-plan endpoints are edited. The `/analyze-materials` handler and its import stay byte-for-byte the same. New routes are added with `router.include_router(floorplan_router, prefix="/floorplans")`, so `main.py` is not touched. |
| `backend/app/core/config.py` | whole app | **Not modified.** Floor-plan settings live in a new `floorplan/settings.py` (pydantic-settings, prefix `FLOORPLAN_`, same `.env`). |
| `floorplan_generator.py` functions | `parsing/service.py`, `plans/router.py` | Kept importable with the same signatures (Decision 4). Phase 0 only removes names/branding inside it. The one side effect outside the feature: the PNG fallback in `plans/router.py` will no longer print "(Vikas Patodi ... Standard)" in its subject line. |
| Supabase `plans` table | parsing, plans, sheets, 3D viewer | Used as today, no schema change. Each floor plan is one row: `plan_json` = legacy PlanJSON from the adapter (so "Open in 3D" and BOQ keep working), `generation_metadata` = `{floorplan, brief, messages, version}`. Edits update the **same row** (stable id). |
| Frontend `lib/api.ts` | whole app | `apiRequest` reused as is, not modified. |
| `frontend/src/lib/sse.ts` | nobody (empty stub) | **Not modified.** The fetch-based SSE reader lives in `features/floorplan/hooks/useJobEvents.ts` (`EventSource` cannot send the `Authorization` header). |
| `frontend/src/app/router.tsx` | whole app | **Not modified.** `AiGeneratorPage.tsx` keeps its name and export and renders the new `FloorplanPage`, so the route stays the same. |

Out-of-scope material-analysis files: `material_vision.py`, `backend/app/modules/materials/*`, `frontend/src/features/materials/*`. **Not opened beyond reading the import lines of `material_vision.py`**, not changed. The hunt below found **no** sample strings in them.

---

## 4. Content to remove (hunt results)

There is **no PDF or plan image file** in the repo. The "sample architecture PDF" (Er. Vikas Patodi's working drawing for Smt. Geeta Gaud, Shalimar Greens, 36'6" x 55') exists as **digitised data, names and prompts**. Search: case-insensitive `patodi|geeta|gaud|shalimar` over all files except `node_modules`, `.git`, `.venv`, `.uv-cache`; plus all `*.pdf, *.png, *.jpg, *.webp, *.svg, *.dxf, *.ipynb`.

### 4.1 In the floor plan feature

| # | Location | What | How it reaches the LLM / output |
|---|---|---|---|
| 1 | `ai/floorplan_generator.py:40-69` | `ARCHITECTURAL_KNOWLEDGE_PROMPT` names "Er. Vikas Patodi ... Smt. Geeta Gaud at Shalimar Greens, 36'6\" x 55'" + Vastu | Sent as Gemini `system_instruction` on every generation |
| 2 | `ai/floorplan_generator.py:1690` | JSON example title `SMT. GEETA GAUD 36'6" X 55' ...` | In the Gemini prompt → copied into `layout_name` → title block + DB `name` |
| 3 | `ai/floorplan_generator.py:179-860` | Three room tables digitised from the sample (36.5 x 55 ft coordinates, sample labels) | **Are** the generated layout, scaled to the plot |
| 4 | `ai/floorplan_generator.py:180, 443, 653` | `layout_name` "... (Vikas Patodi ... Standard)" | Title block, DB `name`, UI |
| 5 | `ai/floorplan_generator.py:962, 1634, 1608` | Default `client_name` / `"client"` = `SMT. GEETA GAUD` | Title block, PlanJSON `client` |
| 6 | `ai/floorplan_generator.py:1703-1732` | Hard-coded commentary with the sample's room sizes | Shown to user as "AI commentary" |
| 7 | `ai/floorplan_generator.py:10, 39, 1027` | Docstring/comments naming the sample | Not runtime, but must go for the guard test |
| 8 | `ai/router.py:46, 59, 174` | Default `client_name`, docstring, chat hard-code | Title block of every plan |
| 9 | `frontend/src/features/chat/AiGeneratorPage.tsx:42, 145, 524` | Default client name, "Rendering calibrated Er. Vikas Patodi CAD title block" stage text, placeholder | Sent to backend as `client_name`; shown on screen |
| 10 | `frontend/src/features/chat/chatApi.test.ts:52` | Test payload | Test only |
| 11 | `backend/tests/unit/test_ai_floorplan.py:24, 64, 120, 142, 159` | Names in tests | Test only |

### 4.2 Outside this feature, but feeding the same sample into the app

| # | Location | What | How it reaches output |
|---|---|---|---|
| 12 | `backend/extracted_plan.json`, `backend/formatted_plan.json` | Full sample PlanJSON with `client`, `architect`, `project_title` | **Loaded at runtime** as fallback by `parsing/service.py:29-37`, `parsing/router.py:386-395`, `plans/router.py:103-113`, `sheets/router.py:98-104` (+ `:160, :318, :627`), `sheets/service.py:542-556` (+ `:664, :822, :844`) |
| 13 | `backend/app/modules/parsing/service.py:238-252` | If the vision LLM fails, a PDF import silently returns the **sample template** with `client = "SMT. GEETA GAUD"` (filename keywords even include `"geeta"`) | User sees the sample instead of their own PDF |
| 14 | `backend/app/modules/plans/router.py:200-203` | `download-png` fallback renders the sample (always hit, see 1.4) | Every PNG download |
| 15 | `backend/app/modules/parsing/llm_parser.py:103` | Parsing prompt says "Do NOT invent ... like \"Shalimar Greens\"" | Sent to the vision LLM (mentions the name) |
| 16 | `backend/generate_complete_plan.py`, `backend/sync_precision_plan_to_db.py` | Dev scripts that build/push the sample into Supabase | Can re-seed the DB with the sample |
| 17 | `frontend/src/lib/defaultPlan.ts:3-...` (`DEFAULT_ARCHITECTURAL_PLAN`) | Sample plan used as the **default plan** in `context/ProjectContext.tsx:67` | 3D workspace shows the sample when a project has no plan |
| 18 | `frontend/src/viewer3d/fixtures/plan-sample.json` | Sample plan, test fixture of `viewer3d.test.ts` | Test only |
| 19 | `backend/tests/unit/test_sheets.py:145-156, 247`, `test_plan_schema.py:24-25` | Use `extracted_plan.json` as fixture, names in test | Test only |
| 20 | `docs/design.md:218` | "Load Shalimar Greens ..." | Docs only |
| 21 | `backend/.pytest_cache/` | Cached test node id with the name | Generated cache |

Other checks: no base64 image blobs, no few-shot plan examples in prompts other than #1-#2, no logos. `docs/reference/current.png` and `target.png` are **3D dollhouse renders**, not the 2D CAD target (see Q3).

### 4.3 How removal will be done and proven (Phase 0, scoped per Decision 1)

- **Removed (items #1-#11):** names and branding in `floorplan_generator.py`, `ai/router.py` (floor-plan parts only), `AiGeneratorPage.tsx`, `chatApi.test.ts`, `test_ai_floorplan.py`. The knowledge prompt (with its Vastu rules) and the canned commentary are deleted. Title/client default to empty, and the UI placeholder becomes "PROJECT NAME". Vastu labels in the page are removed.
- **Found, not touched (items #12-#21):** `extracted_plan.json`, `formatted_plan.json`, the root dev scripts, the fallbacks in `parsing`, `plans`, `sheets`, `llm_parser.py`, `defaultPlan.ts`, `plan-sample.json`, `test_sheets.py`, `test_plan_schema.py`, `docs/design.md`, `.pytest_cache`. These keep feeding the sample into **other** features (PDF import fallback, the 3D default plan, the BOQ default, and the `plans` PNG fallback which still passes "SMT. GEETA GAUD" itself). Recommend cleaning them in a later task.
- The digitised room tables (#3) stay, de-branded, because the old page (until Phase 7) and `parsing`/`plans` (permanently, Decision 4) import them. The **new pipeline never reads them**, and a test proves it (no import of `floorplan_generator` anywhere under `ai/floorplan/`).
- **Proof:** new `backend/tests/floorplan/test_no_sample_content.py` scans the floor-plan generator's files (`ai/floorplan_generator.py`, `ai/router.py`, `ai/floorplan/**`, `ai/llm/**`, `ai/prompts/**`, `frontend/src/features/chat/**`, `frontend/src/features/floorplan/**`, `backend/tests/floorplan/**` except itself, `backend/tests/unit/test_ai_floorplan.py`) for the deny-list `patodi|geeta|gaud|shalimar`. From Phase 1 on, it also scans every generated SVG/PNG-metadata/PDF/DXF. Plus a manual `Select-String` command for you after Phase 0.

---

## 5. Proposed folder layout

New code lives next to the existing module, inside `backend/app/modules/ai/`:

```
backend/app/modules/ai/
  llm/
    client.py              the only LLM wrapper for floor plans (structured output, Pydantic, retries)
  prompts/floorplan/
    brief_parser.md  room_program.md  edit_ops.md
  floorplan/
    schemas/   brief.py  program.py  plan.py  edit_ops.py  api.py
    settings.py            FLOORPLAN_* env settings (core/config.py untouched)
    rules.py               minimum room sizes, circulation %, wall thickness (one config file)
    units.py               cm <-> ft/in/m, label formatting
    pipeline/
      brief_parser.py  feasibility.py  room_program.py
      layout/  templates.py  solver.py  openings.py  fixtures.py
      validator.py  edit_engine.py  generate.py (orchestrator + retry loop)
    render/
      symbols.py           each fixture defined once -> SVG <symbol> + DXF block
      svg_renderer.py  raster.py (PNG/PDF)  dxf_exporter.py  legacy_adapter.py
    store.py               existing Supabase `plans` table (no schema change); in-memory when TESTING=1
    jobs.py                background job + progress events
    router.py              mounted at /api/v1/ai/floorplans
backend/tests/floorplan/   unit, property, snapshot tests + snapshots/ + fixtures/ (neutral, tests only)
backend/eval/floorplan/    cases.json + run_eval.py
backend/scripts/render_sample_plan.py
frontend/src/features/floorplan/
  FloorplanPage.tsx  api.ts  schemas.ts
  components/ BriefForm  ConfirmationCard  MicButton  PlanViewer2D  EditChat  ProgressSteps  ExportMenu
  hooks/ useSpeechInput.ts  useJobEvents.ts
```

API (adapted to the existing `/api/v1/ai` prefix):

```
POST /api/v1/ai/floorplans/brief/parse
POST /api/v1/ai/floorplans/generate            -> {job_id}
GET  /api/v1/ai/floorplans/jobs/{id}/events    SSE
GET  /api/v1/ai/floorplans/{id}                -> plan JSON + svg
POST /api/v1/ai/floorplans/{id}/edit
GET  /api/v1/ai/floorplans/{id}/export?format=svg|pdf|png|dxf
```

---

## 6. File-by-file table

| File | Action | Phase | Change and why |
|---|---|---|---|
| `backend/app/modules/ai/floorplan_generator.py` | MODIFY | 0 | Remove names, knowledge prompt, Vastu, canned commentary. Kept afterwards for `parsing`/`plans` imports (Decision 4); no longer used by the AI page after Phase 7 |
| `backend/app/modules/ai/router.py` | MODIFY | 0, 7 | P0: remove default client name/docstring. P7: mount new router; retire `/generate-plan`, `/chat`, `/plans/{id}/png` after approval. `/analyze-materials` untouched |
| `backend/app/modules/ai/llm_client.py` | KEEP | — | Shared; not changed |
| `backend/app/modules/ai/material_vision.py` | KEEP | — | Out of scope |
| `backend/app/modules/ai/{chat,edit_ops,models,schemas,service,__init__}.py` | KEEP | — | Empty scaffold stubs; new code goes in `floorplan/` |
| `backend/app/modules/ai/llm/client.py` | NEW | 4 | Single provider-agnostic wrapper, model from env |
| `backend/app/modules/ai/prompts/floorplan/*.md` | NEW | 4, 5 | Prompts as files |
| `backend/app/modules/ai/floorplan/**` | NEW | 1-7 | Pipeline, renderer, exports, API (section 5) |
| `backend/app/modules/ai/floorplan/settings.py` | NEW | 4 | `FLOORPLAN_LLM_MODEL`, `FLOORPLAN_LLM_TEMPERATURE`, `FLOORPLAN_SOLVER_TIME_S`, read from `.env`; `core/config.py` untouched |
| `backend/tests/unit/test_ai_floorplan.py` | MODIFY → REPLACE | 0 → 7 | P0: de-brand. P7: old-template tests reduced to "functions still importable for parsing/plans"; new tests live in `tests/floorplan/` |
| `backend/tests/floorplan/test_no_sample_content.py` | NEW | 0 | Guard test (scoped, section 4.3) |
| `backend/tests/floorplan/**`, `backend/tests/floorplan/fixtures/**`, `backend/eval/floorplan/**`, `backend/scripts/render_sample_plan.py` | NEW | 1-7 | Tests, neutral hand-written fixtures, eval set, render script |
| `backend/pyproject.toml`, `uv.lock` | MODIFY | 2, 3, 6 | New deps (section 7), installed with `uv add` |
| `frontend/src/features/chat/AiGeneratorPage.tsx` | MODIFY → REPLACE | 0 → 7 | P0: remove name defaults, Patodi stage text, Vastu labels. P7: becomes a thin wrapper that renders `FloorplanPage` (keeps route and export) |
| `frontend/src/features/chat/api.ts`, `chatApi.test.ts` | MODIFY | 0, 7 | P0: de-brand. P7: old calls removed once the new API is in use |
| `frontend/src/app.test.tsx` | MODIFY (if needed) | 7 | Only the assertions about `AiGeneratorPage` content, if they break |
| `frontend/src/features/floorplan/**` | NEW | 7 | New UI, incl. the SSE reader hook |
| `frontend/package.json`, `package-lock.json` | MODIFY | 7 | `react-hook-form`, `@hookform/resolvers` |
| Everything under `parsing`, `plans`, `sheets`, `materials`, `core`, `main.py`, `frontend/src/lib`, `context`, `viewer3d`, root JSON/scripts, `docs/` (except this file) | **NOT TOUCHED** | — | Decision 1 |

---

## 7. Dependencies

| Package | Where | Why |
|---|---|---|
| `ortools` | backend | CP-SAT layout solver (`AddNoOverlap2D`) |
| `networkx` | backend | Reachability / adjacency graph checks in the validator |
| `ezdxf` | backend | DXF export with layers, blocks, dimensions |
| `hypothesis` (dev group only) | backend | Property tests; not installed in the production image (`uv sync --no-dev`) |
| `react-hook-form`, `@hookform/resolvers` | frontend | Form state + Zod validation (pure JS) |

All new backend packages publish prebuilt wheels for manylinux (Python 3.12, used in production) and Windows (Python 3.13, used locally). No system libraries needed. If `uv add` fails to find a wheel for either platform, I stop and tell you.

Already present and reused: `pymupdf` (SVG → PDF/PNG), `shapely`, `pydantic`, `pydantic-settings`, `httpx`, `sse-starlette`, `zod`, `supabase`. No voice libraries, no image-generation models, no pan/zoom library (a small pointer/wheel handler on the SVG is enough).

---

## 8. Phases

Each phase ends with: `uv run pytest` + `uv run ruff check` (backend), `npm run lint` + `npx vitest run` + `npx tsc -b` (frontend, when touched), a check command for you, and a stop.

0. **Cleanup.** Section 4.3. Done when the scoped guard test passes, `Select-String` over the floor-plan files finds nothing, the old AI generator page still generates (de-branded), and all existing tests pass.
1. **Schemas + SVG renderer.** Pydantic `Brief`, `RoomProgram`, `FloorPlan` (cm), `EditOp`. Neutral hand-written sample plan (tests only). Renderer: thick walls with joins and cut openings, door arcs, window symbols, fixture symbols, labels with size (`BED ROOM 400X500` or ft-in), outer dimension lines, title block from user input only, courtyard hatch. Check: `uv run python scripts/render_sample_plan.py` → open `plan.svg`. Snapshot test added.
2. **Validator** (Shapely + NetworkX) with passing and failing cases: overlap, outside plot, below min size, unreachable room, missing attached bath, window on internal wall, door wider than shared wall, area tolerance; wet-room clustering as warning.
3. **Layout.** Templates for compact 2/3-bed houses and a courtyard villa; CP-SAT solver on a 15 cm grid with no-overlap, plot bounds, size ranges, adjacency distance objective, covered-area objective, time limit. Then doors/windows/fixtures placement in code. Hypothesis tests: no overlaps, nothing outside the plot. Works from hand-written room programs only.
4. **LLM layer.** Wrapper, Brief parser (prompt wins on conflict, per owner decision; unknowns left empty and listed), feasibility from the rules table with clear options, room program, retry loop (max 3) feeding validator errors back to layout. Tests mock the wrapper; one optional live test skipped without a key.
5. **Edit engine.** The 9 ops, locking of unmentioned rooms, re-solve, validate, change summary, impossible-edit message with alternative. Tests prove locked rooms keep identical coordinates.
6. **Exports.** PNG/PDF from the same SVG via PyMuPDF; DXF with layers `WALLS DOORS WINDOWS FURNITURE TEXT DIMENSIONS HATCH`, fixtures as blocks, arcs, real dimensions, `$INSUNITS` = cm. Check with a free DXF viewer.
7. **API + frontend.** Endpoints, storage in the `plans` table, background job + SSE progress, new page (form, mic, confirmation card, viewer with zoom/pan, edit chat with mic, progress steps, downloads). Eval set (30-50 cases, one command prints pass rate). Then, **with your approval**, retire the old `/generate-plan`, `/chat` and `/plans/{id}/png` endpoints and the old page UI. `floorplan_generator.py` stays (Decision 4).

---

## 9. Risks and open questions

**Resolved:** Q1 (scope, Decision 1), Q2 (3D default left as is), R1 (PyMuPDF, Decision 3), R4 (no migration, Decision 2).

**Still open:**

- **Q3. 2D reference image.** `docs/reference/` only has 3D dollhouse renders. Please add the 2D CAD reference image before Phase 1 (renderer). Until then I follow the written description in the spec, section 8.

**Risks:**

- **R2. OR-Tools wheels** exist for Python 3.12 (prod) and 3.13 (local). Verified at install time in Phase 3; if unavailable, I stop and tell you.
- **R3. Solver time.** CP-SAT gets a time limit (default 8 s) and templates run first; plans that time out return a clear message, never an unvalidated plan.
- **R4. Database (decided).** No migration. One row per floor plan in the existing `plans` table: `plan_json` = legacy PlanJSON, `generation_metadata.floorplan` = the new cm-based plan (source of truth), plus `brief`, `messages` (chat history) and `version`. `origin` stays `'chat'` with the existing `'extracted'` fallback for the check constraint. When `TESTING=1` or Supabase is unreachable, an in-memory store is used.
- **R5. Background jobs.** An in-process job store breaks with multiple uvicorn workers. Fine for now (single worker in dev); move to Celery/Redis later if needed.
- **R6. SSE auth.** `EventSource` cannot send the Bearer token. Plan: fetch-streaming reader in `lib/sse.ts`.
- **R7. LLM determinism.** Low temperature + Pydantic validation + schema-constrained output; invalid output is retried once, then a clear error. The LLM never returns coordinates.
- **R8. Old page during transition.** Until Phase 7 the old page keeps working with de-branded, still template-based output. That is expected; it is not the new behaviour.
- **R9. Symbol licences.** All fixture symbols are drawn by me from basic shapes; no third-party CAD blocks.
