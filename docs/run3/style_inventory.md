# Style handover inventory (villa_look_handover)

Made from `blend/scene_report.json` (interior build) and the scripts' function list. Values are the handover's;
the library ports keep them as defaults (see Stage 1). Everything is procedural: no images, HDRIs, models or add-ons.

## Render and colour management

- engine: CYCLES
- device: CPU
- samples: 72
- adaptive_threshold: 0.019999999552965164
- denoiser: OPENIMAGEDENOISE
- bounces: {'max': 8, 'diffuse': 4, 'glossy': 4, 'transmission': 8, 'transparent': 24}
- clamp_indirect: 6.0
- caustics: [False, False]
- filter: ['BLACKMAN_HARRIS', 1.5]
- view_transform: AgX
- look: AgX - Medium High Contrast
- gamma: 1.0
- display: sRGB
- exposure and white balance: per shot (entrance -0.3 / 5000 K, living, dining, kitchen -0.1 / 4700 K, bedroom and bathroom 0.0 / 4700 K, courtyard +0.3 / 5000 K, roof +0.5 / 6000 K, hero -0.5 / off)
- world: `lantern_more.sunset_sky` (node gradient, strength 1.6, warm western band glow 2.2); hills `lantern_more.ridge`

## Lights (50 in the interior build)

