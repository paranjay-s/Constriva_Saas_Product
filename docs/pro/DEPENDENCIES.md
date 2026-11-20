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

## PART 2: reading scans (B)

| Item | Version | Licence | Shipped | Use |
|---|---|---|---|---|
| rapidocr (RapidAI/RapidOCR) with its bundled PP-OCR ONNX models | 3.x | Apache-2.0 (code and models) | yes, backend dependency | OCR of room names, size labels and floor titles in scans (`plan3d/scan_reader.py`) |
| onnxruntime | 1.x | MIT | yes, backend dependency | runs the OCR models |
| opencv-python-headless | already a dependency | Apache-2.0 | yes | wall masks, deskew |

Cloned into `tools/vendor-eval/` (git-ignored) to read code and licences; nothing from them is shipped:

| Repository | Licence | Use by us |
|---|---|---|
| CubiCasa/CubiCasa5k | CC BY-NC 4.0 (dataset and model) | none in the product; private benchmark at most |
| zlzeng/DeepFloorplan | GPL-3.0 | none (would only ever run as a separate process) |
| art-programmer/FloorplanTransformation | MIT code; data and weights under other terms | ideas only (junction graph, integer-programming clean-up) |
| RapidAI/RapidOCR | Apache-2.0 | the shipped OCR (installed from PyPI) |
| mindee/doctr | Apache-2.0 | evaluated as the alternative OCR; not installed |

## PART 2: High quality (E) and PART 3

| Item | Version | Licence | Shipped | Use |
|---|---|---|---|---|
| Style handover ("Lantern house", docs/reference/style) | 2026-11 | the owner's team; ported with permission given in the brief | ported code in `services/planto3d/blender/look.py` | sky, materials, render settings and finishing of High stills |
| Blender (Cycles, EEVEE, glTF and USD exporters) | 5.3 | GPL-2.0+ | separate process only (already used) | stills, tours, engine export |
| Unreal Engine | 5.8 (already installed) | Epic EULA: no royalty on rendered stills/video; seat subscription above USD 1 M revenue outside games | no (optional renderer, `PLAN3D_RENDERER=unreal`) | prototype in `tools/unreal/HouseProto` |
| Pixel Streaming 2 (Unreal plugin) | with UE 5.8 | Epic EULA | no (disabled) | documented in deploy-3d.md |
| Twinmotion | n/a | free under USD 1 M revenue, paid seat above | no (research only) | REALTIME_ENGINES.md |
| ffmpeg (libx264) | system | LGPL/GPL build | separate process (already used) | tours and the fast tour |
| Chrome for Testing | 158 | BSD-style (Chromium) | no (local screenshots of the walkthrough for F only, in the scratchpad) | Low pictures in the comparison sheets |
| cwebp (libwebp, Homebrew) | system | BSD-3-Clause | no (local re-encoding of one landing image) | PART 3 image compression |
| ODA File Converter (optional in the backend image) | 27.x | proprietary freeware | only if the owner allows (`ODA_DEB_URL`) | DWG export (from PART 1) |
