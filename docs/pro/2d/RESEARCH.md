# 2D generator research

Written 2026-11-20 before any change to the generator. Every value below that drives a rule is
repeated in [RULES.md](RULES.md), marked "to be confirmed against the Dubai Building Code by an
engineer". Nothing here is legal advice.

## 1. Drafting standards

### Line weights and types (ISO 128)

ISO 128 sets line *types* (continuous, dashed, chain) and a line-width series in the ratio
1 : √2: 0.13, 0.18, 0.25, 0.35, 0.5, 0.7, 1.0 mm. Construction drawings use two or three widths
from the series on one sheet. ISO 128-23 (lines on construction drawings) is withdrawn and folded
into ISO 128-2:2020, so we cite the series and the type meanings, not a part number.
[ISO 128 (Wikipedia)](https://en.wikipedia.org/wiki/ISO_128),
[CAD standards (Wikipedia)](https://en.wikipedia.org/wiki/CAD_standards).

What we use (at 1:100 on A3, see RULES.md for the table):

| Element | Width | Type |
|---|---|---|
| Cut exterior walls (outline) | 0.70 mm, dark solid fill | continuous |
| Cut interior walls (outline) | 0.50 mm, grey fill | continuous |
| Door leaves, window frames, stair outlines | 0.25 mm | continuous |
| Door swing arcs, glazing lines, fixtures, furniture | 0.18 mm | continuous (arcs thin) |
| Hatches (lawn, water, paving), grid, dimension lines | 0.13 mm | continuous |
| Overhead / above cut plane (stair above, slab edge) | 0.25 mm | dashed |
| Setback lines, centre lines | 0.18 mm | chain |
| Plot boundary | 0.50 mm | chain (long dash, dot) |

### Layers (ISO 13567 vs US National CAD Standard)

ISO 13567-1:2017 builds a layer name from fixed-length fields: agent responsible, element
(a classification code), presentation (E element, T text, H hatch, D dimension...), optional status.
[ISO 13567 (Wikipedia)](https://en.wikipedia.org/wiki/ISO_13567).
The US National CAD Standard (AIA layer guidelines) uses `Discipline-Major-Minor-Status`, for example
`A-WALL`, `A-WALL-PATT`, `A-DOOR`, `A-GLAZ`, `A-FLOR-FIXT`, `A-FURN`, `A-ANNO-DIMS`, `A-ANNO-TEXT`,
`L-SITE`, `C-PROP`.

**Choice: the US NCS / AIA names.** They are what UAE consultants and Revit/ArchiCAD/AutoCAD
templates use day to day, are readable without a code table, and ezdxf, FreeCAD and the ODA tools
handle them. ISO 13567 needs a national classification table (Uniclass/SfB) to fill its element
field. The layer table is in RULES.md and in the drafting-standards skill.

### Plan symbols

Standard conventions used in the references and in the AIA graphic standards:
hinged door = leaf drawn open at 90° plus a quarter-circle swing arc; sliding door = two offset
leaf rectangles with a direction arrow; window = frame lines on both wall faces plus one or two
thin glazing lines in between, sill line on the outside; stair = treads, a walking line with an
arrow pointing UP from the floor drawn, "UP"/"DN" text, and a diagonal cut line where the cut plane
crosses the flight (steps above the cut dashed). WC, basin, shower tray, bath, kitchen counter,
sink, hob and fridge are drawn as blocks at true size.

## 2. Dubai and UAE villa planning

Source: Dubai Building Code 2021 edition, Part K (Villas). The official u.ae link returns 404 today;
we read the copy at [archive.org](https://archive.org/details/dubai-building-code-2021) (the
Part K body in that copy is the Arabic text; the tables were read from the page images).
Page references are the code's own (K-nn).

| Topic | DBC Part K value | Section |
|---|---|---|
| Setbacks, standalone villa | 3 m road side, 3 m neighbour side, 3 m lane/rear (Table K.1) | K.5.2.4 |
| Setbacks, townhouse | 3 m road, 0 m neighbour, 3 m lane | K.5.2.4 |
| Annex distance | ≥ 1.5 m from the main villa | K.5.2.3 |
| Annex area | ≤ 60% of the main villa's gross area, height ≤ 5.5 m | K.5.2.3 |
| Building height | ≤ 16 m | K.5.2.2 |
| Gross area (GA) | measured to the inside of the external walls, includes corridors, stairs, internal walls; excludes openings and shafts | K.5.2.6 |
| Plot coverage | horizontal area of all buildings incl. annexes, measured to the outer face of external walls, includes covered balconies/terraces; excludes pergolas, car shades, decorative projections | K.5.2.7 |
| Coverage limit | none given for private villas in DBC; DM FAQ: no maximum BUA, setbacks govern | K.5.2.7, [DM FAQ](https://www.dm.gov.ae/wp-content/uploads/2023/09/FAQ-for-Buildings-Permit-Procedures-and-Regulations-eng-1.pdf) |
| Living space (bedroom, living, majlis...) | ≥ 10.5 m², least dimension ≥ 3.0 m (Table K.2) | K.5.3.1 |
| Maid's / driver's / guard room (single, no bath) | ≥ 5.5 m², least dimension ≥ 2.1 m | K.5.3.1 |
| Enclosed kitchen | ≥ 5.4 m², least dimension ≥ 1.8 m; ≥ 1.2 m clear between counters | K.5.3.1 |
| Clear height | living and bedrooms 2.7 m; other spaces 2.3 m; stair 2.3 m; under-stair service rooms 2.03 m (Table K.3) | K.5.3.2 |
| Door clear width | entrance and general doors 915 mm; bathrooms and WCs 710 mm (Table K.4) | K.5.4.1 |
| Windows | bedrooms, living rooms and kitchens: glazing ≥ 10% of floor area; maid's room ≥ 8%; room depth ≤ 3 × window wall width for daylight; ≥ 150 lux by daylight | K.5.4.2 |
| Corridors | clear width ≥ 1.0 m, clear height ≥ 2.3 m | K.5.5.1 |
| Stairs | clear width ≥ 1.0 m; riser 100–180 mm, uniform within 10 mm per flight; going (tread) ≥ 280 mm; landings ≥ stair width and ≥ 1.0 m; headroom ≥ 2.3 m; handrail 865–965 mm; intermediate landing recommended above 4 m rise | K.5.5.2 |
| Spiral / curved stairs | width ≥ 1.0 m, riser ≤ 240 mm (spiral), headroom 2.03 m | K.5.5.2.8 |
| Parking | ≥ 1 space per villa; open single 3.0 × 5.5 m; enclosed single 3.6 × 6.0 m; enclosed double 6.0 × 6.0 m; slope ≤ 4% (Tables K.6, K.7) | K.5.6.4 |
| Sanitary | every villa has a WC, basin and bath or shower; ventilation of WCs and bathrooms (natural or mechanical, K.10.1.6) | K.5.7.1 |
| Fixture clearances | WC and basin centre ≥ 400 mm from a side wall or obstruction, ≥ 750 mm between centres; 750 mm clear in front of a WC or basin; 600 mm between facing fixtures | K.5.7.2 |
| Pools | windows opening onto the pool area: sill ≥ 1.2 m; shallow water 0.85–1.2 m deep | K.5.8.2 |

The user's requested setback defaults (3 m front, 1.5 m sides and rear) are **lower** than the DBC
standalone-villa table (3 m on all sides). 1.5 m all round is allowed only for Emirati owners under
the Home First relaxations ([Gulf News](https://gulfnews.com/uae/dubai-eases-villa-construction-rules-for-emiratis-allows-second-family-homes-1.500713942)).
We keep the user's defaults as settings, and the checker reports a warning when a side setback is
below 3 m. This is in "What you must decide" in SUMMARY.md.

### Typical villa programme (UAE)

From the references (antonovich sheets) and common UAE practice: entrance foyer; **majlis** (formal
guest sitting, near the entrance, often with its own guest WC and sometimes a separate entrance);
family living; formal dining; **show kitchen** (clean, open to dining or living) and **service
("dirty") kitchen** behind it with a store and service entrance; **maid's room** with its own bath
near the service kitchen; **driver's room** near parking, often outside the main house; laundry;
guest bedroom on the ground floor; master suite with dressing and bath; children's bedrooms each
with a bath; prayer room; lift in larger villas; covered parking for 2–4 cars; pool with deck,
garden, outdoor majlis or BBQ area. The service zone (service kitchen, maid, laundry, driver) has its
own access away from the guest route.

### Presentation in the UAE

Practice seen in the references and in DM submission sets: A3 or A1 sheets; drawing at 1:100
(1:50 for parts); right-hand or bottom title block with consultant logo, client, project and plot
number, drawing title and number, scale, date, drawn/checked, revision table; north arrow; graphic
scale; room names in capitals with size and area; dimension chains on all sides; monochrome line
work with light hatches only for landscape, water and paving. Fonts in the references: Century Gothic
(proprietary) and Times New Roman. We use **Jost** (SIL Open Font License 1.1, a geometric sans
close to Century Gothic) for all text.

## 3. Open-source floor plan generation

Cloned into `tools/vendor-eval/` (git-ignored) for reading only. **None can be shipped.**

| Project | Licence | Shippable | Idea we use |
|---|---|---|---|
| [HouseDiffusion](https://github.com/aminshabani/house_diffusion) (CVPR 2023) | "not allowed for commercial usage"; research use under GPL-3 | No | Discrete + continuous denoising: coordinates snapped to a discrete grid so walls align exactly. We already solve on an integer grid (now 50 mm multiples). |
| [House-GAN++](https://github.com/ennauata/houseganpp) | "can only be used for research purposes" | No | Iterative refinement conditioned on the previous layout: our edit engine locks unchanged rooms and re-solves only what moved; full re-solve when that fails. |
| [Graph2Plan](https://github.com/HanHan55/Graph2plan) | no licence file (all rights reserved); trained on RPLAN (non-commercial) | No | User layout graph (adjacency + doors) as the input, retrieve a similar boundary then refine. Our rule language is that graph; our templates are the retrieval step. |
| RPLAN dataset | non-commercial | No (benchmark ideas only) | Room-type vocabulary and adjacency statistics. |
| [Generative floor plan design with LLMs via RL with verifiable rewards](https://arxiv.org/pdf/2605.14117) (2026) | paper | n/a | The validator as a verifiable reward. We use the same idea without training: the LLM writes rules, the CP-SAT solver satisfies them, the validator verifies. |
| [Unified vector floorplan generation via markup](https://arxiv.org/pdf/2604.04859), [GSDiff](https://arxiv.org/html/2408.16258v2) | papers | n/a | Wall-graph (not room-box) output; confirms that a structured intermediate model beats image generation for CAD output. |

Conclusion: learned generators give plausible pictures but no guarantees on areas, setbacks, door
widths or adjacency, and none is licensed for commercial use. A constraint solver (OR-Tools CP-SAT,
Apache-2.0, already our solver) driven by a rule language the LLM fills is the right base. The
changes we make: hard constraints for "touches several rooms", "door between", relative sides,
zones, size/aspect bounds and daylight; outdoor areas as solver objects; a time-boxed full re-solve;
and conflict naming by dropping one rule at a time.

## 4. Open-source CAD and BIM tools

| Tool | Licence | Use |
|---|---|---|
| [ezdxf](https://ezdxf.mozman.de/) 1.4.5 | MIT | DXF writer (already used); `ezdxf.audit` for validation; `ezdxf.addons.odafc` drives the ODA converter. |
| [IfcOpenShell](https://ifcopenshell.org/) 0.9.0 | LGPL-3.0 | IFC4 writer (walls, doors, windows, spaces, slabs, storeys) and validator (`ifcopenshell.validate`). Used as a library (dynamic linking from Python is fine under LGPL). |
| [FreeCAD](https://www.freecad.org/) 1.1.4 | LGPL-2.0+ | Headless checker only (`FreeCADCmd` opens the DXF and IFC we write). Installed with Homebrew cask. Not shipped in the API image. |
| [GNU LibreDWG](https://www.gnu.org/software/libredwg/) 0.14 | GPL-3.0+ | `dxf2dwg` writes DWG (R2000 only, "work in progress" per its manual), `dwgread`/`dwg2dxf` read DWG back. Run only as a separate process, never linked. |
| [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter) (guest build for macOS arm64, downloaded 2026-11-20) | proprietary freeware; no licence text in the download | Best DWG fidelity (all versions, audit flag). Server use inside a commercial SaaS is not clearly allowed by any text we could find: owner decision. |

DWG choice is made by measurement in task 8 (see SUMMARY.md and DEPENDENCIES.md).