| name | type | W | colour | ≈K | cone | camera visible | glossy visible | made by |
|---|---|---|---|---|---|---|---|---|
| CourtUp0 | SPOT | 900 | (1.0, 0.62, 0.33) | 3808 | 75.0 | False | True | lantern_lib.spot / area |
| CourtUp1 | SPOT | 900 | (1.0, 0.62, 0.33) | 3808 | 75.0 | False | True | lantern_lib.spot / area |
| CourtUp2 | SPOT | 900 | (1.0, 0.62, 0.33) | 3808 | 75.0 | False | True | lantern_lib.spot / area |
| CourtWash0 | SPOT | 380 | (1.0, 0.62, 0.33) | 3808 | 80.0 | False | True | lantern_lib.spot / area |
| CourtWash1 | SPOT | 380 | (1.0, 0.62, 0.33) | 3808 | 80.0 | False | True | lantern_lib.spot / area |
| CourtWash2 | SPOT | 380 | (1.0, 0.62, 0.33) | 3808 | 80.0 | False | True | lantern_lib.spot / area |
| CourtWash3 | SPOT | 380 | (1.0, 0.62, 0.33) | 3808 | 80.0 | False | True | lantern_lib.spot / area |
| CourtWash4 | SPOT | 380 | (1.0, 0.62, 0.33) | 3808 | 80.0 | False | True | lantern_lib.spot / area |
| FireGlow | SPOT | 420 | (1.0, 0.45, 0.16) | 2923 | 175.0 | False | True | lantern_lib.spot / area |
| FireGlowDown | SPOT | 160 | (1.0, 0.45, 0.16) | 2923 | 150.0 | False | True | lantern_lib.spot / area |
| HallLight | AREA | 500 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| LRoomLight0 | AREA | 300 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| LRoomLight1 | AREA | 220 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| LRoomLight2 | AREA | 180 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| LRoomLight3 | AREA | 160 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| RRoomLight0 | AREA | 150 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| RRoomLight1 | AREA | 300 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| RRoomLight2 | AREA | 180 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| RRoomLight3 | AREA | 160 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| Up0 | SPOT | 5200 | (1.0, 0.62, 0.33) | 3808 | 48.0 | False | True | lantern_lib.spot / area |
| Up1 | SPOT | 5200 | (1.0, 0.62, 0.33) | 3808 | 48.0 | False | True | lantern_lib.spot / area |
| Up2 | SPOT | 5200 | (1.0, 0.62, 0.33) | 3808 | 48.0 | False | True | lantern_lib.spot / area |
| Up3 | SPOT | 5200 | (1.0, 0.62, 0.33) | 3808 | 48.0 | False | True | lantern_lib.spot / area |
| Up4 | SPOT | 5200 | (1.0, 0.62, 0.33) | 3808 | 48.0 | False | True | lantern_lib.spot / area |
| Up5 | SPOT | 5200 | (1.0, 0.62, 0.33) | 3808 | 48.0 | False | True | lantern_lib.spot / area |
| Up6 | SPOT | 900 | (1.0, 0.62, 0.33) | 3808 | 70.0 | False | True | lantern_lib.spot / area |
| Up7 | SPOT | 500 | (1.0, 0.62, 0.33) | 3808 | 70.0 | False | True | lantern_lib.spot / area |
| Up8 | SPOT | 900 | (1.0, 0.62, 0.33) | 3808 | 70.0 | False | True | lantern_lib.spot / area |
| Up9 | SPOT | 500 | (1.0, 0.62, 0.33) | 3808 | 70.0 | False | True | lantern_lib.spot / area |
| UpLightL0 | AREA | 150 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| UpLightL1 | AREA | 150 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| UpLightL2 | AREA | 150 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| UpLightR0 | AREA | 150 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| UpLightR1 | AREA | 150 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| UpLightR2 | AREA | 150 | (1.0, 0.8, 0.62) | 4986 |  | False | False | lantern_scene.room_light |
| Wash0 | SPOT | 120 | (1.0, 0.62, 0.33) | 3808 | 58.0 | False | True | lantern_scene.washer |
| Wash1 | SPOT | 120 | (1.0, 0.62, 0.33) | 3808 | 58.0 | False | True | lantern_scene.washer |
| Wash2 | SPOT | 120 | (1.0, 0.62, 0.33) | 3808 | 58.0 | False | True | lantern_scene.washer |
| Wash3 | SPOT | 120 | (1.0, 0.62, 0.33) | 3808 | 58.0 | False | True | lantern_scene.washer |
| WashBath0 | SPOT | 45 | (1.0, 0.62, 0.33) | 3808 | 62.0 | False | True | lantern_scene.washer |
| WashBath1 | SPOT | 45 | (1.0, 0.62, 0.33) | 3808 | 62.0 | False | True | lantern_scene.washer |
| WashBed0 | SPOT | 55 | (1.0, 0.62, 0.33) | 3808 | 62.0 | False | True | lantern_scene.washer |
| WashBed1 | SPOT | 55 | (1.0, 0.62, 0.33) | 3808 | 62.0 | False | True | lantern_scene.washer |
| WashBed2 | SPOT | 55 | (1.0, 0.62, 0.33) | 3808 | 62.0 | False | True | lantern_scene.washer |
| WashE0 | SPOT | 70 | (1.0, 0.62, 0.33) | 3808 | 62.0 | False | True | lantern_scene.washer |
| WashE1 | SPOT | 70 | (1.0, 0.62, 0.33) | 3808 | 62.0 | False | True | lantern_scene.washer |
| WashE2 | SPOT | 70 | (1.0, 0.62, 0.33) | 3808 | 62.0 | False | True | lantern_scene.washer |
| WashW0 | SPOT | 70 | (1.0, 0.62, 0.33) | 3808 | 62.0 | False | True | lantern_scene.washer |
| WashW1 | SPOT | 70 | (1.0, 0.62, 0.33) | 3808 | 62.0 | False | True | lantern_scene.washer |
| WashW2 | SPOT | 70 | (1.0, 0.62, 0.33) | 3808 | 62.0 | False | True | lantern_scene.washer |

## Light-emitting materials

| material | objects |
|---|---|
| StepLight | StepGlow |
| Cove | CoveFront, LCove, RoomCoveL, RoomCoveR |
| Shade | BedLamp0Shade, BedLamp1Shade, BollardLamp0, BollardLamp1, BollardLamp2, BollardLamp3 … |
| Downlight | LRoomLight0Fitting, LRoomLight1Fitting, LRoomLight2Fitting, LRoomLight3Fitting, RRoomLight0Fitting, RRoomLight1Fitting … |
| Bulb | HallLamp, HallLamp.001, HallLamp.002, HallLamp.003, HallLamp.004, HallLamp.005 … |
| CoveSoft | HallCove, NicheStrip |
| GlowWall | CourtGlow |
| Lantern | CourtLantern0Glow, CourtLantern1Glow, CourtLantern2Glow, RoofLantern0Glow, RoofLantern1Glow, RoofLantern2Glow … |
| MirrorRing | MirrorGlow0, MirrorGlow1 |
| SeatStrip | StripN, StripS, StripW |
| Embers | Embers |
| Flame | Flame0, Flame1, Flame2, Flame3, Flame4, Flame5 … |
| RidgeNear | RidgeNear |
| RidgeMid | RidgeMid |
| RidgeFar | RidgeFar |

