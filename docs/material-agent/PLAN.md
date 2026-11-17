# Material Identification & Quantity Agent — Plan

Status: **Phase 1 built, waiting for your test and OK before Phase 2** (see section 11).
Scope: the "Material Finder" feature only. The 2D floor plan generator, 3D viewer, loan
extraction, auth and landing page are not touched (one small, backwards-compatible
addition to the shared LLM wrapper is listed below).

---

## 1. Audit: why the current feature does not work

| # | Finding | Where |
|---|---|---|
| 1 | **The page never calls the backend.** "Analyse" runs three `setTimeout` steps ("Querying CPWD … price indices") and then shows the same hard-coded 5 materials for every photo, with ₹ rates and a ₹ total. | `frontend/src/features/materials/AnalyseMaterialsPage.tsx` (lines 118–137) |
| 2 | The backend prompt asks for **INR unit rates and a total cost**, with example lines like `"unit_rate_inr": 9.50`. This pulls the model towards pricing instead of identification. | `backend/app/modules/ai/material_vision.py` (prompt, lines 29–73) |
| 3 | The **LLM invents the quantities** ("based on typical room heights 2.8–3.0 m"). The user's own room is never used, so quantities mean nothing. | same file, rule 3 |
| 4 | **Fake results on failure.** With no API key, or when the model call fails, it returns made-up bricks/tiles/cement with costs as if they were real. The two fallbacks even use different field names (`detected_materials` vs `materials_detected`). | same file, lines 93–202 |
| 5 | No schema validation of the model output; no retry on bad JSON. | `material_vision.py`, `llm_client.call_gemini_vision` |
| 6 | No focus area ("only the ceiling"), no target room, no follow-up, no storage, no job/progress — one synchronous call. | `ai/router.py` `/analyze-materials` |
| 7 | Output is generic (“Tiles”, “Plaster”, “Cement”) because the prompt only asks for categories, not specific finishes, patterns or sizes. | prompt |
| 8 | The old vision helper puts the API key in the URL query string (`?key=…`), which ends up in logs. | `llm_client.py` line 74 |

Nothing else in the app uses `material_vision.py` or `/api/v1/ai/analyze-materials`
(checked: only `ai/router.py` imports it; the frontend never calls it).

---

## 2. What already exists and will be reused

| Need | Existing piece | How it is used |
|---|---|---|
| LLM calls (structured JSON, Pydantic validation, retry on bad JSON, timeout, fallback model) | `backend/app/modules/ai/llm/client.py` (`GeminiClient.structured`) | Add an optional `images=[(bytes, mime)]` argument. Text-only callers (floor plan) are unchanged. |
| Background job + live progress (SSE with polling fallback) | Floor plan job runner `ai/floorplan/jobs.py` + `useJobEvents` hook | Move the generic part to `ai/jobs_common.py`; the floor plan keeps working exactly as now (its tests guard this). `app/events/sse.py` and `pubsub.py` are empty stubs, so there is no other SSE helper to reuse. |
| File storage | `core/supabase.upload_to_storage()` + `files` table | Reference images → bucket `site-photos`; uploaded plans → bucket `blueprints`; one `files` row each. |
| Floor plan parsing (PDF/image → PlanJSON) | `parsing/pdf_to_image.convert_pdf_page_to_png` + `parsing/llm_parser.parse_blueprint_image_with_llm` | Called directly. **Not** `ParsingService.process_blueprint_pdf`, because that one inserts the result into the project's `plans` table (the spec forbids overwriting the saved plan). |
| Projects of the logged-in user | `projects` table (`user_id` column) | `find_project(name)` queries `projects` filtered by `user_id = current user` and fuzzy-matches names in code. No new endpoint needed. |
| Saved plan of a project | `plans` table (`plan_json`; AI-generated plans also have `generation_metadata.floorplan` in cm) | Latest plan for the project. |
| Conversation state | Existing tables `conversations`, `messages` (`metadata` jsonb), `message_attachments` | See section 4. **No new tables, no migration.** |
| Auth | `core/security.get_current_user` | Every endpoint; every read is checked against the user id. |
| Units | `ai/floorplan/units.py` (ft-in formatting) | Display of feet/inches. |

