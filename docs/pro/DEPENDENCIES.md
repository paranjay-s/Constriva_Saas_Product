# New dependencies, tools and cloned repositories

Every addition made during the pro run, with its licence and how it is used. "Shipped" means it
runs in our API or worker image or its output reaches users.

## Python packages (backend)

| Package | Version | Licence | Shipped | Use |
|---|---|---|---|---|

## System tools

| Tool | Version | Licence | Shipped | Use |
|---|---|---|---|---|
| GNU LibreDWG (`brew install libredwg`) | 0.14 | GPL-3.0+ | as a separate process only | DXF to DWG (`dxf2dwg`), DWG read-back check |
| FreeCAD (`brew install --cask freecad`) | 1.1.4 | LGPL-2.0+ | no (test-time checker) | headless open of our DXF and IFC files |
| ODA File Converter (guest download, macOS arm64) | current guest build | proprietary freeware, no licence text shipped | no until the owner decides | DWG fidelity comparison |

## Cloned repositories (tools/vendor-eval/, git-ignored, read only)

| Repository | Licence | Shipped | Why cloned |
|---|---|---|---|
| aminshabani/house_diffusion | non-commercial; research use under GPL-3 | no | read for ideas (grid-snapped coordinates) |
| ennauata/houseganpp | research purposes only | no | read for ideas (iterative refinement) |
| HanHan55/Graph2plan | no licence file (all rights reserved) | no | read for ideas (graph-conditioned layout) |

## Data and fonts

| Item | Licence | Shipped | Use |
|---|---|---|---|