## Materials (68)

| material | users | base colour (linear) | roughness | metallic | transmission | textures | made by |
|---|---|---|---|---|---|---|---|
| Art | 0 | (0.195, 0.262, 0.254) | 0.8 | 0.0 | 0.0 | Coord; Noise scale=3.0 | lantern_house.mat_simple |
| Art1 | 1 | node:Mix | 0.85 | 0.0 | 0.0 | Coord; Noise scale=0.45; Noise scale=1.8; Coord; Noise scale=260.0 | lantern_scene.mat_art |
| Art2 | 1 | node:Mix | 0.85 | 0.0 | 0.0 | Coord; Noise scale=0.7; Noise scale=2.8; Coord; Noise scale=260.0 | lantern_scene.mat_art |
| Art3 | 1 | node:Mix | 0.85 | 0.0 | 0.0 | Coord; Noise scale=0.6; Noise scale=2.4; Coord; Noise scale=260.0 | lantern_scene.mat_art |
| Art4 | 1 | node:Mix | 0.85 | 0.0 | 0.0 | Coord; Noise scale=0.5; Noise scale=2.0; Coord; Noise scale=260.0 | lantern_scene.mat_art |
| Bark | 32 | (0.069, 0.047, 0.03) | 0.9 | 0.0 | 0.0 | Coord; Noise scale=14.0 | lantern_house.mat_simple |
| BathFloor | 1 | node:Mix | node:Math | 0.0 | 0.0 | Coord; Brick scale=1.0; Noise scale=0.9; Noise scale=1.7; Noise scale= | lantern_scene.mat_paving |
| BookA | 5 | (0.041, 0.054, 0.069) | 0.7 | 0.0 | 0.0 |  | lantern_scene.mat_simple |
| BookB | 5 | (0.485, 0.423, 0.314) | 0.7 | 0.0 | 0.0 |  | lantern_scene.mat_simple |
| BookC | 2 | (0.198, 0.078, 0.042) | 0.7 | 0.0 | 0.0 |  | lantern_scene.mat_simple |
| Brass | 22 | (0.434, 0.266, 0.095) | node:Math | 1.0 | 0.0 | Coord; Noise scale=9.0 | lantern_scene.mat_metal |
| Bronze | 84 | (0.07, 0.042, 0.02) | node:Math | 1.0 | 0.0 | Coord; Noise scale=6.0 | ? |
| Bulb | 16 | None |  |  |  |  | lantern_house.mat_emit |
| Ceiling | 8 | (0.896, 0.847, 0.76) | 0.9 | 0.0 | 0.0 |  | lantern_house.mat_simple |
| CeilingGlow | 0 | None |  |  |  |  | lantern_house.mat_emit |
| Ceramic | 7 | (0.807, 0.753, 0.644) | 0.3 | 0.0 | 0.0 |  | lantern_scene.mat_simple |
| CeramicDark | 3 | (0.044, 0.042, 0.037) | 0.35 | 0.0 | 0.0 |  | lantern_scene.mat_simple |
| Charcoal | 16 | node:Mix | 0.9 | 0.0 | 0.0 | Coord; Noise scale=220.0; Noise scale=3.0 | lantern_scene.mat_fabric |
| Clay | 3 | node:Mix | 0.9 | 0.0 | 0.0 | Coord; Noise scale=220.0; Noise scale=3.0 | lantern_scene.mat_fabric |
| Concrete | 16 | node:Mix | 0.72 | 0.0 | 0.0 | Coord; Noise scale=0.8; Noise scale=1.6; Wave scale=1.3; Noise scale=4 | ? |
| Cove | 4 | None |  |  |  |  | lantern_house.mat_emit |
| CoveSoft | 2 | None |  |  |  |  | lantern_house.mat_emit |
| Curtain | 8 | node:Mix | 0.9 | 0.0 | 0.0 | Coord; Noise scale=1.3 | lantern_house.mat_leaf |
| DarkLeaf | 17 | node:Mix | 0.6 | 0.0 | 0.0 | Coord; Noise scale=1.3 | lantern_house.mat_leaf |
| DarkMetal | 114 | (0.012, 0.01, 0.009) | 0.5 | 1.0 | 0.0 |  | lantern_house.mat_simple |
| DarkStone | 3 | node:Mix | node:Math | 0.0 | 0.0 | Coord; Brick scale=1.0; Noise scale=0.55; Noise scale=2.2; Noise scale | lantern_scene.mat_limestone |
| Deck | 3 | node:Mix | 0.55 | 0.0 | 0.0 | Coord; Brick scale=1.0; Noise scale=3.0 | lantern_scene.pxy |
| Downlight | 25 | None |  |  |  |  | lantern_scene.mat_emit |
| Embers | 1 | None |  |  |  | Coord; Voronoi scale=22.0; Noise scale=6.0 | lantern_scene.disc |
| Flame | 9 | None |  |  |  | Coord; Noise scale=3.0 | ? |
| FloorOak | 2 | node:Mix | 0.4 | 0.0 | 0.0 | Coord; Brick scale=1.0; Noise scale=3.0 | lantern_scene.mat_plank |
| Glass | 12 | (1.0, 1.0, 1.0) | 0.0 | 1.0 | 0.0 |  | ? |
| GlowWall | 1 | None |  |  |  |  | lantern_scene.mat_emit |
| Grass | 6 | node:Mix | 0.6 | 0.0 | 0.0 | Coord; Noise scale=1.3 | lantern_house.mat_leaf |
| Gravel | 7 | node:Mix | 0.85 | 0.0 | 0.0 | Coord; Voronoi scale=55.0; Noise scale=40.0 | ? |
| Lantern | 7 | None |  |  |  |  | lantern_scene.mat_emit |
| Leather | 8 | (0.254, 0.102, 0.037) | 0.42 | 0.0 | 0.0 | Coord; Noise scale=120.0 | lantern_house.mat_simple |
| Lemon | 5 | (0.687, 0.462, 0.042) | 0.45 | 0.0 | 0.0 |  | lantern_scene.mat_simple |
| Limestone | 18 | node:Mix | node:Math | 0.0 | 0.0 | Coord; Brick scale=1.0; Noise scale=0.55; Noise scale=2.2; Noise scale | ? |
| Linen | 39 | node:Mix | 0.9 | 0.0 | 0.0 | Coord; Noise scale=220.0; Noise scale=3.0 | lantern_house.mat_fabric |
| LinenWhite | 5 | node:Mix | 0.9 | 0.0 | 0.0 | Coord; Noise scale=220.0; Noise scale=3.0 | lantern_scene.mat_fabric |
| Mirror | 2 | (0.888, 0.905, 0.905) | node:Math | 1.0 | 0.0 | Coord; Noise scale=9.0 | lantern_scene.mat_metal |
| MirrorRing | 2 | None |  |  |  |  | lantern_scene.mat_emit |
| Niche | 0 | None |  |  |  |  | lantern_house.mat_emit |
| Oak | 21 | node:ValToRGB | 0.5 | 0.0 | 0.0 | Coord; Noise scale=3.0 | lantern_house.mat_wood |
| OliveLeaf | 10 | node:Mix | 0.5 | 0.0 | 0.0 | Coord; Noise scale=1.3 | lantern_house.mat_leaf |
| OvenGlass | 2 | (0.007, 0.009, 0.01) | node:Math | 1.0 | 0.0 | Coord; Noise scale=9.0 | lantern_scene.mat_metal |
| PalmLeaf | 6 | node:Mix | 0.42 | 0.0 | 0.0 | Coord; Noise scale=1.3 | lantern_house.mat_leaf |
| PalmStem | 6 | (0.258, 0.254, 0.069) | 0.6 | 0.0 | 0.0 |  | lantern_house.mat_simple |
| Paving | 6 | node:Mix | node:Math | 0.0 | 0.0 | Coord; Brick scale=1.0; Noise scale=0.9; Noise scale=1.7; Noise scale= | ? |
| Plaster | 7 | (0.863, 0.783, 0.651) | 0.85 | 0.0 | 0.0 | Coord; Noise scale=30.0 | lantern_house.mat_simple |
| RibbedGlass | 1 | (0.9, 0.95, 0.93) | 0.08 | 0.0 | 1.0 | Coord | ? |
| RidgeFar | 1 | None |  |  |  |  | lantern_scene.mat_flat |
| RidgeMid | 1 | None |  |  |  |  | lantern_scene.mat_flat |
| RidgeNear | 1 | None |  |  |  |  | lantern_scene.mat_flat |
| Rug | 2 | node:Mix | 0.9 | 0.0 | 0.0 | Coord; Noise scale=90.0; Noise scale=3.0 | lantern_house.mat_fabric |
| Sage | 4 | node:Mix | 0.9 | 0.0 | 0.0 | Coord; Noise scale=220.0; Noise scale=3.0 | lantern_scene.mat_fabric |
| Screen | 2 | node:ValToRGB | 0.6 | 0.0 | 0.0 | Coord; Noise scale=0.7; Noise scale=50.0 | lantern_house.box |
| ScreenY | 1 | node:ValToRGB | 0.6 | 0.0 | 0.0 | Coord; Noise scale=0.7; Noise scale=50.0 | lantern_scene.mat_screen |
| SeatStrip | 3 | None |  |  |  |  | lantern_scene.mat_emit |
| Shade | 9 | None |  |  |  |  | lantern_house.mat_emit |
| Soffit | 1 | node:ValToRGB | 0.5 | 0.0 | 0.0 | Coord; Noise scale=3.0 | lantern_house.mat_wood |
| StepLight | 1 | None |  |  |  |  | lantern_house.mat_emit |
| Terrain | 1 | (0.011, 0.012, 0.009) | 0.95 | 0.0 | 0.0 | Coord; Noise scale=0.02 | lantern_scene.mat_simple |
| Towel | 6 | node:Mix | 0.9 | 0.0 | 0.0 | Coord; Noise scale=60.0; Noise scale=3.0 | lantern_scene.mat_fabric |
| TubStone | 3 | (0.815, 0.76, 0.658) | 0.38 | 0.0 | 0.0 | Coord; Noise scale=18.0 | lantern_scene.mat_simple |
| Walnut | 39 | node:ValToRGB | 0.42 | 0.0 | 0.0 | Coord; Noise scale=3.0 | ? |
| Water | 2 | (0.001, 0.003, 0.004) | 0.015 | 0.0 | 0.0 | Coord; Noise scale=2.6; Noise scale=15.6 | lantern_house.pxy |

