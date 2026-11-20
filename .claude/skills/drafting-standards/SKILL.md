---
name: drafting-standards
description: The house rules for Constriva's 2D floor plan generator - the mm building model, plot/built-up areas and setbacks, the solver rule language and full re-solve, the muted ISO 128 CAD drawing look, PDF/SVG/PNG/DXF/IFC/DWG exports and the Dubai villa engineering checks. Use it whenever you touch backend/app/modules/ai/floorplan/, its prompts in backend/app/modules/ai/prompts/floorplan/, the floorplan or studio frontend, or when you generate, export, check, compare or explain a 2D plan, even if the request only says "plan", "drawing", "layout", "CAD" or "make it look professional".
---

# Drafting standards for the 2D generator

Source of the values: `docs/pro/2d/RESEARCH.md` and `docs/pro/2d/RULES.md` (Dubai Building Code
2021 Part K, ISO 128, US NCS layers). Every engineering value is a setting in
`app/modules/ai/floorplan/rules.py` or `settings.py`, never inline, and is marked "to be confirmed
against the Dubai Building Code by an engineer".

## 1. One building model

- `app/modules/ai/floorplan/model/building.py::Building` is the single source of truth: millimetres,
  every coordinate a multiple of 50 mm, y grows south, origin at the plot's north-west corner.
- It holds storeys, walls (type, thickness: exterior 200 mm, interior 100–150 mm), doors and windows
  hosted in a wall (width, height, sill, swing side and direction, kind hinged/sliding/opening),
  rooms (name, type, polygon, net and gross area, finish), fixtures, stairs (risers, treads,
  flights, up direction), site elements (plot, setbacks, pool, garden, lawn, courtyard, parking,
  driveway, dock, boundary wall, gate) and north.
- Every drawing and export is made from `Building`, never from `FloorPlan` directly.
  `Building -> PlanJSON 2.0` (BOQ) and `Building -> PlanTo3D plan` (3D) are lossless and tested.
- Geometry checks use Shapely. The solver is OR-Tools CP-SAT.

## 2. Areas

- Ask once whether a stated area is the plot or the built-up area unless the words say it.
- Default split 70% built-up / 30% exterior (`FLOORPLAN_BUILT_UP_SHARE`), kept within 65–75%
  only when the user gives no built-up area. A built-up area, share or plot size the user states
  always wins; unusual coverage gets a note, never a refusal (cut only to what physically fits).
- Setbacks are settings, default 0 (owner's decision, feat/pro_2); the user can ask for them in
  the brief or in chat (`set_setbacks`). Enclosed rooms stay inside the setback line; everything
  stays inside the plot.
- Report exactly: `Total area 5,000 sq ft (3,500 sq ft built-up + 1,500 sq ft exterior)`, then the
  same in m², then coverage %. Room gross areas add up to the built-up area within 1%; report net
  and gross.

## 3. Chat and solver

- AI calls go through the provider-neutral settings (`PLAN_PARSER_LLM_*`, `json_client`); record
  the model on every version.
- Never answer "not supported" for a spatial request. Translate it into rules: `touches` (one room
  to several), `door_between`, `side` (front/rear/left/right of the facing), `zone`, size and aspect
  bounds, `daylight`. Outdoor areas are solver objects and can take doors.
- If an edit cannot fit, re-solve from the brief with all rules. "Break the plan", "start over" and
  similar always force a full re-solve with the larger budget (`FLOORPLAN_FULL_RESOLVE_S`, 30 s),
  with progress in chat. If still impossible, name the conflicting rules and offer the two
  closest layouts that work.

## 4. Drawing look

- Black and greys on white. Colour only as light hatches: water, lawn, paving. No room fills.
- ISO 128 weights at 1:100: exterior walls 0.70 mm with dark solid fill; interior walls 0.50 mm,
  grey fill; doors, windows, stairs 0.25 mm; arcs, glazing, fixtures, furniture 0.18 mm; hatches and
  dimensions 0.13 mm; overhead elements dashed; setbacks and plot boundary chain lines.
- Symbols: hinged door = leaf + 90° arc; sliding door = offset leaves + arrow; window = frame on
  both faces + glazing lines; stair = treads, walking line with arrow, UP/DN, cut line. Fixtures
  and furniture are reusable blocks; one minimal furniture set per room, switchable off.
- Font: Jost (OFL), fixed sizes only. Room name, size and area in every room; no text overlaps
  lines or other text.
- Dimension chains on all four sides plus room dimensions; chain segments add up exactly.
- Sheet A3 (A1 option) at a stated scale with scale bar, north arrow, legend and title block
  (project, client, title, drawing number, scale, date, revision table, area schedule, logo
  placeholder, "For design purposes only, not for construction"). The in-app preview uses the
  same renderer.

## 5. Outputs

- PDF (vector, true scale), SVG, PNG. DXF via ezdxf in mm with AIA/US NCS layers (`A-WALL`,
  `A-DOOR`, `A-GLAZ`, `A-FLOR-FIXT`, `A-FURN`, `A-FLOR-STRS`, `A-ANNO-DIMS`, `A-ANNO-TEXT`,
  `L-SITE-*`, `C-PROP`), blocks for doors and fixtures, real DIMENSION and HATCH entities; must pass
  `ezdxf.audit` and open in FreeCAD headless. IFC4 via IfcOpenShell; validated and opened in
  FreeCAD. DWG via the chosen converter (DEPENDENCIES.md), read back to verify.
- Every PDF carries the plan id and the building model as a signed attachment; 3D and BOQ readers
  use a valid attachment directly.

## 6. Engineering checks

Run on every version; show issues in chat and in the notes panel; never deliver a plan with a
critical issue without saying so. Checks: room minimum size and width by type, door widths,
corridor widths, window on an exterior wall for habitable rooms, bathroom ventilation, stair
riser/tread/headroom, kitchen work triangle, wet areas stacked between storeys, every room has a
door, coverage and setbacks.

## Things that undo the work

- Tuning a rule to one drawing: the generator serves every plot, so a rule that fixes the nandu
  plan but not the held-out samples is a regression.
- Shipping non-commercial code, weights or data (HouseDiffusion, House-GAN++, Graph2Plan, RPLAN):
  the product is commercial; those stay in `tools/vendor-eval/` as reading material.
- Claiming 100% accuracy: report measured numbers and the sample size.
- Colour fills in rooms or a missing "For design purposes only, not for construction" label: the
  first breaks the premium CAD look the owner asked for, the second exposes the firm to liability.