What a saved PlanJSON contains (checked): rooms as polygons with a name (AI-generated plans also
have `tag` = room type), walls, doors and windows on walls (width, height), and one
`wall_height` per level (= ceiling height, typically 2.8–3.0 m). **No counters.** AI-generated
plans also carry a `kitchen_counter` fixture position, which tells us the platform wall.

---

## 3. Architecture

```
POST /material-analysis (images, focus, target space)
  [A] validate, downscale (long side 2000 px), hash, store in Supabase storage
  [B] vision call (structured ImageAnalysis)   ← cached by image hash + focus + prompt version + model
  [C] normalise to the catalog (aliases → catalog id; unknown kept as "other")
  [D] resolve target space (manual dims | project plan | uploaded plan) → surfaces
  [E] calculator (pure Python)                  ← all numbers come from here
  [F] composer (LLM writes the explanation; every number checked; template fallback)
  [G] save to conversation, stream progress: uploading → analysing_image →
      matching_materials → calculating → writing_summary → done
Follow-up chat → usually only [D]–[F]. No second vision call unless a new surface is asked for.
```

The chat layer is **not** a free-roaming agent. One LLM call turns the message into a typed
`ChatIntent` (like the floor plan's edit ops):
`recalculate | apply_material | change_focus | explain_material | use_project | upload_plan | cost_question | unclear`,
with material, application, room, project name, layout and overrides. Code then runs the
tools (`find_project`, `get_project_context`, `parse_uploaded_plan`, `get_room`,
`compute_application`, `recalculate`, `ask_user`) deterministically. Missing info → one
question (`needs_input` state with options).

---

## 4. Data (no new tables)

| What | Where |
|---|---|
| One material analysis session | `conversations` row: `conversation_type = "material_finder"`, `project_id`, `user_id`, `title` |
| ImageAnalysis, target space, every report, uploaded plan reference | `messages.metadata` (jsonb) on the assistant messages; the latest state is read from the last one |
| Reference images / uploaded plans | Supabase storage + `files` rows, linked with `message_attachments` |
| Vision cache | `backend/.tmp/material_cache/<key>.json` (same approach as the parser's plan cache) |

If `conversation_type` has a check constraint that rejects `"material_finder"`, the code
falls back the same way the floor plan does for `plans.origin` (I will verify on the first
real insert). If Supabase is not configured or `TESTING=1`, an in-memory store is used.

The tables `materials`, `material_prices`, `sheet_items` stay untouched (they belong to the
BOQ/cost feature, which is out of scope and has price columns).

---

## 5. Files

### Delete
| File / code | Why |
|---|---|
| `backend/app/modules/ai/material_vision.py` | Cost prompt, LLM quantities, fake fallbacks. Replaced, not commented out. |
| `/analyze-materials` endpoint in `backend/app/modules/ai/router.py` | Replaced by `/material-analysis`. Nothing calls it. |
| Mock data, ₹ rates and cost total in `AnalyseMaterialsPage.tsx` | The page is rebuilt (same route `/materials/analyse`, same navbar link). |

### Add (backend: `backend/app/modules/ai/material_agent/`)
| File | Purpose |
|---|---|
| `schemas.py` | `DetectedMaterial`, `ImageAnalysis`, `QuantityLine`, `ApplicationRequest`, `TargetSpace`, `MaterialReport`, `ChatIntent`, API bodies. No cost fields anywhere. |
| `vision.py` | Step B: one structured call per image, focus passed in, cached. |
| `normalise.py` | Step C: alias matching against the catalog. |
| `space.py` | Step D: PlanJSON / generator plan / manual dims → rooms and surfaces in feet; room matching with aliases; unit conversion (mm, cm, m, in, ft). |
| `geometry.py` | Section 7A application rules: platform runs (one wall / L / U / island, corner counted once, no run across a door), backsplash, floor, all walls, one wall, ceiling. Per-run breakdown. |
| `calculator.py` | Step E: pure functions (coverage × area, wastage, buy units, rounding, assumptions). |
| `compose.py` | Step F: explanation + number check + template fallback. |
| `projects.py` | `find_project(user, name)` (own projects only; 0 / 1 / many) and `get_project_context(project_id)` (compact room table for the LLM, raw JSON for code). |
| `plan_upload.py` | Plan uploaded in chat: store file, rasterise PDF, call the existing parser, keep the result on the conversation only. |
| `chat.py` | `ChatIntent` interpretation + tool dispatch. |
| `store.py` | conversations / messages / files persistence (memory store in tests). |
| `service.py`, `router.py` | Orchestration and endpoints (mounted under `/api/v1/ai/material-analysis`). |
| `prompts/material_vision.md`, `prompts/material_chat.md`, `prompts/material_summary.md` | Prompts (in the existing `ai/prompts/` folder). |
| `data/material_catalog.json` | ~80 entries over all categories in section 6 of the spec. Plain JSON, editable without code. |
| `data/material_rules.json` | Wastage per material type / layout, paint coats, rounding. Marked "to be verified with the architecture firm". |
| `data/application_rules.json` | Platform depth 2 ft, backsplash 2 ft, skirting 4 in, bath tiles 7 ft, default ceiling 10 ft, … same marking. |
| `data/room_aliases.json` | kitchen / modular kitchen / master bedroom / bedroom 2 / hall / pooja / washroom … |

### Change
| File | Change |
|---|---|
| `backend/app/modules/ai/llm/client.py` | Optional `images` argument on `structured()`. Backwards compatible. |
| `backend/app/modules/ai/floorplan/jobs.py` | Generic part moved to `ai/jobs_common.py` and re-imported; floor plan API and behaviour unchanged. |
| `backend/app/modules/ai/router.py` | Remove `/analyze-materials`; mount the new router (same way as `/floorplans`). |
| `frontend/src/features/materials/` | New page and components (below). |
| `.env.example` | `MATERIAL_VISION_MODEL`, `MATERIAL_MAX_IMAGES`, `MATERIAL_MAX_IMAGE_MB` (commented defaults). |

### Frontend (`frontend/src/features/materials/`)
`MaterialFinderPage.tsx` (route `/materials/analyse`), `components/UploadPanel`, `AreaSelector`
(surface chips + free text), `TargetSpacePicker` (rooms of the active/selected project, or
manual L × W × H / wall W × H), `ProgressSteps`, `ResultView` (image + materials grouped by
surface, confidence badges, look-alikes for low confidence), `AssumptionsPanel` (editable →
`/recalculate`), `MaterialChat` (attach plan, "Using: Kitchen, 10 × 8 ft, from project X"
chip with Edit), always-visible note "Quantities are planning estimates. Verify by site
measurement before ordering." `api.ts`, `schemas.ts` (zod), hooks reuse `useJobEvents`.
No new UI library; same dark theme as the rest of the app.

---

## 6. API (under `/api/v1/ai`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/material-analysis` | multipart: 1–4 images, `focus` (surface chips + text), optional target space (manual dims or `project_id` + room) → `{report_id, job_id}` |
| GET | `/material-analysis/jobs/{job_id}/events` | SSE progress (polling fallback `GET …/jobs/{job_id}`) |
| GET | `/material-analysis/{id}` | Latest report + chat history |
| POST | `/material-analysis/{id}/recalculate` | New dimensions / wastage / coverage / area → steps D–F only |
| POST | `/material-analysis/{id}/chat` | multipart: message + optional plan file (PDF/PNG/JPG). Returns the answer, a question (`needs_input`) or a job id when a plan must be parsed first |

States returned: `ok`, `needs_input` (one question + options), `not_found` (material not in
the image, room or project not found — with the list), `failed` (clear message, never fake data).
"How much will it cost?" → fixed answer: this tool gives materials and quantities only.

---

## 7. Phase 1 deliverables (what you can test)

1. Upload a living-room photo, focus "TV wall", manual wall 12 × 10 ft →
   fluted veneer 92.4 sq ft ≈ 3 sheets (8 × 4 ft), marble 39.6 sq ft (worked example 1).
2. Same session: "how much marble for the kitchen platform?" with
   - a project name you own → its saved plan's kitchen is used, or
   - an uploaded floor plan → parsed, kept on the conversation only.
   If the layout is unknown, it asks "one wall / L / U / island". L-shape on 10 × 8 ft →
   32 sq ft, 35.2 sq ft with 10 % wastage (worked example 2), with a per-run breakdown.
3. Applications: kitchen platform, floor, all walls, one wall, ceiling, backsplash.
4. Editing ceiling height / wastage / dimensions in the assumptions panel updates instantly,
   with no new vision call.
5. Works for living room, kitchen, bedroom and facade photos.

## 8. Tests (Phase 1)

Calculator formulas, wastage, openings, rounding; both worked examples exact; geometry per
application (incl. openings, door-blocked runs, corners); room matching (exact, alias,
ambiguous → question, none → question); project lookup (own projects only; 0/1/many);
follow-up with an uploaded plan makes **no second vision call**; an uploaded plan never
writes to `plans`; normaliser aliases and `other`; composer number check; vision cache key;
**no-cost guards**: prompt files must not contain `cost`, `price`, `budget`, `₹`, `rs.`,
`inr`, `$`, `rate per`; schema field names must not contain `cost`, `price`, `rate`,
`amount_inr`, `currency`, `budget`. Frontend: components + a guard that the materials
feature has no ₹/price/cost text. Plus an end-to-end HTTP check like the floor plan one.

Phase 2 (after your OK on Phase 1): draw-a-box crop, more chat intents and multi-room
totals, derived supporting materials (adhesive, grout, backing ply…), PDF/sheet export
(the existing `sheets/export.py` prints price columns, so a cost-free variant is needed),
multi-image combined analysis. Phase 3: eval set and scores, catalog editing UI, boards.

---

## 9. Risks found during exploration

| Risk | Plan |
|---|---|
| The existing parser **rejects plans with fewer than 6 rooms** (`llm_parser.py` line 472), so a small 1–2 BHK upload fails. | Catch it and ask for the room size instead. Optional fix (needs your OK, it is in the parsing module): a `min_rooms` argument, default 6, that the material agent sets to 1. |
| Plan parsing takes ~20–60 s (one vision call on a 300 dpi image). | Runs as a job with progress; the user's question continues automatically when it finishes. |
| `GET /api/v1/projects/{id}` does not check that the project belongs to the user. | The material agent does its own `user_id` check on every project read. I will not change the projects module (flagging it for you). |
| Without a login token the backend uses a shared demo user. | Same behaviour as the rest of the app; project lookup then searches the demo user's projects. |
| Gemini timeouts (seen today). | 1 retry + fallback model; on failure a clear "try again" message, never invented materials. |

---

## 10. Open questions (please answer)

1. **Vision model.** The key and wrapper already work with `gemini-3.5-flash-lite` (main) and
   `gemini-3.5-flash` (fallback). For specific identification I recommend **`gemini-3.5-flash`
   as the main vision model** (lite tends to be generic), overridable with `MATERIAL_VISION_MODEL`.
   OK?
2. **Units.** Feet / sq ft everywhere (as in the spec examples), or also metric (m, m²)?
3. **Who reviews** the catalog and wastage values at the firm? (Values ship marked "to be verified".)
4. **Marble / stone slab sizes** the firm uses, or keep answers in sq ft for now?
5. **Small plans:** may I add the `min_rooms` option to the existing parser (section 9), or
   should small plans just fall back to typed dimensions?
6. **Old page:** OK to replace the current Material AI page in place (same route and navbar
   link), rather than keeping the mock version?

Answered from the code (no need to reply): ceiling height and openings (section 2), existing
exporter (Phase 2 note), how projects are stored and scoped (section 2), PlanJSON contents
(section 2), parser function and duration (sections 2 and 9).

---

## 11. Phase 1: what was built (approved 2026-11-17)

Open questions were answered with the recommendations:

| # | Decision |
|---|---|
| 1 | Vision model **`gemini-3.5-flash-lite`** (changed 2026-11-18 for speed: measured ~5 s per photo vs 60-150 s / timeouts for `gemini-3.5-flash`), thinking "low", 30 s limit; fallback `gemini-3.5-flash` with its own 40 s limit; chat calls 15 s then the keyword reader. Photos downscaled to 1600 px; no extra summary call. All overridable with `MATERIAL_*` in `.env`. |
| 2 | Feet / sq ft in all answers; input accepts ft, in, m, cm, mm. |
| 3 | Catalog and rules ship marked "to be verified with the architecture firm" (reviewer still to be named). |
| 4 | Stone answers in sq ft (no slab sizes yet). |
| 5 | `parse_blueprint_image_with_llm(png, min_rooms=6)`: new optional argument, default unchanged; the material finder passes 1. |
| 6 | The old page is replaced in place (same route `/materials/analyse`, same navbar link). |

Differences from the plan above:

- Jobs: only `stream_events` moved to `ai/jobs_common.py` (the floor plan re-imports it);
  the material finder has its own small `material_agent/jobs.py` with the same behaviour.
  The frontend `useJobEvents` hook takes an optional API base (default: floor plan).
- One vision call per analysis covers all its photos (up to 4), not one call per photo.
- **Changed after your first look (2026-11-17):** no focus chips and no space form. The page is
  just photo(s) + one prompt ("Analyze this interior design"). If the prompt names an area, only
  that area is analysed; if it contains a size ("TV wall 12 x 10 ft", "kitchen 10 x 8 ft"),
  quantities are calculated straight away. Otherwise sizes, projects and plans come through
  the follow-up chat.
- **Whole-design requests (2026-11-18):** new chat action `apply_all` ("replicate this design in
  my floor plan", "all quantities"). Every material goes on its natural surface (floor, walls,
  ceiling, platform, backsplash) of the room whose type matches the photo (kitchen photo ->
  Kitchen in the plan); it asks only what it cannot know (platform layout, which of several
  bedrooms / "All of them"). A plan sent with a general message applies the whole design; a
  request that names no single material is treated the same way.
- **Questions about the analysis (2026-11-18):** chat action `explain_quantity` (+ a richer
  `explain_material`). Answers "how did you calculate…", "why 10 % wastage", "why 3 sheets", "why
  quartz", "what did you assume" from the same facts the calculator used (`explain.py`: steps,
  size source, share source, rules). The LLM may phrase it (`prompts/material/material_answer.md`)
  but every number is checked against the facts; otherwise the step-by-step answer is shown.
- **Analysis tools (2026-11-18)** (`tools.py`, knowledge in `data/material_knowledge.json`,
  supporting-item rules in `data/material_rules.json`, all marked "to be verified"): alternatives
  for a material filtered for the place, swap and requantify ("use quartz instead"), suitability
  (wet / outdoor / near the hob / heavy traffic), compare two materials, care / durability /
  installation / pros and cons, supporting items (adhesive, grout, primer, putty, backing ply,
  sealer; counter tops get fixing sealant + sealer) shown as an "Also needed" table, set the
  share of a surface ("marble is 40% of the wall"; the others adjust), piece size ("2 x 4 ft
  tiles" -> buy count in pieces), totals across rooms, and general design advice. "This" means
  the material talked about last. The LLM phrases answers from the facts
  (`prompts/material/material_advice.md`); numbers are checked; money is still refused.
- The chat action for money questions is named `money_question` (no banned word in prompts).
- Uploaded photos are kept downscaled in `backend/.tmp/material_cache/images` (so "now only the
  ceiling" can re-analyse) and, best effort, in the `site-photos` bucket.

Checks: backend `tests/material_agent` (41 tests, incl. both worked examples, no-cost guards,
"no second vision call", "uploaded plan never writes plans", own-projects-only), full backend
suite green; frontend type check, lint, 70 tests (incl. a no-money-text guard), build.
