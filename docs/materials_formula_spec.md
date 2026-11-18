# Materials Formula Spec: 59 items (UAE)

Version 1.2. Source of truth for the BOQ material calculator. Quantities are estimates from a 2D plan. Items typed A are allowances.

Changes in 1.2: `boq_kind` (parking is paved outdoor area; semi-open wet rooms are indoor), whole-word abbreviations in the room-type rules, combined dressing and toilet rooms, small pantries, item 58, item 53b in the apartment rule, the steel row in tonnes, a warning for under-read doors, and the double-height exterior wall noted as a known limit.

## 0. Conventions

- All inputs are in metres after `unit_scale`. Areas in m², lengths in m.
- `[x]` is 1 if x is true, else 0.
- `ceil(x)` always means `math.ceil(round(x, 6))`.
- `clamp(x, lo, hi) = min(max(x, lo), hi)`.
- Kind always means `boq_kind` (section 2). Built rooms have `boq_kind` `indoor` or `semi_open`. Indoor rooms have `boq_kind` `indoor`.

## 1. Inputs read from PlanJSON

| Input | Source | Default if missing |
|---|---|---|
| `A_r`, `P_r` per room | polygon | none |
| `room.kind` per room | plan, else `_classify_room_kind` | derived from the name |
| `boq_kind` per room | `room.boq_kind`, else derived by section 2 | derived |
| `boq_type` per indoor room | `room.boq_type`, else derived by section 2 | derived |
| `A_built`, `A_built_l`, `A_ground` | existing code (built rooms) | none |
| `A_netwall`, `A_netwall_0` | `a_net_wall_total`, `a_net_wall_ground` | none |
| `N_door`, `N_win`, `L` (levels) | existing code | 0 |
| `H_l` | `_resolve_room_height_m({}, lvl)` | 3.35 |
| Opening `width`, `height` (optional) | `openings[]` | door 0.90 × 2.10, window 1.20 × 1.20 |
| `building_type` (optional) | plan, or user input | villa |
| `f_fc`, plot perimeter (optional user inputs) | request parameter | 1.0, none |
| Ceiling height, tile size, tile pattern (optional user inputs) | request parameter | per level, 600 × 600, standard |

## 2. Room kind and type (`boq_kind`, `boq_type`)

`room.kind` and `room.type` belong to the 3D adapter. The BOQ never changes them, and never reads `room.type`. Both BOQ keys are derived in one shared module and stored on the room; a plan stored without them gets them derived the same way.

### 2.1 `boq_kind`

Start from `room.kind`. The first matching rule wins:

1. A void stays a void.
2. The lowercased name contains parking, car park, car porch, carport or driveway: `boq_kind = outdoor`. The room is paved area (`A_pave`, `P_pave`) and is not part of the built area.
3. `room.kind` is `semi_open` and the first matching rule of section 2.2 for the name is BATH, KITCHEN or LAUNDRY: `boq_kind = indoor`, and the room is typed.
4. Otherwise `boq_kind = room.kind`.

Stairs, verandahs, balconies and terraces therefore stay semi-open. Every use of kind in this spec, including items 1–7 and the bounding boxes, is `boq_kind`.

### 2.2 `boq_type`

Only rooms with `boq_kind` `indoor` are typed. Lowercase the room name; the first matching rule wins. A rule matches when the name contains one of its keywords, or when one of its abbreviations is a whole word of the name. Words are the runs of letters in the name, so `KIT.`, `DRG./DIN.` and `BR-2` give the words kit; drg, din; br.

| # | Type | Keywords (anywhere in the name) | Abbreviations (whole words) |
|---|---|---|---|
| 1 | BATH | bath, toilet, toi, wc, w.c, washroom, powder, lavatory, restroom, shower, ensuite | bth |
| 2 | KITCHEN | kitchen, pantry | kit |
| 3 | LAUNDRY | laundry, utility, wash | util |
| 4 | CIRC | hallway, corridor, passage, lobby, foyer, stair, lift, entrance | |
| 5 | LIVING | living, majlis, family, lounge, drawing, sitting | drg, liv, lvg |
| 6 | DINING | dining | din |
| 7 | STORE | store, storage, closet, dress, wardrobe | |
| 8 | BED | bed, master, guest, maid, driver, nanny | br, bdr, mbr |
| 9 | STUDY | study, office, library | |
| 10 | LIVING | hall | |
| 11 | OTHER | everything else | |

