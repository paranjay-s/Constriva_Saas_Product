<USER_REQUEST>
# AGENTS.md — Floor-plan 3D viewer (vanilla Three.js, "dollhouse" style)

## 0. Goal

Our viewer takes a 3D JSON (derived from a 2D architectural floor-plan PDF) and renders it in Three.js.
Today it looks like a flat diagram: grey floor slabs, thin black wall outlines, box furniture, floating text labels.

Rebuild the renderer so the same JSON produces a polished **isometric dollhouse cutaway**:
white walls with a dark charcoal top edge, warm wood floors, large glazed openings, soft rounded furniture,
plants, soft shadows, bright warm daylight, pale background.

Reference look = "Image 1" (target). Current look = "Image 2" (what we are replacing). Keep both images
in `docs/reference/target.png` and `docs/reference/current.png` and compare against them at every milestone.

**Be honest about the ceiling.** The reference is a path-traced render. Vanilla Three.js with procedural
textures, soft shadows, tone mapping and fake ambient occlusion can reach roughly 80–90% of that look.
Do not try to fake global illumination or photoreal furniture. Aim for "clean architectural model", not "photo".

## 1. Hard constraints

- Only the `three` npm package. Allowed imports: `three` and `three/addons/*` (they ship inside the same package):
  `OrbitControls`, `RoomEnvironment`, `RoundedBoxGeometry`, `BufferGeometryUtils`; optional Tier-2 only:
  `EffectComposer`, `RenderPass`, `GTAOPass`, `OutputPass`.
- No Blender, no GLTF/FBX/OBJ, no HDR/EXR files, no image textures, no CDN fetches. Everything is generated in code.
- No `react-three-fiber`, `drei`, `three-stdlib`, `troika`, or any other 3D/helper library.
- The viewer core is **framework-free TypeScript** (`createViewer(container, opts)`); React only wraps it.
- Do not change the backend or the JSON producer. Adapt on the client (see §3).
- Do not hardcode room coordinates or sizes. Everything derives from the plan data.
- Use a recent `three` (r160+). `THREE.NeutralToneMapping` needs r162+; fall back to ACES if older.

## 2. Visual target — what must be visible

Study the target image and treat this as the checklist:

1. **Camera**: perspective, narrow FOV (~28–32°), looking down at ~45–55° elevation, rotated ~35–45° around the building. Reads as isometric but with a hint of depth.
2. **No roof or ceiling.** Walls are full-height solids you look into from above.
3. **Walls**: white/off-white faces; **exterior walls have a thick dark charcoal top cap** (this dark outline is the single strongest signature of the look); interior walls have thinner, white/light-grey caps.
4. **Glazing**: big floor-to-ceiling windows and sliding doors on exterior walls, thin dark frames, pale blue translucent glass.
5. **Floors**: warm light-oak planks in living, dining, kitchen, bedrooms; pale tile in bathrooms; light marble in puja; concrete in parking. Plank direction is consistent across rooms (continuous grain).
6. **Furniture**: soft, rounded, mostly white/cream upholstery with wood tables; dark stools; white-linen beds; a rug in the living area. Chunky and simple, not detailed.
7. **Greenery**: round green shrubs and potted plants near windows and corners (the target also has palms outside; those are optional staging).
8. **Light**: bright, warm, soft. Sun from upper-left-front, soft shadows falling right/back, no harsh black. Shadowed white walls stay light grey, never muddy.
9. **Ground**: the house sits on a thin pale plinth over an off-white ground; faint soft shadow around the base.
10. **No labels baked into the scene.** Room labels exist only as an optional HTML overlay (§13), off by default.

## 3. Input data contract

We do not own the exact JSON shape here, so the first task is:

1. Find where the current Three.js scene is built in the repo and write down the existing JSON shape in `docs/plan-json.md`.
2. Write `adapter/normalizePlan.ts` that converts the existing JSON into this internal `Plan` type. All new code consumes only `Plan`.

