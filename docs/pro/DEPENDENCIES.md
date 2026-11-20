# New dependencies, tools and cloned repositories

Every addition made during the pro run, with its licence and how it is used. "Shipped" means it
runs in our API or worker image or its output reaches users.

## Python packages (backend)

| Package | Version | Licence | Shipped | Use |
|---|---|---|---|---|
| ifcopenshell | 0.9.0.post1 | LGPL-3.0 | yes (library, dynamically linked from Python) | IFC4 export and validation (`render/cad_ifc.py`) |
| fonttools (via `uvx`, not a project dependency) | current | MIT | no | made the static Jost instances and web subsets once |
| matplotlib (via `uv run --with`, not a project dependency) | current | PSF-based | no | rendered a DXF to PNG to check it by eye |

## System tools

| Tool | Version | Licence | Shipped | Use |
|---|---|---|---|---|
| GNU LibreDWG (`brew install libredwg`) | 0.14 | GPL-3.0+ | as a separate process only | DXF to DWG (`dxf2dwg`), DWG read-back check |
| FreeCAD (`brew install --cask freecad`) | 1.1.4 | LGPL-2.0+ | no (test-time checker) | headless open of our DXF and IFC files |
| ODA File Converter (guest download, macOS arm64, copied to /Applications) | current guest build | proprietary freeware; the download ships no licence text; the ODA site calls it "freely available" | only where installed and configured (`FLOORPLAN_DWG_CONVERTER`); owner to confirm server use | DXF -> DWG (AutoCAD 2018) and DWG read-back |

## Cloned repositories (tools/vendor-eval/, git-ignored, read only)

| Repository | Licence | Shipped | Why cloned |
|---|---|---|---|
| aminshabani/house_diffusion | non-commercial; research use under GPL-3 | no | read for ideas (grid-snapped coordinates) |
| ennauata/houseganpp | research purposes only | no | read for ideas (iterative refinement) |
| HanHan55/Graph2plan | no licence file (all rights reserved) | no | read for ideas (graph-conditioned layout) |

## Data and fonts

| Item | Licence | Shipped | Use |
|---|---|---|---|
| Jost font (static Regular 400 and SemiBold 600 cut from the Google Fonts variable font, plus Latin subsets for SVG) | SIL Open Font License 1.1 (`drawing/fonts/OFL.txt`) | yes, embedded in PDFs and SVGs | the one font of the drawing |

## DWG converter: measured choice (2026-11-20)

| Converter | Writes our R2018 DXF as DWG | Read back | Notes |
|---|---|---|---|
| ODA File Converter | yes, AutoCAD 2018 DWG, about 37 KB for the nandu plan, 1 s | same entity counts by type and same layers, read back by ODA itself and, independently, by LibreDWG `dwg2dxf` | runs headless from the command line on macOS; on Linux set `QT_QPA_PLATFORM=offscreen` (the code does) |
| GNU LibreDWG `dxf2dwg` 0.14 | no: "Invalid DXF code 50 for MTEXT", "Failed to decode DXF file" | n/a | writes R2000 only and is marked work in progress; kept as an independent DWG reader for checks |

Chosen: the ODA File Converter, used only when installed. If the owner does not clear its
licence for server use, DWG is switched off (the endpoint answers 503 with a message) and DXF
remains, which every CAD program opens.