## Procedural generators and helpers

| function | what it makes |
|---|---|
| lantern_lib.srgb | '#rrggbb' -> linear RGB tuple (Blender shader colours are linear). |
| lantern_lib.rgba |  |
| lantern_lib.reset |  |
| lantern_lib.link |  |
| lantern_lib.sock |  |
| lantern_lib.setv |  |
| lantern_lib.new_mat |  |
| lantern_lib.mat_simple |  |
| lantern_lib.mat_limestone | Honed sand-coloured stone cladding with fine joints. wall=True maps joints on vertical faces. |
| lantern_lib.mat_concrete | Board-marked concrete: faint horizontal board lines and soft staining. |
| lantern_lib.mat_bronze |  |
| lantern_lib.mat_glass | Architectural glass: clear straight through, mirror reflection weighted by Fresnel. |
| lantern_lib.mat_paving | Large honed stone slabs on the ground, reflective enough to carry light. |
| lantern_lib.mat_water | Still dark water over dark stone: a mirror with very small ripples. |
| lantern_lib.mat_screen | Perforated stone screen (jaali): diamond openings with small square ones between them. |
| lantern_lib.mat_emit |  |
| lantern_lib.mat_fabric |  |
| lantern_lib.mat_wood |  |
| lantern_lib.mat_leaf |  |
| lantern_lib.mat_gravel |  |
| lantern_lib.mesh_obj |  |
| lantern_lib.box |  |
| lantern_lib.plane_xz | Vertical pane facing -Y. |
| lantern_lib.plane_yz |  |
| lantern_lib.plane_xy |  |
| lantern_lib.sphere |  |
| lantern_lib.curtain | A hanging linen curtain: a wavy sheet facing -Y. |
| lantern_lib._unit |  |
| lantern_lib.palm | Date palm: slightly leaning trunk and a crown of arching fronds with stiff leaflets. |
| lantern_lib.tree | A branching tree with a cloud of small leaves (used for olive trees and background trees). |
| lantern_lib.grasses | Clumps of ornamental grass inside the rectangle region = (x0, x1, y0, y1). |
| lantern_lib.spot |  |
| lantern_lib.area |  |
| lantern_lib.dusk_sky | Clear evening sky: deep blue overhead, paler toward the horizon, dark below it. |
| lantern_lib.setup_render |  |
| lantern_lib.camera |  |
| lantern_lib.render |  |
| lantern_house.materials |  |
| lantern_house.shell |  |
| lantern_house.interiors |  |
| lantern_house.terrace |  |
| lantern_house.garden |  |
| lantern_house.build |  |
| lantern_house.main |  |
| lantern_more.lathe | Surface of revolution around the vertical axis. profile = [(radius, height), ...] bottom to top. |
| lantern_more.rod | A straight round bar between two points. |
| lantern_more.disc |  |
| lantern_more._cloud_tex |  |
| lantern_more.soft_box | An upholstered block: rounded edges, optionally with gentle fabric wrinkles. |
| lantern_more.pillow | A plump cushion: a flattened ball with a soft seam. |
| lantern_more.tub | A freestanding stone bathtub: an oval bowl with a thick rim. |
| lantern_more.ridge | A distant mountain ridge: a wall whose top edge follows fractal noise. |
| lantern_more.mat_screen | Perforated stone screen. axis = the horizontal direction the screen runs along. |
| lantern_more.mat_art | An abstract painting: soft layered colour fields on canvas. |
| lantern_more.mat_metal |  |
| lantern_more.mat_ribbed_glass | Fluted glass for the shower: lets light through, blurs what is behind it. |
| lantern_more.mat_embers | A bed of glowing coals for the fire bowl. |
| lantern_more.mat_flame | A small flame: bright at the base, fading and breaking up toward the tip. |
| lantern_more.mat_flat | A flat, self-lit colour: used for distant mountain silhouettes seen through haze. |
| lantern_more.mat_plank | Timber boards on a floor: long planks with thin gaps. |
| lantern_more.sunset_sky | The clear evening sky of the hero picture, plus a thin band of last light on the western horizon. |
| lantern_more.camera_at | A camera at loc looking toward the point `look`. level=True keeps it horizontal so verticals stay straight. |
| lantern_scene.more_materials |  |
| lantern_scene.room_light | A soft ceiling light. It lights the room but is not itself seen, directly or in reflections; |
| lantern_scene.washer | A recessed downlight that grazes a wall. |
| lantern_scene.table_lamp |  |
| lantern_scene.vase_branches |  |
| lantern_scene.books |  |
| lantern_scene.potted_tree |  |
| lantern_scene.chair | A dining chair. back_north: the backrest is on the north side of the seat. |
| lantern_scene.lounge_chair | A low lounge chair, 0.8 deep and 0.78 wide, with a timber side frame. |
| lantern_scene.lantern |  |
| lantern_scene.upstairs_shell |  |
| lantern_scene.living |  |
| lantern_scene.dining_kitchen |  |
| lantern_scene.hall_court |  |
| lantern_scene.bedroom | Main bedroom, upstairs left. The bed stands against the far stone wall; the screens are on the left. |
| lantern_scene.bathroom |  |
| lantern_scene.roof_terrace |  |
| lantern_scene.landscape | The land to the west: dark ground, scattered trees, three low ridges fading into haze. |
| lantern_scene.build | outside=True is the view from across the water: the roof terrace furniture is left out so the |
| lantern_scene.position_pass | Turn the scene into a 'what 3D point is here' picture: every surface shines with its own |
| lantern_scene.main |  |

## Post-processing (`scripts/post.py`, after Cycles)

bloom (luma > 0.72, blurs 0.6 % and 3 % of width mixed 0.6/0.4, screen 0.2; roof 0.3); S-curve 0.06; vignette -10 % from 35 % radius (hero -6 %); grain sigma 0.006 seeded; unsharp 0.25 / 1 px; downscale only (INTER_AREA).

## Tour (`scripts/tour_build.py`)

8 finished stills + a world-position pass each; per-room dolly 0.4-1.7 m with forward splatting and far-side hole filling; 60-frame segments with cross-dissolves; 421 frames at 30 fps.

Counts: {'objects': {'MESH': 660, 'LIGHT': 50}, 'polygons': 583814}