- The rules are primary. If they return OTHER and the parser's model supplied a valid `boq_type` for that room, use the model's value. This covers Arabic labels and abbreviations not listed here.
- Open-plan kitchen: if a name matches KITCHEN and also matches the LIVING or DINING rule (rules 5, 6 or 10, keywords or abbreviations), the room is LIVING and one kitchen is counted. Its kitchen portion is `A_k = min(12, A_r / 3)` with `P_k = 4 × sqrt(A_k)`. Add `A_k` to `A_kit`, `P_k` to `P_kit`, 1 to `N_kit`, and 6 sockets to item 33. For every other formula the room is a LIVING room with its full area.
- Small pantry: a room that matches KITCHEN only through the keyword pantry and has `A_r < 4` is STORE, not KITCHEN.
- Combined dressing and toilet: a room that matches BATH and whose name also contains dress, closet or wardrobe is BATH with a bath portion `A_b = A_r / 2` and `P_b = 4 × sqrt(A_b)`. For every other BATH room `A_b = A_r` and `P_b = P_r`. `A_b` and `P_b` are what `A_bath`, `P_bath`, `N_shower`, wall tiles, waterproofing and the bathroom lights (item 40) use. The other half of a combined room is dry area. For every other formula the room is a BATH room.

## 3. Derived quantities (computed once per plan)

