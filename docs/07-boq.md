# 07 BOQ (bill of quantities)

Location: `backend/app/modules/sheets/` and `frontend/src/features/sheets/`. The BOQ flow takes a floor plan PDF and returns material rows, with PDF and Excel exports built from the same rows.

```
PDF upload -> parse (parsing module, cached) -> calculate (llm_mapper) -> rows -> table / PDF / Excel
```

## The calculator

[materials_formula_spec.md](materials_formula_spec.md) is the source of truth for every quantity: the room types, the derived quantities, the 59 formulas, the warnings and the test fixture. The code follows it section by section.

```
PlanJSON -> measure each level -> PlanFacts -> derive_primitives -> Primitives -> compute_items -> rows
            (llm_mapper)          (spec section 1)                  (section 3)   (section 4)
```

| Step | Where | What it does |
|---|---|---|
| Room kind and type | `plans/room_types.py` | `boq_kind` of each room and `boq_type` of each indoor room (spec section 2). Shared with the plan parser, which writes them; the calculator derives them when a stored plan has none. `room.kind` is read and never changed. |
| Measure | `llm_mapper._measure_level` | Applies the unit scale, then measures rooms, wall areas, openings and bounding boxes of one level. |
| Derive | `primitives.derive_primitives` | The derived quantities, computed once per plan: wet and dry areas, room counts, the roof level, and the wall model (`A_ext`, `A_int`, `A_gyp_wall`, `A_cem`, `s_gyp`, `s_cem`). |
| Formulas | `formulas.compute_items` | One formula per item, written as the spec states it. Pure functions of numbers, so they are tested without a drawing. |
| Rows | `boq_rows.build_boq_rows` | 64 rows from the catalog: 59 items, with 17, 18, 47, 53 and 57 split into two lettered rows. |

Rules that hold everywhere:

- **Items 8 to 59 are project scope only.** The seven core materials (items 1 to 7) are also given per level and per room, from `_compute_7_materials_for_scope`. That engine takes the plan's `s_gyp` and `s_cem`, so room and level values add up to the project totals. The top level carries the parapet and the ground level the plinth.
- **Project totals come from project-level quantities**, never from adding up rooms.
- **`ceil` is `math.ceil(round(x, 6))`** and waste is applied once, at the end of a formula.
- **Nothing is invented.** A room or opening the plan does not show gives 0 and a warning.
- **Apartment rule.** When `building_type` is `apartment`, items 8, 10, 20, 21, 22, 23, 26, 30, 31, 53b and 58 are 0 with a note, and a warning says composite items still include roof and plinth terms.
- **Every number is a named constant** in `constants.py`.

### Assumptions

A user can set six things, in `BoqAssumptions` (`boq_schemas.py`). Each default is what the calculator does on its own:

| Assumption | Default | Effect |
|---|---|---|
| `building_type` (villa, apartment, other) | the plan's own, or villa | `apartment` applies the apartment rule |
| `ceiling_height_m` | each level's height from the plan, 3.35 m where it states none | one height for every level: wall areas and everything built on them |
| `tile_size_mm` (600x600, 800x800, 1200x600) | 600x600 | tile pieces and grout |
| `tile_pattern` (standard, herringbone) | standard | tile waste, 5% or 15% |
| `false_ceiling_share` (0 to 1) | 1 | regular gypsum board (18b) |
| `plot_perimeter_m` | none: estimated from the plan outline | site hoarding (58) |

The result states what was used under `assumptions`, with where each value came from (`user`, `plan`, `default`, `assumed`). Both exports print it.

Changing an assumption never parses the PDF again. A BOQ job keeps the PlanJSON it parsed, and `POST /jobs/{job_id}/recalculate` calculates from that: no model call, no upload. The job lives for one hour; after that the PDF is uploaded again, which the parser's caches answer without a model call.

The result also carries `derived_quantities`: every symbol of spec section 3 for this plan, for checking a quantity by hand.

Warnings the calculator adds: parking under an upper floor is counted as paved outdoor area; no bathroom or kitchen detected; doors look under-read (fewer doors than bathrooms plus bedrooms); more than 30% of the indoor area has no recognised room type; opening widths absent (items 28 and 29 are 0); no paved outdoor rooms (items 22 and 23 are 0); the exterior wall area was capped by the net wall area; the gypsum-plastered wall area was clamped to 0; no built area.

## Row contract

Every row, in the API, the exports and the UI:

| Field | Meaning |
|---|---|
| `serial_no` | 1 to 59. A split item is two rows with a letter (`"17a"`, `"17b"`), which sort after their number. |
| `item_code` | Stable code of the item. |
| `category_code`, `category`, `sub_category` | Placement from `CATEGORY_PLAN` in `boq_rows.py` (A to F). |
| `name`, `unit`, `quantity` | What to buy and how much. `quantity` is the exact value of the formula. |
| `quantity_decimals` | How to show the quantity: 0 for counts and for quantities the formula rounds up, 2 for measures. |
| `components` | Breakdown of one product as `[{label, quantity, unit, quantity_decimals}]`: rods of steel, tonnes of sand, tile pieces, boards, cable coils, sockets and switches, breakers, tank sizes. |
| `calc_type` | `geometry`, `count` or `allowance`. |
| `quote_status` | `INCLUDED` or `EXCLUDED_FROM_QUOTE`. |
| `note` | Free text shown in Remarks. |

