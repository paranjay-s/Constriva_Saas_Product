# 07 BOQ (bill of quantities)

Location: `backend/app/modules/sheets/` and `frontend/src/features/sheets/`. The BOQ flow takes a floor plan PDF and returns material rows, with PDF and Excel exports built from the same rows.

```
PDF upload -> parse (parsing module, cached) -> calculate (llm_mapper) -> rows -> table / PDF / Excel
```

## Status

The calculator produces the **seven core materials** (serials 1 to 7). Serials 8 to 59, the single wall model and the room-type rules are defined in `docs/materials_formula_spec.md`, which is not in the repository yet. Everything around the calculator (endpoint, row contract, category plan for all 59 serials, exports, UI) is in place and needs no change when those rows are added.

## Row contract

Every row, in the API, the exports and the UI:

| Field | Meaning |
|---|---|
| `serial_no` | 1 to 59. A split item carries a letter (`"17a"`, `"17b"`) and sorts after its number. |
| `item_code` | Stable code of the item. |
| `category_code`, `category`, `sub_category` | Placement from `CATEGORY_PLAN` in `boq_rows.py` (A to F). |
| `name`, `unit`, `quantity` | What to buy and how much. |
| `quantity_decimals` | 0 for counted units, 2 for measured units (`MEASURE_UNITS`). |
| `components` | Breakdown as `[{label, quantity, unit, quantity_decimals}]`. |
| `calc_type` | `geometry`, `count` or `allowance`. |
| `quote_status` | `INCLUDED` or `EXCLUDED_FROM_QUOTE`. |
| `note` | Free text shown in Remarks. |

Rows of the seven core materials also keep that material's earlier keys (`id`, `surface_tag`, `highlight_3d`, `secondary_quantity`, `secondary_unit`, `waste_multiplier`, `details`). The calculator's earlier output keys (`project_metadata`, `geometry_summary`, `materials`, `materials_by_key`, `level_summaries`, `room_breakdown`) are unchanged; `items` and `warnings` were added next to them.

## Endpoints (`/api/v1/sheets/boq`)

| Method and path | Purpose |
|---|---|
| `POST /` | Multipart `file` (PDF, up to 50 MB). Returns `202 {job_id}`. |
| `GET /jobs/{job_id}` | Job state with every event so far. |
| `GET /jobs/{job_id}/events` | SSE progress: `uploading`, `parsing`, `calculating`, then `done` or `failed`. |
| `GET /jobs/{job_id}/result` | The BOQ once the job is done (`409` before, or when it failed). |
| `POST /export/pdf`, `POST /export/xlsx` | Body: `items`, `warnings`, `geometry_summary`, `project_metadata` of a result. Returns the file. |

Every BOQ endpoint uses the same authentication as the project endpoints: the app's one dependency, `get_current_user`. A valid Bearer token identifies the user; an expired or invalid token gets `401`. A job belongs to the user who started it, and anyone else gets `404`. `tests/unit/test_boq_auth.py` pins this.

A failed job carries the parser's `error_code` (see [04-parsing-module.md](04-parsing-module.md)) and message. No other plan is ever used in place of one that could not be read.

Jobs run in an in-process thread pool and live in memory for one hour, like the floor plan and material finder jobs. This needs a single API worker.

## Files

| File | Purpose |
|---|---|
| `llm_mapper.py` | `map_plan_to_materials(plan)`: the calculator and its entry point (aliases `calculate_raw_materials_from_plan`, `generate_material_sheet`). |
| `constants.py` | Every engineering constant. The one place to recalibrate. |
| `boq_rows.py` | Row contract, `CATEGORY_PLAN`, units, rows of the core materials. |
| `boq_service.py` | PDF to result: parse, calculate, attach the source file name. |
| `boq_jobs.py` | Background jobs and their progress events. |
| `boq_router.py`, `boq_schemas.py` | Endpoints and their models. |
| `boq_export.py` | PDF and Excel from rows. Columns: S.No, Category, Sub-category, Material, Unit, Quantity, Remarks. |
| `export.py`, `service.py`, `router.py` | The earlier per-project cost sheet (unchanged). |

## Exports

- **Excel**: sheet `BOQ` with a frozen header row, an autofilter, numeric quantity cells and set column widths; sheet `Inputs and warnings` with the project facts, the geometry inputs and the warnings.
- **PDF**: project title, source file name, date and built area in the header; rows grouped by category; excluded items greyed and marked in Remarks; `Page X of Y`; footer "Estimated quantities from a 2D plan. Verify before procurement."

## Tests

`backend/tests/unit/test_boq.py`: row contract, category plan, calculator keys, determinism, the endpoints with a fake plan parser, and both exports.