```ts
// types.ts — units are METERS, Y-up in Three.js, plan (x, y) -> world (x, z)
export type RoomType =
  | 'bedroom' | 'living' | 'drawing' | 'dining' | 'kitchen' | 'toilet' | 'wash'
  | 'puja' | 'parking' | 'balcony' | 'terrace' | 'store' | 'utility'
  | 'passage' | 'stairs' | 'other';

export interface Vec2 { x: number; y: number }

export interface Wall {
  id: string;
  a: Vec2; b: Vec2;            // centerline endpoints
  thickness: number;           // m; default 0.23 exterior, 0.115 interior
  height: number;              // m; default 2.9
  kind: 'exterior' | 'interior';
}

export interface Opening {
  id: string;
  wallId: string;
  kind: 'door' | 'window' | 'slider' | 'arch';
  offset: number;              // m from wall start to opening CENTER
  width: number;               // m
  height: number;              // m
  sill: number;                // m above floor (door: 0, window: ~0.9, slider: 0)
}

export interface Room {
  id: string;
  type: RoomType;
  label?: string;              // raw label, e.g. "BEDROOM 10'2\"X12'"
  polygon: Vec2[];             // closed ring, no repeated last point
  dims?: { w: number; d: number };  // m, from the label if present
}

export interface FurnitureItem {  // optional: only if the JSON already has it
  type: string; position: Vec2; rotation: number; size: { w: number; d: number; h: number };
}

export interface Plan {
  walls: Wall[]; openings: Opening[]; rooms: Room[];
  furniture?: FurnitureItem[];
  meta: { sourceUnit: 'ft' | 'm' | 'mm' };
}
```

Adapter rules:

- Convert every unit to meters once, here (`1 ft = 0.3048 m`, `1 in = 0.0254 m`). Parse labels like `10'2"X12'` with a tested `parseFtIn()`.
- Detect Y-flip: PDF coordinates often have Y pointing down. The plan must not appear mirrored; verify with the label overlay (text must read correctly).
- Re-center the plan so its bounding box center is at the origin.
- Normalize room types with a case-insensitive map: `BEDROOM|BED|MBR→bedroom`, `LIV|LIVING→living`, `DRG|DRAWING→drawing`, `DIN|DINING→dining`, `KIT|KITCHEN→kitchen`, `TOI|TOILET|WC|BATH→toilet`, `WASH|WASH AREA→wash`, `PUJA|MANDIR→puja`, `PARKING|GARAGE→parking`, `BALCONY|TERRACE|DECK→balcony`, `STORE→store`, `STAIR→stairs`; anything else → `other`.
- If walls come without `kind`, mark a wall exterior when one side has no room on it; otherwise interior.
- If the JSON has no openings, do not invent them silently; log a warning and render solid walls. (Doors and windows must come from the data.)
- Keep a `fixtures/plan-sample.json` exported from the exact plan in Image 2 and use it for every milestone below.

## 4. Folder structure

```
frontend/src/viewer3d/
  index.ts                 // createViewer(container, opts) => ViewerApi
  PlanViewer.tsx           // thin React wrapper (ref + effect + dispose)
  types.ts
  adapter/normalizePlan.ts
  core/renderer.ts  core/camera.ts  core/lights.ts  core/environment.ts  core/loop.ts
  materials/palette.ts  materials/textures.ts  materials/materials.ts
  build/plinth.ts  build/floors.ts  build/walls.ts  build/openings.ts  build/ao.ts
  furniture/builders/*.ts  furniture/layout.ts  furniture/stage.ts  furniture/plants.ts
  ui/labels.ts  ui/cutaway.ts
  utils/geometry.ts  utils/rng.ts  utils/dispose.ts  utils/units.ts
  __tests__/               // vitest: parseFtIn, polygon area, OBB, wall hole validation
```

`ViewerApi`:

```ts
interface ViewerApi {
  loadPlan(plan: Plan): void;
  setView(v: 'iso' | 'top'): void;
  setFurniture(on: boolean): void;
  setLabels(on: boolean): void;
  setWallMode(m: 'auto' | 'full' | 'low'): void;
  screenshot(): string;         // PNG data URL
  dispose(): void;
}
```

## 5. Design tokens (single source: `materials/palette.ts`)

Never write a hex value outside this file.