Rows of the seven core materials also keep that material's earlier keys (`id`, `surface_tag`, `highlight_3d`, `secondary_quantity`, `secondary_unit`, `waste_multiplier`, `details`). The rows use the spec's units (steel in tonnes with kg and rods in its breakdown, sand and aggregate in m³, tiles in m²); `materials_by_key` keeps the units it always had (tonnes, pieces). The calculator's earlier output keys (`project_metadata`, `geometry_summary`, `materials`, `materials_by_key`, `level_summaries`, `room_breakdown`) are unchanged; `items`, `warnings` and `derived_quantities` were added next to them.

## Endpoints (`/api/v1/sheets/boq`)

| Method and path | Purpose |
|---|---|
| `POST /` | Multipart `file` (PDF, within the upload limits of [04-parsing-module.md](04-parsing-module.md)), plus the optional assumption fields. Returns `202 {job_id}`. |
| `GET /jobs/{job_id}` | Job state with every event so far. |
| `GET /jobs/{job_id}/events` | SSE progress: `uploading`, `parsing`, `calculating`, then `done` or `failed`. |
| `GET /jobs/{job_id}/result` | The BOQ once the job is done (`409` before, or when it failed). |
| `POST /jobs/{job_id}/recalculate` | JSON `BoqAssumptions`. Returns the BOQ calculated again from the job's parsed plan, and makes it the job's result. No model call. `409` when the job is not done. |
| `POST /export/pdf`, `POST /export/xlsx` | Body: `items`, `warnings`, `geometry_summary`, `project_metadata` and `assumptions` of a result. Returns the file. |

Every BOQ endpoint uses the same authentication as the project endpoints: the app's one dependency, `get_current_user`. A valid Bearer token identifies the user; a missing, expired or invalid token gets `401` (see "Authentication" in [02-backend-structure.md](02-backend-structure.md)). A job belongs to the user who started it, and anyone else gets `404`. `tests/unit/test_boq_auth.py` pins this.

A failed job carries the parser's `error_code` (see [04-parsing-module.md](04-parsing-module.md)) and message. No other plan is ever used in place of one that could not be read.

Jobs run in an in-process thread pool and live in memory for one hour, like the floor plan and material finder jobs. This needs a single API worker.

## Files

| File | Purpose |
|---|---|
| `llm_mapper.py` | `map_plan_to_materials(plan)`: reads the plan, measures it and returns the bill (aliases `calculate_raw_materials_from_plan`, `generate_material_sheet`). Also the seven-material engine for room and level scopes. |
| `primitives.py` | `PlanFacts` (what is measured), `Primitives` (the derived quantities) and `derive_primitives`. |
| `formulas.py` | `compute_items`: the 59 formulas. `calculation_warnings`. The apartment rule. |
| `constants.py` | Every engineering constant. The one place to recalibrate. |
| `boq_rows.py` | Row contract, `CATALOG` (name, unit, type and quote status of each of the 64 rows), `CATEGORY_PLAN`. |
| `boq_service.py` | PDF to result: parse, calculate, attach the source file name. |
| `boq_jobs.py` | Background jobs and their progress events. |
| `boq_router.py`, `boq_schemas.py` | Endpoints and their models. |
| `boq_export.py` | PDF and Excel from rows. Columns: S.No, Category, Sub-category, Material, Unit, Quantity, Remarks. Rows are ordered by `group_sort_key` (in `boq_rows.py`). |
| `export.py`, `service.py`, `router.py` | The earlier per-project cost sheet (unchanged). |

## Exports

Both files carry every row the result has (64 for a full bill), a lettered row on a line of its own. Rows are grouped by category, then sub-category, then serial number, so a sub-category whose serials are not consecutive stays together (Painting is 17a, 17b, 19, 21). The API itself returns rows in serial order; the table on the BOQ page groups them the same way.

Remarks reads: "Excluded from quote" and "Allowance" when they apply, then the row's breakdown (`components`, such as `Ground tank: 2,000 L; Roof tank: 1,500 L`), then its note.

- **Excel**: sheet `BOQ` with a frozen header row, an autofilter, numeric quantity cells and set column widths; sheet `Inputs and warnings` with the project facts, the geometry inputs (including the wall-model areas), the assumptions and the warnings.
- **PDF**: project title, source file name, date, built area and the assumptions in the header; one band per category; excluded items greyed and marked in Remarks; `Page X of Y`; footer "Estimated quantities from a 2D plan. Verify before procurement."

## Tests

- `backend/tests/unit/test_boq_formulas.py`: the fixture of spec section 8 on the formula layer (every derived quantity and all 64 rows), one test per edge case of section 7, every warning, the apartment rule, and that room and level values add up to the project totals.
- `backend/tests/unit/test_boq.py`: row contract, category plan, calculator keys, determinism, the endpoints with a fake plan parser, and both exports with the full 64-row bill (grouping, lettered rows, breakdowns).
- `frontend/src/features/sheets/boqFullBill.test.tsx`: the table, filters and export request with the full bill. Its data, `boqFullBill.fixture.json`, is the spec's section 8 fixture as the API returns it. The backend writes that file and `test_the_frontend_fixture_is_the_bill_this_backend_produces` fails when it is stale; rewrite it with `BOQ_WRITE_FIXTURE=1 uv --directory backend run pytest tests/unit/test_boq_formulas.py`.
