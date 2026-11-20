# 2D generator: architecture as found (feat/merged, d08ad48)

This describes the generator before the pro run changed it, and lists every limitation behind the
problems reported. Sections 7 and 8 describe what the pro run changed.

Code: `backend/app/modules/ai/floorplan/` (about 7,000 lines), prompts in
`backend/app/modules/ai/prompts/floorplan/`, frontend in `frontend/src/features/floorplan/` and the
chat studio. `app/modules/ai/floorplan_generator.py` (1,700 lines) is an older generator still
mounted by `app/modules/ai/router.py`; the studio uses the new one.

## 1. The chat model and prompts

| Step | Prompt | Model call |
|---|---|---|
| Brief: form + free text to a `Brief` | `brief_parser.md` | `GeminiClient.structured(..., schema=TextBrief)` |
| Room program: sizes and adjacency wishes | `room_program.md` | `structured(..., schema=ProgramDraft)` |
| Chat edit: message to typed operations | `edit_ops.md` | `structured(..., schema=EditInterpretation)` |

The client is `app/modules/ai/llm/client.py::GeminiClient`, built by `get_llm()` from
`FLOORPLAN_LLM_PROVIDER / _MODEL / _FALLBACK_MODEL` (defaults `gemini`, `gemini-3.5-flash-lite`,
fallback `gemini-3.5-flash`). `get_llm()` raises for any provider other than `gemini`. The
provider-neutral client (`llm/json_client.py`, adapters for Gemini and Anthropic, configured by
`PLAN_PARSER_LLM_*`) is used by the plan parser and by all 3D AI features, **not** by the
generator. Which model answered is not recorded on the plan version.

## 2. Request to rooms and constraints

`Brief` (plot in cm, bedrooms, `rooms: list[RoomRequest]`, `preferences`, `pool_layout`) ->
`requirements.expand_rooms` (fixed ids, attached baths and dresses) -> `room_program.build_program`
(LLM sizes, then code clamps to minimums and scales the total to `PROGRAM_PLOT_SHARE` = 75–88% of
the plot) -> `RoomProgram` (rooms with target area and zone, `adjacency` wishes with weights,
`pool_layout`).

Preferences the brief can carry: `adjacent`, `near`, `away_from`, `on_side` (one room to one room or
one side). The whole plot is the layout area; there is no setback, no built-up target and no
plot/built-up question.

## 3. The solver and its rule language

`pipeline/layout/engine.py::generate_layout`: first a row template (`templates.compact_rows`), then
OR-Tools CP-SAT (`solver.py::solve_layout`): rooms are axis-aligned rectangles on a 15 cm grid
(`grid.py`), `AddNoOverlap2D`, minimum side and area per type, area within ±18% of target,
aspect-ratio limits, a door-length shared wall between each room and its topology parent
(`topology.py`, a tree rooted at the entrance room), the entrance room and parking on the road
edge. Soft objective: covered area, rooms near target, habitable rooms on an exterior wall,
weighted adjacency wishes, public near the road and private/pool away from it, garden on the road
side. Leftover space is grown into by neighbours (`fill_gaps`), then turned into shafts joined to
an adjacent outdoor area (`fill_holes_with_shafts`, `join_outdoor`). Time limit
`FLOORPLAN_SOLVER_TIME_S` = 8 s per attempt; up to `FLOORPLAN_MAX_ATTEMPTS` = 3 attempts with the
validator's errors fed back to the LLM sizing step.

Hard wishes the solver can take from an edit: `anchors` (room touches plot edges), `adjoin` (pairs
share ≥ 1 m of wall, **pairwise only**), `sizes`, `area_bounds`. Special pool layouts (`centre`,
`u_shape`, `two_block`) have hand-written constraint sets (`_pool_layout_rules`).

Doors are placed by code after solving (`openings.place_doors`): one door per topology link, the
entrance door on the road side. Open-area types (`garden`, `parking`, `balcony`, `pool`) get **no
door**: they are "reached from outside" (`OPEN_EDGE`). Windows go on exterior walls of habitable
rooms; fixtures from a small symbol set (`render/symbols.py`).

## 4. Edits