| Token | Hex | Use |
|---|---|---|
| `bgTop` / `bgBottom` | `#FAF8F4` / `#E9E5DD` | CSS radial gradient behind a transparent canvas |
| `ground` | `#EFEBE4` | ground disc, receives soft shadow |
| `plinth` | `#E6E1D8` | slab under the house, 0.2 m thick |
| `wallFace` | `#FAF9F6` | all wall faces |
| `wallCapExterior` | `#35363A` | exterior wall top cap (dark outline) |
| `wallCapInterior` | `#F2F0EB` | interior wall top cap |
| `glass` | `#BFE6F0` | opacity 0.25–0.3 |
| `frame` | `#2A2C30` | window/door frames, mullions |
| `woodLiving` | `#D9B58A` | base for plank texture (variation `#C99E6D`–`#E4C9A0`) |
| `woodBedroom` | `#DDBE94` | slightly lighter |
| `woodDeck` | `#C9A173` | balcony/terrace planks (`#B98A5E`–`#D2A877`) |
| `tileBath` | `#E6E8EA` | grout `#D0D3D6`, 0.6 m tiles |
| `marblePuja` | `#F1ECE2` | |
| `concrete` | `#CFCFCB` | parking |
| `fabricLight` | `#F2EEE7` | sofas, armchairs; cushions `#E3DDD1` |
| `linen` | `#F7F6F2` | bedding |
| `woodFurniture` | `#B98B5C` | tables, TV unit, headboards, nightstands |
| `accentTeal` | `#2F5D62` | one accent: a headboard, a cushion, or a rug stripe per room, never more |
| `stoolDark` | `#2B2B2D` | bar stools, TV |
| `stone` | `#F5F3EF` | kitchen counters, vanity tops |
| `foliageA/B/C` | `#5F8F4E` / `#4A7A3C` / `#7FA85A` | plants |
| `pot` | `#E9E4DA` | planters |
| `car` | `#D8DBDF` | body; glass `#2A3036`, tyres `#1B1B1C` |

Rules: colors are `THREE.Color` in sRGB; use `MeshStandardMaterial` for everything (roughness 0.7–0.95, metalness 0) except glass (`MeshPhysicalMaterial`, `transparent`, `opacity 0.28`, `roughness 0.05`, `depthWrite false`). Share one material instance per token.

## 6. Renderer, camera, lights, environment

```ts
// core/renderer.ts
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: false });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.NeutralToneMapping;   // keeps whites white; ACESFilmic greys them out
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;  // VSMShadowMap if you need softer edges
```

- Transparent canvas; the container gets `background: radial-gradient(ellipse at 50% 40%, bgTop, bgBottom)`.
- `ResizeObserver` on the container, not `window.resize`.

**Camera** (`core/camera.ts`):

- `PerspectiveCamera(fov 30)`. Fit to the building's bounding sphere: `distance = radius / sin(fov/2) * 1.05`.
- Default iso view: azimuth 40°, elevation 50°. Top view: elevation 89°, azimuth 0.
- `OrbitControls`: `enableDamping`, `dampingFactor 0.08`, `maxPolarAngle = 1.35` (never go below the floor), `minDistance = radius * 0.8`, `maxDistance = radius * 4`, pan on, target = building center.
- Smoothly animate between views (400 ms ease-out), no jump cuts.

**Lights** (`core/lights.ts`), tune by eye. Targets: lit white wall ≥ `#FAFAF8` without clipping, shadowed white wall ≥ `#D8D8D6`.

- `HemisphereLight(0xffffff, 0xe9e2d6, ~1.0)`.
- Key sun `DirectionalLight(0xfff4e0, ~2.5–3.5)` placed at direction `(-0.6, 1.0, 0.5)` from the building center. `castShadow = true`, `shadow.mapSize 4096`, orthographic shadow camera sized to the bounding sphere * 1.2, `bias -0.0004`, `normalBias 0.03`.
- Fill `DirectionalLight(0xdfe8ff, ~0.5)` from the opposite side, no shadows.
- Environment: `scene.environment = pmrem.fromScene(new RoomEnvironment()).texture; scene.environmentIntensity = 0.4` (soft reflections on glass, floors and tabletops).
- Every mesh sets `castShadow` / `receiveShadow` explicitly. Floors and ground receive only. Glass casts nothing.