| Symbol | Definition |
|---|---|
| `A_in` | sum of `A_r` over indoor rooms |
| `A_bath`, `P_bath`, `N_bath` | sum of `A_b`, sum of `P_b`, count of BATH rooms (section 2.2) |
| `N_shower` | BATH rooms with `A_b ≥ 2.5` |
| `A_kit`, `P_kit`, `N_kit` | KITCHEN rooms plus open-plan kitchen portions |
| `A_lau`, `P_lau`, `N_lau` | LAUNDRY rooms |
| `A_wet`, `P_wet` | bath + kitchen + laundry |
| `A_dry` | `max(A_in − A_wet, 0)` |
| `N_bed`, `N_liv`, `N_din` | counts by type |
| `N_ac` | sum of `ceil(A_r / 40)` over BED, LIVING, DINING, STUDY, KITCHEN, OTHER rooms with `A_r ≥ 6` |
| `N_wh` | `N_bath + N_kit` |
| `P_ext_l` | `2 × (W_l + D_l)`, bounding box of built rooms on level l (walls' box if the level has no rooms) |
| `l*` | level with the largest `A_built_l`, lowest index on ties |
| `A_roof`, `P_roof`, `d_roof` | `A_built` of `l*`, `P_ext` of `l*`, `min(W, D)` of `l*` |
| `G_ext` | sum over levels of `P_ext_l × H_l` |
| `A_ext` | `min(max(G_ext − 1.44 × N_win, 0.5 × G_ext), A_netwall)` |
| `A_int` | `A_netwall − A_ext` |
| `A_plinth` | `0.25 × A_netwall_0` |
| `A_parapet` | `1.0 × P_roof` (parapet height 1.0 m) |
| `A_masonry` | `A_netwall + A_plinth + A_parapet` |
| `T_wall` | `2.07 × P_bath + 0.30 × (P_kit + P_lau)` |
| `T_floor` | `A_built + 0.10 × ΣP_r` over built rooms |
| `A_gyp_wall` | `max(2 × A_int + A_ext − T_wall, 0)` (interior painted and gypsum-plastered wall faces) |
| `A_cem` | `2 × A_netwall − A_gyp_wall + 2 × A_parapet` (cement-plastered faces: exterior, wet walls, parapet) |
| `s_gyp`, `s_cem` | `s_gyp = A_gyp_wall / (2 × A_netwall)` if `A_netwall > 0` else 0; `s_cem = 1 − s_gyp` |
| `E_net` | `A_ext + 2 × A_parapet` |
| `V_dry` | `A_built × 0.115 × 1.35 × 1.54` |
| `A_pave`, `P_pave` | outdoor rooms whose name has no lawn, garden, grass, plant or pool. Parking and driveways are outdoor by section 2.1 |
| `P_site` | bounding-box perimeter of all rooms of any kind on level 0 |

Identity to test: when `A_gyp_wall` is not clamped, `A_cem = E_net + T_wall`.

Known limit: `G_ext` uses the level height `H_l`, while `A_netwall` uses each room's own height. A double-height room on an exterior wall therefore has its exterior wall area understated and its interior wall area overstated by the same amount.

## 4. Formulas

Type: G = geometry, C = room counts, A = allowance (overridable input). EXCL = excluded from quote, quantity still computed.

### Group A (1–7)

Constants, units and output keys stay as in the existing code. Only the wall areas change: the fixed 65/35 share and `4 × sqrt(A_ground)` are replaced by the wall model in section 3.

| # | Material | Unit | Formula |
|---|---|---|---|
| 1 | AAC blocks | pieces | `ceil(A_masonry / 0.12 × 1.05)` |
| 2 | Steel rebar | t | kg = `(34 × A_ground + 22 × A_built) × 1.10`; tonnes = `kg / 1000`; rods = `ceil(kg / 10.656)` |
| 3 | Cement | 50 kg bags | `ceil((V_dry / 5.5 × 28.8 + 0.10 × A_masonry + 0.14 × A_cem) × 1.05)` |
| 4 | Sand | m³ | `1.5 / 5.5 × V_dry + 0.012 × A_masonry + 0.018 × A_cem + 0.025 × A_built`; tonnes = `m³ × 1.55 × 1.05` |
| 5 | Coarse aggregate | m³ | `3 / 5.5 × V_dry × 1.05`; tonnes = `m³ × 1.50` |
| 6 | Gypsum plaster | 30 kg bags | `ceil((0.012 × A_gyp_wall + 0.006 × A_built) × 1.15 × 1000 / 30)` |
| 7 | Floor tiles and skirting | m² | `T_floor × w`, w = 1.05 or 1.15; pieces = `ceil(m² / tile area)` |

Room and level scopes for items 1–7: pass `s_gyp` and `s_cem` into `_compute_7_materials_for_scope` in place of the two share constants. Gypsum wall area for a scope is `2 × s_gyp × a_net_wall`. Cement plaster area for a scope is `2 × s_cem × a_net_wall + 2 × a_parapet_wall`. The top level carries `A_parapet`. Room and level values must sum to the project totals.

### Group B (8–23)

| # | Material | Unit | Formula | Type |
|---|---|---|---|---|
| 8 | PU spray foam | m² | `(A_roof + 0.30 × P_roof) × 1.05` | G |
| 9 | Bitumen coating | L | `ceil((0.30 × A_roof + 0.50 × (2 × A_plinth + 0.50 × A_ground)) × 1.05)` | G |
| 10 | Lightweight screed | m³ | `A_roof × t × 1.05`, `t = clamp(0.05 + 0.0025 × d_roof, 0.06, 0.15)` | G |
| 11 | Waterproofing coat | kg | `ceil((1.2 × (A_roof + 0.30 × P_roof) + 1.5 × (A_wet + 0.30 × P_wet + 3.0 × N_shower)) × 1.05)` | G |
| 12 | Wet-area wall tiles | m² | `T_wall × 1.10` | G |
| 13 | Tile grout | kg | `ceil((g × T_floor + 0.255 × T_wall) × 1.10)`, `g = 51 × (a + b) / (a × b)` for an a × b mm floor tile | G |
| 14 | Cleaning solvents | L | `ceil(0.08 × A_built)` | A |
| 15 | Marble thresholds and sills | LM | `(0.90 × (N_bath + N_kit + N_lau + [A_built > 0]) + Σ(w_window + 0.10)) × 1.05` | C |
| 16 | Ceramic niches | m² | `(0.40 × N_shower + 1.50 × N_liv) × 1.10` | A |
| 17a | Interior wall paint | L | `ceil(A_gyp_wall × 2 / 9 × 1.05)` | G |
| 17b | Interior wall primer | L | `ceil(A_gyp_wall / 10 × 1.05)` | G |
| 18a | MR gypsum board | m² | `1.10 × A_wet`; boards = `ceil(m² / 2.88)` | G |
| 18b | Regular gypsum board | m² | `1.10 × f_fc × A_dry`; boards = `ceil(m² / 2.88)` | G |
| 19 | Ceiling paint | L | `ceil(A_built × 2 / 9 × 1.05)` | G |
| 20 | Exterior plaster | m² | `E_net × 1.05` | G |
| 21 | Exterior paint | L | `ceil(E_net × 2 / 6.5 × 1.05)` | G |
| 22 | Interlock paving (EXCL) | m² | `A_pave × 1.05` | G |
| 23 | Kerbstone (EXCL) | LM | `0.75 × P_pave × 1.05`; pieces = `ceil(LM / 0.915)` | G |

- Item 12 is wall tiles only; wet floors are inside item 7. Baths are tiled from the skirting to 2.40 m with 10% off for openings (2.30 × 0.90 = 2.07). Kitchens and laundries get a 0.60 m splashback on half the perimeter.
- Item 13: `g` is 0.17 for 600 × 600 and 0.1275 for 800 × 800 or 1200 × 600 (3 mm joint, 10 mm depth). 0.255 is the same formula for 300 × 600 wall tiles.
- Item 9: roof primer at 0.30 L/m², plus two coats at 0.25 L/m² on both faces of plinth walls and on footings taken as half the footprint.

### Group C (24–31)

| # | Material | Unit | Formula | Type |
|---|---|---|---|---|
| 24 | Ceiling access hatches | Nos | `N_ac + N_bath` | C |
| 25 | Aluminium canopy / AC screen | Nos | `ceil(N_ac / 2)` | A |
| 26 | Steel access ladder | Nos | `[A_built > 0]` | C |
| 27 | Wet-area doors | Nos | `N_bath + N_lau` | C |
| 28 | Aluminium curtain wall | m² | `Σ(w × h)` over windows with `w ≥ 2.20`; h = opening height or 2.40 | G |
| 29 | Internal glass doors | Nos | count of doors with `w ≥ 1.40` | G |
| 30 | Pergola (EXCL) | m² | sum of `A_r` for rooms named pergola or gazebo | G |
| 31 | Gates (EXCL) | Sets | `2 × [A_built > 0]` | A |

Items 28 and 29 return 0 with a warning when openings carry no width.

### Group D (32–43)

| # | Material | Unit | Formula | Type |
|---|---|---|---|---|
| 32 | Cable (single core) | LM | `ceil(A_built × 14.5 × 1.10)`; coils = `ceil(LM / 91.4)` | G |
| 33 | Switches and sockets | Nos | `S + SW + DP` | C |
| 34 | Distribution boards | Nos | `N_db = (L + [L ≥ 2]) × [A_built > 0]` | C |
| 35 | Breakers and isolators | Nos | `(ceil(S / 6) + ceil(Lt / 10) + N_ac + N_wh + N_kit) + 3 × N_db + (N_ac + N_wh)` | C |
| 36 | LED spotlights | Nos | sum of `ceil(A_r / 3)` over dry indoor rooms, `ceil(A_r / 2)` over KITCHEN and LAUNDRY rooms, `ceil(A_r / 6)` over semi-open rooms | G |
| 37 | Exhaust fans | Nos | `N_bath + N_kit` | C |
| 38 | Water heaters | Nos | `N_wh` | C |
| 39 | Chandeliers | Nos | `N_liv + N_din + ceil(N_bed / 2)` | A |
| 40 | Bathroom IP65 lights | Nos | sum over BATH rooms of `max(1, ceil(A_b / 2))` | G |
| 41 | LED strip | LM | `(0.75 × ΣP_r over LIVING and BED rooms + 2.5 × N_bath) × 1.05` | A |
| 42 | Aluminium LED channel | LM | same as item 41 | A |
| 43 | Thermostats | Nos | `N_ac` | C |

- `S` (13 A twin sockets), summed per indoor room: BED, LIVING, DINING, STUDY, OTHER → `max(2, ceil(P_r / 4))`; KITCHEN → `max(6, ceil(P_r / 2))`; BATH → 1; LAUNDRY → 2; CIRC → `ceil(P_r / 10)`; STORE → 1.
- `SW` (light switches): `1 + [A_r > 20]` per indoor room.
- `DP` (heater and cooker switches): `N_wh + N_kit`.
- `Lt` = items 36 + 39 + 40. Dry indoor rooms are indoor rooms that are not BATH, KITCHEN or LAUNDRY.
- Item 32 note for purchasing: 35% lighting, 40% sockets, 20% AC and heaters, 5% cooker.

### Group E (44–57)

| # | Material | Unit | Formula | Type |
|---|---|---|---|---|
| 44 | AC condensate drain | LM | `N_ac × 8.5 × 1.05` | C |
| 45 | Angle valves | Nos | `6 × N_bath + 5 × N_kit + N_lau` | C |
| 46 | Isolation valves | Nos | `2 × (N_bath + N_kit) + 4 × [N_bath + N_kit > 0]` | C |
| 47a | Shattaf sets | Nos | `N_bath` | C |
| 47b | Hose bibs | Nos | `2 × [A_built > 0]` | C |
| 48 | Basin and sink mixers | Nos | `N_bath + N_kit` | C |
| 49 | Shower mixer sets | Sets | `N_shower` | C |
| 50 | Toilet accessory sets | Sets | `N_bath` | C |
| 51 | Pump sets | Sets | `2 × [N_bath + N_kit > 0]` | C |
| 52 | Water tanks (EXCL) | Nos | `2 × [N_bath + N_kit > 0]`; ground litres = `500 × ceil(600 × max(1, N_bed) / 500)`, roof litres = `500 × ceil(400 × max(1, N_bed) / 500)` | C |
| 53a | Floor traps | Nos | `N_bath + N_shower + N_kit + N_lau` | C |
| 53b | Roof rainwater outlets | Nos | `max(2, ceil(A_roof / 60)) × [A_roof > 0]` | G |
| 54 | Bottle traps | Nos | `N_bath + N_kit` | C |
| 55 | Water closets | Nos | `N_bath` | C |
| 56 | Basins and sinks (EXCL) | Nos | `N_bath + N_kit` | C |
| 57a | Gully traps | Nos | `ceil((N_bath + N_kit) / 2)` | C |
| 57b | Inspection manholes | Nos | `max(4, ceil(P_ext_0 / 12)) × [N_bath + N_kit > 0]` | G |

### Group F (58–59)

| # | Material | Unit | Formula | Type |
|---|---|---|---|---|
| 58 | Site hoarding | LM | `B × 1.05 × [A_built > 0]`, where `B` is the plot perimeter if supplied, else `max(P_site, P_ext_0 + 24)` | G |
| 59 | Project signboard | No. | `[A_built > 0]` | C |

## 5. Scope, categories and rows

- Items 8–59 are computed at project scope only. Room and level breakdowns keep items 1–7.
- Categories and sub-categories:
  - A Structure and Masonry: Masonry 1; Reinforcement 2; Concrete and binders 3; Aggregates 4, 5; Wall finishes 6; Flooring 7
  - B Civil, Finishing and Waterproofing: Roofing and waterproofing 8–11; Tiling 12–14; Stone and feature 15, 16; Painting 17, 19, 21; Ceilings 18; External render 20; External works 22, 23
  - C Architectural Components: Access and metalwork 24–26; Doors and glazing 27–29; External works 30, 31
  - D Electrical and HVAC: Cabling and containment 32, 42; Wiring devices 33; Distribution and protection 34, 35; Lighting 36, 39, 40, 41; Ventilation and controls 37, 43; Water heating 38
  - E Plumbing and Sanitary: Drainage 44, 53, 54, 57; Valves and fittings 45–47; Sanitary fixtures 48, 49, 50, 55, 56; Pumps and storage 51, 52
  - F Site Setup: Preliminaries 58, 59
- Lettered rows (17a/b, 18a/b, 47a/b, 53a/b, 57a/b) are separate rows in the API, table and exports. Breakdowns of one product (33, 35, 52, coils in 32, pieces in 23, kg and rods in 2) go in `components` and `note`.
- Each row: `serial_no`, `item_code`, `category`, `sub_category`, `name`, `unit`, `quantity`, `components` (label, quantity, unit), `calc_type` (geometry, count, allowance), `quote_status` (INCLUDED or EXCLUDED_FROM_QUOTE), `note`. Items 1–7 also keep their existing keys.
- Apartment rule: if `building_type` is `apartment`, items 8, 10, 20, 21, 22, 23, 26, 30, 31, 53b and 58 return 0 with a note, and a warning says composite items still include roof and plinth terms.

## 6. Determinism rules

1. Apply `unit_scale` before anything else, including bounding boxes.
2. Use `ceil` as defined in section 0 everywhere.
3. Apply waste once, at the end of each formula. Round displayed decimals to 2 places.
4. Iterate levels and rooms in the canonical order the parser's normaliser produces.
5. Never invent a room or opening. If the plan does not show it, return 0 and a warning.
6. Compute project totals from project-level quantities, not by summing per-room results.

Warnings to emit:
- No BATH or KITCHEN detected.
- More than 30% of indoor area typed OTHER.
- Opening widths absent, so items 28 and 29 are 0.
- No paved outdoor rooms, so items 22 and 23 are 0.
- `A_ext` was capped by `A_netwall`.
- `A_gyp_wall` was clamped to 0.
- Doors look under-read: `N_door < N_bath + N_bed`.
- A parking or driveway room sits under an upper floor, so slab quantities exclude it. It sits under an upper floor when the level above has built rooms and their bounding box overlaps the room's bounding box.

## 7. Edge cases (each needs a test)

- Empty level or zero areas: every item returns 0, no errors. The only division by a variable is `s_gyp`, which is guarded.
- Single room, no openings: `A_ext` is capped, `A_int` is 0, plumbing is 0 with a warning.
- Unlabelled rooms ("Room 1"): OTHER; wet items 0 with a warning.
- Arabic or abbreviated labels: rules return OTHER, the model's `boq_type` is used.
- Upper floor smaller than ground: roof uses the largest level; exterior wall is summed per level.
- L-shaped footprint: bounding-box perimeter is exact. U-shapes and courtyards are understated (known limit).
- Double-height rooms: bath tile height stays 2.40 m.
- "Open Kitchen" is a room, not a void. "Open to sky", "open shaft" and a bare "OPEN" label are voids.
- Open-plan "Living / Dining / Kitchen": LIVING with one kitchen counted.
- Old PlanJSON without `boq_type` or opening sizes still calculates.
- Same input twice gives identical output.
- Parking under an upper floor: outdoor and paved, out of the built area, with the warning.
- A semi-open "Wash" yard or "Washroom": indoor, typed LAUNDRY or BATH. A semi-open staircase stays semi-open and untyped.
- Abbreviations are whole words: `KIT.` is KITCHEN, `KITTY ROOM` is not; `DRG./DIN.` is LIVING; `BR 2` is BED, `LIBRARY` is STUDY.
- "DRESS/TOI.": BATH with half its area as the bath portion; "DRESS" alone is STORE.
- A pantry under 4 m² is STORE; "Kitchen / Pantry" of any size is KITCHEN.
- Double-height room on an exterior wall: known limit (section 3), no correction.

## 8. Test fixture

Primitives only. This is not a drawable layout: `A_netwall` and the bounding box are given directly, so test the formula layer with these values and do not derive them from the room list.

Inputs: `L = 1`, `A_built = A_in = A_ground = 160`, `A_netwall = A_netwall_0 = 520`, `H = 3.35`, bounding box of built rooms and of all rooms 10 × 16, 12 windows and 13 doors without widths, 600 × 600 tiles with w = 1.05, `f_fc = 1.0`, `building_type = villa`, no outdoor or semi-open rooms.

| Room | boq_type | Area | Perimeter |
|---|---|---|---|
| Bed 1 | BED | 20 | 18 |
| Bed 2 | BED | 16 | 16 |
| Bed 3 | BED | 16 | 16 |
| Living | LIVING | 36 | 24 |
| Dining | DINING | 16 | 16 |
| Study | STUDY | 10 | 13 |
| Kitchen | KITCHEN | 12 | 14 |
| Bath 1 | BATH | 4.5 | 8.6 |
| Bath 2 | BATH | 4.5 | 8.6 |
| Powder | BATH | 2.0 | 6.0 |
| Laundry | LAUNDRY | 4 | 8 |
| Corridor | CIRC | 14 | 18 |
| Store | STORE | 5 | 9 |

Derived: `ΣP_r = 175.2`, `N_bath = 3`, `N_shower = 2`, `P_bath = 23.2`, `A_wet = 27`, `P_wet = 45.2`, `A_dry = 133`, `N_bed = 3`, `N_liv = 1`, `N_din = 1`, `N_kit = 1`, `N_lau = 1`, `N_ac = 7`, `N_wh = 4`, `P_ext_0 = P_roof = P_site = 52`, `d_roof = 10`, `A_roof = 160`, `G_ext = 174.2`, `A_ext = 156.92`, `A_int = 363.08`, `A_plinth = 130`, `A_parapet = 52`, `A_masonry = 702`, `T_wall = 54.624`, `T_floor = 177.52`, `A_gyp_wall = 828.456`, `A_cem = 315.544`, `E_net = 260.92`, `V_dry = 38.2536`.

| # | Expected | # | Expected | # | Expected |
|---|---|---|---|---|---|
| 1 | 6,143 pieces | 17b | 87 L | 40 | 7 |
| 2 | 9.856 t; 9,856 kg; 925 rods | 18a | 29.70 m²; 11 boards | 41 | 66.15 LM |
| 3 | 331 bags | 18b | 146.30 m²; 51 boards | 42 | 66.15 LM |
| 4 | 28.536592 m³; 46.44 t | 19 | 38 L | 43 | 7 |
| 5 | 21.90888 m³; 32.86 t | 20 | 273.966 m² | 44 | 62.475 LM |
| 6 | 418 bags | 21 | 85 L | 45 | 24 |
| 7 | 186.396 m²; 518 pieces | 22 | 0 | 46 | 12 |
| 8 | 184.38 m² | 23 | 0 | 47a | 3 |
| 9 | 229 L | 24 | 10 | 47b | 2 |
| 10 | 12.60 m³ | 25 | 4 | 48 | 4 |
| 11 | 295 kg | 26 | 1 | 49 | 2 |
| 12 | 60.0864 m² | 27 | 4 | 50 | 3 |
| 13 | 49 kg | 28 | 0 | 51 | 2 |
| 14 | 13 L | 29 | 0 | 52 | 2; 2,000 L and 1,500 L |
| 15 | 22.05 LM | 30 | 0 | 53a | 7 |
| 16 | 2.53 m² | 31 | 2 | 53b | 3 |
| 17a | 194 L | 32 | 2,552 LM; 28 coils | 54 | 4 |
| | | 33 | 61 (42 + 14 + 5) | 55 | 3 |
| | | 34 | 1 | 56 | 4 |
| | | 35 | 40 (26 + 3 + 11) | 57a | 2 |
| | | 36 | 56 | 57b | 5 |
| | | 37 | 4 | 58 | 79.80 LM |
| | | 38 | 4 | 59 | 1 |
| | | 39 | 4 | | |

### 8.1 Rule checks added in 1.2

The fixture above has no parking, combined room or pantry, so its values are the same as in 1.1 (item 2 is now shown in tonnes). These small cases pin the new rules:

| Case | Expected |
|---|---|
| "DRESS/TOI." of 8.0 m², perimeter 12.0 | BATH; `A_b = 4.0`, `P_b = 8.0`; adds 4.0 to `A_bath` and to the dry area; 1 shower; item 40 gives 2 lights |
| "TOI." of 2.6 m², perimeter 6.6 | BATH; `A_b = 2.6`, `P_b = 6.6`; 1 shower |
| "DRESS/TOI." of 4.0 m² | BATH; `A_b = 2.0`; no shower |
| "Pantry" of 3.5 m² | STORE |
| "Pantry" of 4.0 m² | KITCHEN |
| "KIT./DIN." of 30 m² | LIVING; one kitchen counted with `A_k = 10` |
| "PARKING 18X18'6", `room.kind` semi_open | `boq_kind` outdoor; in `A_pave`; not in `A_built` |
| "WASH 5' WD.", `room.kind` semi_open | `boq_kind` indoor; LAUNDRY |
| "STAIRCASE", `room.kind` semi_open | `boq_kind` semi_open; no type |
| Supplied plot perimeter 100 | item 58 = 105.00 LM |
| `A_built = 0` | item 58 = 0 |