`pipeline/edit_engine.py`: the LLM turns a message into typed operations (`schemas/edit_ops.py`:
resize, move to an anchor or next to one room, swap, add, remove, rename, plot, door/window ops,
pool layout, facing, rotate, mirror, units, undo). Layout operations are re-solved in widening
steps: (1) only named rooms move into spare garden, (2) neighbours too, (3) everything, only with
`allow_reflow`. Rooms not named are locked. If no step yields a valid plan, the plan is unchanged
and alternatives are listed. Anything the prompt lists as unsupported goes into
`EditInterpretation.unsupported` and the reply starts "Not supported in this tool: ...".
Versions: every successful edit snapshots the previous plan (`service._snapshot`, `MAX_HISTORY`),
undo/revert restore one.

## 5. Renderer

`render/svg_renderer.py` draws, in cm units: zone-coloured room fills (cream, lavender, blue-grey),
green hatch for open areas, a bright blue pool with ripple lines and beige paving, coloured fixture
symbols, dark wall outlines (exterior 23 cm, interior 12 cm), blue windows, red door arcs, navy
labels with magenta sizes, dimension lines on two sides plus overall dimensions, a north arrow and a
four-cell title block (project, owner, floor name, total area). Font: Helvetica/Arial. No scale is
stated; the sheet is sized to the plot, not to A3/A1.

## 6. Outputs

`render/exports.py`: SVG (the renderer), PDF (PyMuPDF converts the SVG; the plan id goes into the
PDF Keywords as `constriva-plan:<uuid>;v=<n>`), PNG (raster of the SVG), DXF (`dxf_renderer.py`:
layers WALLS, DOORS, WINDOWS, FURNITURE, HATCH, TEXT, DIMENSIONS, PLOT, in cm). No DWG, no IFC.
Legacy PlanJSON for BOQ and the 3D viewer comes from `legacy_plan_json.py` (rooms as rectangles,
walls as merged centre lines). The 3D gateway uses the stored plan only when the **plan's owner**
uploads the PDF (`plan3d/router.py`, `stored_plan_for_pdf`); anyone else, and the BOQ upload, read
the drawing again.

## Limitations behind each reported problem

| Problem reported | Cause in the code |
|---|---|
| Too bright | `ZONE_FILL` pastel room fills, `POOL_COLORS` saturated blue water, red door arcs, blue windows, magenta size text, navy labels, coloured furniture (`svg_renderer.py`, `symbols.FILLS`). |
| Not like a CAD drawing, font not professional | One wall colour with no ISO line-weight hierarchy; no hatched cut walls; no sheet size or scale; dimension chains only on two sides; Helvetica/Arial; furniture drawn as filled coloured shapes. |
| Large areas give too much to the garden | Program targets are scaled to 75–88% of the plot but capped by `ROOM_SCALE_UP_MAX` = 1.4× typical sizes, so on large plots the rooms stop growing and `with_spare_garden` + `fill_gaps` hand all leftover area to a garden that grows without limit (`OPEN_GROW`). No built-up target, no coverage band, no setbacks. nandu: plot about 5,000 sq ft, rooms 1,987 sq ft (about 40%), lawn about 2,250 sq ft. |
| "Not supported in this tool: pool attached to multiple specific rooms simultaneously" | The edit language has `move_room next_to` **one** room and `adjoin` pairs only; the prompt tells the LLM to put anything else in `unsupported`; the pool has no doors (`OPEN_EDGE`), so "a door onto the pool" has no operation either. |
| "could not be arranged" / still refused after "break the plan" | Re-layout widens only to "everything may move" with the *same* program and the old topology; there is no full re-solve from the brief with new rules, no larger time budget, and no report of which rules conflict. "Break the plan" sets `allow_reflow` at most. |
| No fixtures, scale bar, revision info, layered CAD, DWG | Fixture set is 17 furniture symbols (no hob, sink, fridge, shower tray as separate blocks); no scale bar; title block has 4 fields and no revision table; DXF layers are ad hoc names in cm; no DWG or IFC export. |
| 3D does not read generated plans properly | Measured on a nandu-like plan generated without the AI and passed through `legacy_plan_json` then `plan3d.convert.planjson_to_planto3d`: the PlanTo3D floor `size` is the house's bounding box (44 × 36 ft) while the pool (14 × 35 ft) and garden lie outside it; BAR, PUJA and GAMING ROOM arrive as the generic type `room` although `rooms.json` has `bar` and `puja` (the legacy PlanJSON tags them `other`); the STAIR room has no stair geometry (`stairs: []`); pool water and walkway are one rectangle. The stored plan is used only when the plan's owner uploads the PDF; anyone else's upload and every BOQ upload re-read the drawing. |

## 7. What the pro run changes (summary; details in RULES.md and the code docstrings)

See SUMMARY.md, PART 1, for the final state and measurements.