**Render loop** (`core/loop.ts`): render on demand. Re-render on controls `change`, resize, toggle, or while an animation is active. Never run a permanent 60 fps loop on an idle model.

## 7. Procedural textures (`materials/textures.ts`)

Canvas-generated, seeded RNG (`mulberry32`) so the output is deterministic.

- `makeWoodTexture({ base, plankW = 0.16, tile = 2.4, seed })`: 2048² canvas. Rows of planks running along canvas-X, each row lightness-jittered ±5%, random butt joints per row, 1–2 px dark seam (alpha 0.2) between planks, ~30 faint grain streaks per plank (alpha 0.05). Output `SRGBColorSpace`.
- `makeTileTexture({ base, grout, tile = 0.6 })`: 1024², 4×4 tiles, 3 px grout.
- `makeConcreteTexture`: flat color + low-amplitude noise.
- `makeBlobTexture()`: 128² radial gradient `rgba(0,0,0,0.35) → 0`, for contact shadows (§11).
- All: `wrapS = wrapT = RepeatWrapping`, `anisotropy = renderer.capabilities.getMaxAnisotropy()`, `generateMipmaps = true`.
- World-space tiling: floor geometry UVs are in meters, so `texture.repeat.set(1 / tile, 1 / tile)`. Use **one shared texture per floor type** so planks line up across adjacent rooms. Deck planks run along the deck's long axis.

## 8. Geometry

Plan point `(x, y)` → world `(x, 0, y)`. Y is up.

### 8.1 Plinth and ground (`build/plinth.ts`)
- Plinth: extruded footprint outline (union of room polygons' bounding hull, offset by 0.15 m), 0.2 m thick, top at `y = 0`, color `plinth`, receives and casts shadow.
- Ground: large disc (radius = 3× building radius) at `y = -0.2`, color `ground`, receives shadow. Add a soft blob shadow under the plinth.
- Do not invent a deck or landscaping. Only render a deck where the plan has a `balcony`/`terrace` room.

### 8.2 Floors (`build/floors.ts`)
- Per room: `Shape` from polygon with `y = -plan.y`, then `geometry.rotateX(-Math.PI / 2)` so plan-y ends up on world +z and the normal points up. Verify visibly from above.
- Lift floors `+0.001 m` over the plinth, and give each floor type its own material. Rooms of the same type share one material instance.
- Assign floor by room type: living/drawing/dining/kitchen/passage → `woodLiving`; bedroom → `woodBedroom`; toilet/wash → tile; puja → marble; parking → concrete; balcony/terrace → deck.

### 8.3 Walls (`build/walls.ts`) — each wall is an extruded rectangle with holes

```ts
function buildWall(w: Wall, openings: Opening[], ext: number): THREE.Group {
  const len = distance(w.a, w.b) + ext * 2;           // ext = thickness/2 -> fills corner gaps
  const H = w.height, t = w.thickness;
  const shape = new THREE.Shape()
    .moveTo(0, 0).lineTo(len, 0).lineTo(len, H).lineTo(0, H).closePath();

  for (const o of openings) {
    const x0 = ext + o.offset - o.width / 2, x1 = x0 + o.width;
    const y0 = Math.max(o.sill, 0.01);                 // holes must not touch the outline
    const y1 = Math.min(o.sill + o.height, H - 0.02);
    const hole = new THREE.Path()
      .moveTo(x0, y0).lineTo(x1, y0).lineTo(x1, y1).lineTo(x0, y1).closePath();
    shape.holes.push(hole);
  }
  const geo = new THREE.ExtrudeGeometry(shape, { depth: t, bevelEnabled: false });
  geo.translate(0, 0, -t / 2);                         // center on the wall line

  const body = new THREE.Mesh(geo, mats.wallFace);
  const group = new THREE.Group();
  group.add(body);
  group.position.set(w.a.x - dir.x * ext, 0, w.a.y - dir.y * ext);
  group.rotation.y = -Math.atan2(w.b.y - w.a.y, w.b.x - w.a.x);   // local +X -> wall direction
  return group;
}
```

- Validate openings before building: clamp inside `[0.05, len - 0.05]`, drop overlaps, and warn. Overlapping or boundary-touching holes break triangulation.
- **Cap**: a separate `BoxGeometry(len, capH, t + capExtra)` sitting on top of the wall. Exterior: `capH 0.08`, `capExtra 0.06`, color `wallCapExterior`. Interior: `capH 0.03`, `capExtra 0.02`, color `wallCapInterior`.
- Anti z-fighting at junctions: offset each cap's Y by `index * 0.0005`, and give exterior caps `polygonOffset`.
- Corner and T-junction gaps are covered by the `ext` extension; check every corner in the sample plan visually, from above.
- Group walls by material and merge with `BufferGeometryUtils.mergeGeometries` after the build, except exterior walls that take part in the cutaway (§9).

### 8.4 Openings (`build/openings.ts`)
- **Window / slider**: glass pane (thin box, `glass` material) filling the hole, `frame` color 0.05 m outer frame, plus mullions: one every ~1.0 m for sliders, none for small windows. Windows get a 0.03 m interior sill ledge.
- **Door**: leave the hole open; add a thin `woodFurniture` leaf rotated ~70° open at the hinge side, so doors read as doors. Frame: 0.04 m `frame`-color lining on both sides.
- **Arch**: hole only.

## 9. Dollhouse cutaway (`ui/cutaway.ts`)

Needed so walls nearest the camera do not hide the interior.

- Exterior walls each get an outward normal (away from the building centroid) and live in their own group.
- On camera change: `facing = dot(normal.xz, normalize(camera.pos.xz - center.xz))`. If `facing > 0.25` the wall's target `scale.y = 1.0 / H` (low, ≈ 1.0 m); else target `1`. Lerp the group's `scale.y` toward the target. Wall groups pivot at `y = 0`, so scaling down keeps their base on the floor.
- Wall modes: `auto` (cutaway, default), `full` (as in the target image), `low` (every wall 1.0 m).
- Interior walls stay full height in every mode.

## 10. Furniture (`furniture/`)

The PDF contains no furniture, so this is **staging**. It must be clearly optional and clearly illustrative:

- Toggle "Furniture" in the UI, default on; tooltip/caption "Illustrative furniture — not part of the drawing".
- If `plan.furniture` exists, render those items with the builders below and skip auto-staging.

**Builders** (`furniture/builders/*.ts`): each returns a `THREE.Group` with origin at floor-center of its footprint, front facing +Z, plus `{ w, d }` footprint. All dimensions in meters. Use `RoundedBoxGeometry` (radius 0.02–0.08) for anything soft: sofas, cushions, mattresses, beds, stools. This single choice is most of the "elegant" look.

| Item | Size (w × d × h) | Notes |
|---|---|---|
| `bed` (double) | 1.6 × 2.05 × 0.45 | base 0.3 `woodFurniture`, mattress 0.22 `linen`, headboard 0.08 thick × 1.0 high, 2 pillows 0.6 × 0.4 × 0.12, folded runner at foot (`accentTeal`) |
| `nightstand` | 0.45 × 0.4 × 0.5 | one each side of the bed |
| `wardrobe` | 1.8 × 0.6 × 2.1 | `fabricLight` doors, 2 thin vertical seams |
| `sofa3` | 2.1 × 0.9 × 0.85 | seat height 0.42, 3 seat cushions, 3 back cushions |
| `sofaL` | 2.6 × 1.6 × 0.85 | only in rooms larger than ~16 m² |
| `armchair` | 0.85 × 0.85 × 0.8 | |
| `coffeeTable` | 1.0 × 0.6 × 0.4 | wood top, round variant optional |
| `tvUnit` | 1.6 × 0.4 × 0.45 | plus TV 1.3 × 0.05 × 0.75 at height 0.9, `stoolDark` |
| `diningTable` | 1.6 × 0.9 × 0.75 | 4–6 chairs 0.45 × 0.45 × 0.85 around it, chairs pushed in 0.1 m |
| `kitchenRun` | length × 0.6 × 0.9 | `stone` top, `woodFurniture` fronts, hob (4 dark discs) and sink (inset dark box) |
| `island` | 1.8 × 0.8 × 0.92 | 3 stools Ø0.35 × 0.65, `stoolDark` (only if kitchen ≥ 10 m² and a clear 1 m aisle remains) |
| `wc` | 0.4 × 0.65 × 0.4 | tank + bowl from rounded boxes |
| `vanity` | 0.7 × 0.45 × 0.85 | basin + mirror plane on the wall |
| `shower` | 0.9 × 0.9 | tray + glass screen (`glass` material) on two sides |
| `pujaUnit` | 0.9 × 0.45 × 1.6 | wood, small shelf, a thin warm `#C9A24B` accent |
| `rug` | 2.4 × 1.7 × 0.015 | light grey `#D9D6CF`, optional single `accentTeal` stripe |
| `plant` | Ø0.5 × 1.0 | `pot` cylinder + 3–5 overlapping `IcosahedronGeometry` leaf blobs in `foliageA/B/C`, flat-shaded off |
| `car` | 4.2 × 1.8 × 1.4 | two rounded boxes (body + cabin) + 4 tyres, parking only, optional |

**Auto-layout** (`furniture/layout.ts`, `stage.ts`), deterministic per room (seed = room id):

1. Compute the room's minimum-area oriented bounding box (try every edge angle). Work in that local frame, then rotate back.
2. For each OBB side, compute the **free length**: side length minus door/window spans (look up via `Opening` ↔ `Wall` ↔ nearest side).
3. Recipes (skip any item that doesn't fit with 0.6 m clearance):
   - **bedroom**: bed head on the longest free side, centered; nightstands either side; wardrobe on another free side; skip wardrobe if the room is < 9 m².
   - **living/drawing**: `sofa3` against the longest free side facing the room; `tvUnit` on the opposite free side; `rug` centered between; `coffeeTable` on the rug; `plant` in a corner by a window.
   - **dining**: table centered in OBB with chairs; rug optional.
   - **kitchen**: `kitchenRun` along the longest free side (L-shape if two adjacent free sides ≥ 2 m); `island` if it fits.
   - **toilet**: `wc` against the shortest side, `vanity` on a different side, `shower` in the far corner if the room ≥ 3.5 m².
   - **puja**: `pujaUnit` on the longest free side.
   - **parking**: one `car`, centered, only when the room ≥ 2.4 × 4.8 m.
   - Others: leave empty.
4. Keep-outs: a quarter-circle of radius = door width at each door's swing, and a 0.6 m strip in front of any door. Windows only block items taller than the sill height.
5. Never place anything that intersects a wall or another item (AABB test after rotation). If a recipe step fails, skip it, do not squeeze.
6. Cap total triangles for the furniture layer to ~150k; use `InstancedMesh` for repeats (chairs, cushions, shrub blobs).

## 11. Soft shadows and fake AO (`build/ao.ts`) — the "expensive" look for cheap

1. **Contact blobs**: under each furniture group, a plane of footprint × 1.25 at `y = 0.004` with `makeBlobTexture()`, `transparent`, `depthWrite: false`, `opacity 0.5`.
2. **Wall-base AO**: along both sides of every wall, a thin plane 0.3 m wide at `y = 0.003`, linear gradient `rgba(0,0,0,0.20) → 0`, merged into one mesh.
3. **Plinth skirt shadow**: a larger blob under the whole building on the ground.
4. Tier 2, only after everything else works and only if FPS stays ≥ 45 on a mid laptop: `GTAOPass` via `EffectComposer` + `OutputPass`. Gate it behind a quality setting. Do not enable it by default on mobile.

## 12. Performance and cleanup

- Idle cost ~0: render on demand (§6).
- Merge static geometry by material. Share materials and textures. Aim for < 400 draw calls on the sample plan.
- Create vectors and matrices outside loops; no allocations in the camera-change handler.
- `dispose()` must: cancel any RAF, disconnect `ResizeObserver`, remove event listeners, dispose `OrbitControls`, every geometry/material/texture, the `PMREMGenerator`, the renderer (`renderer.dispose()`, `forceContextLoss()`), and remove the canvas. React StrictMode mounts twice; the wrapper must survive that with no leaks.
- If WebGL is unavailable, show a plain message and do not throw.

## 13. UI (React wrapper, Tailwind)

Small floating toolbar, bottom-left of the canvas: view (Isometric / Top), Furniture on/off, Labels on/off, Walls (Auto / Full / Low), Screenshot, Reset view.

- Labels: HTML overlay positioned by projecting each room's centroid to screen each frame while visible. White pill, soft shadow, room name plus dimensions in ft-in (`11'4" × 11'`). Off by default. Use them to verify the plan is not mirrored and to catch room-type misclassification.
- Keyboard focus visible on every control; respect `prefers-reduced-motion` (skip the camera tween).

## 14. Build order — finish and verify each milestone before the next

| # | Deliver | Accept when |
|---|---|---|
| M1 | Adapter + floors + plain walls + camera fit + orbit | Sample plan renders un-mirrored, correct proportions, rooms line up, labels read correctly |
| M2 | Wall caps, plinth, openings, glass, frames | Corners are gap-free; windows/doors sit where the plan shows them; dark exterior outline visible |
| M3 | Lighting, shadows, tone mapping, wood/tile textures | Screenshot side-by-side with the target: wall brightness, floor warmth and shadow softness are in the same family |
| M4 | Furniture builders + auto-staging | Every room type has believable furniture; nothing intersects walls or door swings |
| M5 | Fake AO, cutaway, labels, toolbar | Interior always visible in auto mode; no flicker or z-fighting while orbiting |
| M6 | Dispose, perf, tests, StrictMode | No leaks after 20 mount/unmount cycles; idle GPU ≈ 0; unit tests green |

After each milestone: commit, save `docs/progress/Mx.png` (use `viewer.screenshot()`), and list what still differs from the target image. Do not start polishing a milestone's details before the next milestone exists.

## 15. Definition of done

- Visual: side-by-side with the target, a non-technical viewer would say "same style".
- Data-driven: swapping in a different plan JSON works with zero code changes.
- Honest: furniture is labelled illustrative; missing openings are warned, not invented.
- Hygiene: `tsc --noEmit` clean, no new dependencies beyond `three` (and `vitest` as a dev dependency), tests pass.

## 16. Do not

- Do not add any 3D or helper library, any model file, any image texture file, or any network fetch.
- Do not bake labels, dimensions or text into 3D geometry.
- Do not add per-frame allocations, a permanent render loop, or global mutable singletons.
- Do not hardcode room coordinates, wall heights, or colors outside `palette.ts`.
- Do not change the backend or the PDF → JSON pipeline. only change three js 3d model not any other thing  target image how model should look like 
</USER_REQUEST>
<ADDITIONAL_METADATA>
The current local time is: 2026-11-11T21:52:16+05:30.

The user's current state is as follows:
Active Document: c:\Constriva-saas\Constriva_Saas_Product\frontend\src\features\chat\AiGeneratorPage.tsx (LANGUAGE_UNSPECIFIED)
Cursor is on line: 1
Other open documents:
- c:\Constriva-saas\Constriva_Saas_Product\.env (LANGUAGE_UNSPECIFIED)
- c:\Constriva-saas\Constriva_Saas_Product\backend\constriva.db (LANGUAGE_UNSPECIFIED)
- c:\Constriva-saas\Constriva_Saas_Product\backend\app\modules\sheets\router.py (LANGUAGE_UNSPECIFIED)
- c:\Constriva-saas\Constriva_Saas_Product\backend\app\modules\sheets\export.py (LANGUAGE_UNSPECIFIED)
- c:\Constriva-saas\Constriva_Saas_Product\frontend\src\features\plan-viewer\materials\materials.ts (LANGUAGE_UNSPECIFIED)

The user has uploaded 1 image(s):
- C:/Users/Shantanu/.gemini/antigravity/brain/b28099d3-0ca0-46ea-bfc7-be3019a8b8a3/.user_uploaded/media_1794414123893_b1c182e1.jpg
You can embed this image in an artifact if you need the USER to review it.
</ADDITIONAL_METADATA>