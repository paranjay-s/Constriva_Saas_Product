# feat/pro_2 summary

Branch feat/pro_2, made from feat/pro (ab053ee). Every task is committed on its own; nothing pushed; main
untouched. Hardware for every timing: Apple M1 Pro (10 CPU cores, 16-core GPU, 32 GB), macOS, on AC power.
Task-by-task status and commits: [LOG.md](LOG.md).

**Budgets used**: live AI calls **47 of 100** (18 claude-opus-5-5: 14 for the three briefs, 4 for scans not yet
cached; 29 claude-fable-5-2 for the model comparison, 3 of them automatic repairs). Rendering **about 43 of 180
minutes** across Blender and Unreal (longest single render 112 s; 2-minute cooldowns, `nice -n 10`, AC power
checked before every render; Unreal 2.5 minutes of its 15-minute cap). Disk never below 240 GB free; no sudo,
no sign-ins, no .env edits.

## Section A: 2D generator

### A1. A plan every time

**Why the two briefs were refused** ([2d/FAILURES.md](2d/FAILURES.md)). Both ran 9 solver attempts and 3 AI
resizes with every wish as a hard rule, then gave up (44.5 s and 81.7 s). Brief 1 had contradictory and
mis-bound rules (the front lawn and the backyard garden became one garden asked to be front and rear; the
common washroom was bound to the master's attached bath), five rules impossible even alone with a living room
that had to be the door parent of seven rooms, and its stated 5,000 sq ft built-up was cut to what the default
3 / 1.5 / 1.5 m setbacks allowed. Brief 2 asked for more area than the plot holds (open areas sized from the
whole plot on top of 464 m² of rooms) inside the setbacks.

**What changed**
- The person's numbers win: a built-up area stated beside the plot ("built-up area of 5000 ft²", "build up
  area of atleast 3000 sq feet") is read and used as is; the 65-75 % band applies only when none is given;
  unusual coverage gets a note, never a refusal.
- Setbacks default to 0 (settings and .env.example); "3 m setback at the front" works in the brief and as a
  chat edit (`set_setbacks`, re-plans).
- Wishes as weighted soft constraints in CP-SAT (stated sizes 40, touching / doors 20, sides 12, zones 8,
  aspect and daylight 2 points; 5,000 objective units a point).
- Relaxation ladder (`pipeline/relax.py`), each rung logged: weighted wishes, then a. aspect and daylight
  dropped, b. low-weight adjacencies and sides dropped, c. rooms shrunk to 85 % / 70 %, d. other plot
  proportions (1:1, 3:4, 2:3, 1:2 and turned, only when the shape was assumed), e. below the standard
  minimums (each room named), f. a deterministic corridor layout by zone that always succeeds
  (`layout/fallback.py`), with doors from the corridor and anything still wrong listed.
- A first pass that finds no layout no longer spends AI calls on resizes; a feasibility shortfall no longer
  refuses; the plan's first chat message lists what was adjusted in plain words ("The living could not go at
  the rear; it is at the front instead.") and offers to bring any of it back by asking.
- Brief understanding: speech-to-text fixes before the AI reads the brief (four year / for year / "and four
  and" = foyer, walking wardrobe = walk-in, washroom = bathroom, pooja = puja, drawing room = living room...),
  shown on the brief card as "I read your words as"; unclear numbers ("Master bedroom 18") become an
  assumption on the card; a rule naming a room type with several rooms goes to the room its words name
  (FRONT LAWN vs BACKYARD GARDEN, COMMON BATH vs the attached bath).

**Results (measured)** ([2d/RELAXATION.md](2d/RELAXATION.md))
- Brief 1: plan in the first pass with all 13 wishes kept (51 s with live AI sizing). Brief 2: plan in the
  first pass (17 s). Before the reading and binding fixes the ladder alone already delivered both (rung a in
  12 s, weighted rung in 6 s).
- 50 random briefs (1-12 rooms, 1,000-15,000 sq ft, with and without stated built-up, 0-4 random wishes):
  **50 of 50 got a plan**, all validated; first pass 42, weighted 5, rung b 1, corridor fallback 2 (both 5
  bedrooms with baths on about 1,100-1,200 sq ft; delivered as drafts with the remaining problems listed).
  Median 6.0 s, longest 14.1 s.
- The brief that worked: identical program, plot, door tree and solver calls to feat/pro (golden test, under
  feat/pro's setbacks). Note for the owner: the solver is time-limited and multi-threaded, so even feat/pro
  returns a different valid plan on each run (3 runs, 3 different files); byte-identical plans were never
  possible. With the new default of no setbacks this brief lays out a larger area, so its plan changes;
  that follows from your setback decision.

### A2. Presentation view

`drawing/presentation.py` draws the same building model in muted colour: warm grey and beige floors by room
type, dull green garden / lawn / verandah, dull blue water, soft stone paving, solid minimal furniture (beds,
WC and basin, sofa set, dining table and chairs, counters, a puja unit, plants that fit, loungers where the
paving allows), same Jost text, labels, dimension chains, title block, north arrow, scale bar and the "For
design purposes only, not for construction" label, plus a colour legend. The plan panel has an
Engineering (default) / Presentation toggle; PDF, PNG and SVG downloads follow it (file names end in
`-presentation`; the PDF carries the signed building model); DXF, DWG and IFC stay engineering.

The engineering drawing is unchanged: PDF, SVG and PNG of the five sample plans are byte for byte the feat/pro
files once the PDF's dates and file ID are blanked, and each DXF draws exactly the same entities, layers and
styles as feat/pro's (`test_fp_engineering_snapshot.py`, 20 files, every run; 200 repeated PDF exports all
matched). DXF is compared entity by entity rather than byte by byte because ezdxf numbers its objects in an
order that depends on which of its modules a process loaded first: the same feat/pro code writes different
handles in different test orders. The golden values were computed with feat/pro's own code.

Samples side by side: [2d/presentation/](2d/presentation/) (`*_side_by_side.png`, plus each PDF and PNG).

## Section B: material finder (image analysis)

**Cause of the loop**: each "which toilet?" choice mapped back to the room's name, and with three rooms
named TOILET the name matched all three again, so the same question came back for every pick except "All of
them".

**Fix**: choices carry the room's position in the plan; buttons read "Toilet 1 · 8.1 × 3.8 ft" ... plus "All
of them"; typed answers are matched by number, ordinal ("the second one", "last"), size ("8.5 x 5.4", "46 sq
ft", "the biggest"), distinctive name words, several at once ("toilet 1 and 3") or "all of them"; naming a kind
("Toilet") narrows the choice; an answer that still cannot be matched gets the buttons again with what was not
understood; the same question is never asked twice in a row; rooms that share a name keep their number in the
report. Tests cover each answer form and the exact sequence that looped (material suite: 69 passed).

## Section C: 3D

### C1. Rooms looked smaller ([3d/SPACE.md](3d/SPACE.md))

The plan used: the fresh internet plan is `~/Downloads/1000207168.pdf` (PlanTo3D job `dfd12ccd8e35`; the brief's
`docs/reference/plans/<file name>` does not exist, so this is the newest plan you built), plus OPT 5.

**Measured**: walls never eat into rooms (0-0.6 % of a room's rectangle; rooms are read to the inside wall faces).
On the fresh plan the rooms really are smaller: only 2 of 13 labelled rooms are within 5 % of their label (a
bedroom 11'6" wide is built 8.2 ft wide), because that scan was read by the AI reader, whose walls are rough. OPT 5
(vector) has 18 of 30 within 5 %. Besides that the house read low and dark: 3.05 m ceilings, 2.13 m doors and
window heads, a walkthrough camera of 70 degrees vertical (102 across on 16:9, 86 on 4:3), 16 mm in small-room
stills, bedrooms 40-53 % covered with furniture and 0.67 m at the bed's foot.

**Changed** (settings in `.env.example`, PATCHES 59): ceilings 3.4 m, doors and window heads 2.4 m, the walkthrough
at 90 degrees across on every window shape with a "Wide view" toggle (65 normal), 18-24 mm level stills from the
corner along the longest diagonal (corner chosen from where the camera actually stands), beds scaled to the room
with 0.9 m at the foot, optional pieces dropped in small rooms (furniture at most 38 % of the floor under 120 sq
ft), full-length mirrors in dressing rooms (bathrooms had vanity mirrors), walls and wood 45 % lighter, indoor
lamps 1.4x. Every plan dimension is kept. Not done: living rooms and majlis taller than the rest of their storey
(a storey has one height); the tray ceilings of C3.2 make their middle read higher.

**Before / after** for a bedroom, the dining room and a toilet, Low and High: [3d/space_compare/](3d/space_compare/).
Low build 160 s before / 178 s after; stills 90-113 s each (M1 Pro, Metal, 96 samples, 1920 x 1080).

### C2. Reading accuracy ([3d/ACCURACY.md](3d/ACCURACY.md))

- **Fresh plan's wrong walls and doors (C2.1)**: it is a 72 dpi scan with hollow walls (two thin lines). The scan
  reader traces no walls on it, so the AI reader read it, and its walls are rough (outer walls on the dimension
  lines, rooms 22-52 % short of their labels). A hollow-wall mask for low-resolution scans was tried twice and
  reverted (no closed rooms: the lines are too faint and broken, beds and stair treads close into blocks).
  **Partial.**
- **Scans: scan walls + AI room names and types (C2.2)**, now the gateway's behaviour (`PLAN3D_SCAN_AI_NAMES`):
  scanned room types 11-52 % -> **32-61 %** (AI reader alone: 76-92 %, because the scan reader cuts rooms
  differently).
- **Model comparison (C2.3)** on the 26 held-out scans: claude-fable-5-2 reads walls 95 % / 89 % (recall /
  precision, all 50 plans), doors 90 %, windows 93 %, room types 85 %; claude-opus-5-5 69 % / 63 %, 65 %, 67 %,
  87 %. Cost per scanned plan **$0.84 vs $0.22**; Fable takes minutes per plan. Default unchanged (Opus 5.5).
- **Drawing-only round trip (C2.4)** of 20 generated plans read by the vector detector: walls **99.9 %** / 100 %,
  doors **85.2 %** / 96.9 %, windows **96.4 %** / 99.8 % (feat/pro: 95.9 %, 82.6 %, 91.5 %). **The 98 % target is not
  met** for doors or windows. On the way: with no setbacks (A1.3) the dash-dot plot boundary line lay on the outer
  wall faces and the detector lost the outer walls (walls 16.7 %); the reader now ignores dash-dot property and
  centre lines (PATCHES 61). The doors still missed sit at the end of a wall run beside a cross wall (lobby
  corners, bath doors); taking doors from their swing arcs was tried twice and reverted (recall 88 %, precision
  fell to 80 %). The engineering drawing was not changed. A drawing change that would help: drawing a short wall
  nib between a door and an adjoining cross wall (feat/pro tried a 20 cm nib: doors 82.2 %, walls fell); not made.

### C3.1. Curved and circular rooms

Done end to end (PATCHES 60): the building model has curved walls (`Storey.arcs`), round rooms (`Room.circle`)
and spiral stairs (`Stair.shape`), all left out of the JSON when unused so engineering exports stay identical; the
drawing shows curved wall bands and spiral stairs; the PlanTo3D plan carries `floor.arcs` and `room.circle` (with
the disc's row slices in `rects`, so every rectangle-based step still works); PlanTo3D's vector reader recovers
circles drawn as short straight pieces, and the detector reads two concentric arcs a wall's thickness apart as a
curved wall and a room filling a circle as round; Blender builds curved walls, a disc floor, a skirting ring and a
lit cove; round rooms are furnished round the centre. Spiral stairs were already built in 3D. Tests: a villa with
a round rotunda and a spiral stair goes model -> drawing -> PDF without its model -> detector, and the curved wall
(full circle, radius within 5 %) and the round room come back. Not done: arcs in DXF and IFC exports, and in the AI
reader's PlanJSON (straight walls only).

### C3.2. Design details

In the room kits (PATCHES 62): tray ceilings with a warm LED cove (living, majlis, dining, bedrooms above a size),
slatted wood ceilings (foyer, lobby, passage), a chandelier in large living rooms, a pendant cluster over dining
tables, a styled TV wall (marble slab, LED line, walnut slats) behind every TV unit, wainscot panelling in dining
rooms; beds keep their walnut wall panel.

### C3.3. Unreal stills ([3d/unreal/](3d/unreal/README.md))

Made this time, with the Movie Render Queue launched from the command line: an editor script saves a one-frame
level sequence per camera and a render config (49 s), then `UnrealEditor ... -game -LevelSequence=...
-MoviePipelineConfig=...` renders and exits (74 s for the living room, 29 s for the front elevation, start-up
included). Honest state: the house in Unreal is feat/pro's import (before this run's heights and details), the
picture is mirrored against Blender's (a wrong Y flip for glTF imports) and the living room is overexposed;
`server.py`'s Unreal path still uses the old capture. Blender stays the default.

### C3.4. Reference vs Low vs High again ([3d/compare/index.md](3d/compare/index.md))

8 sheets (living, bedroom, bathroom, kitchen, dress, bar, puja, front elevation), nandu built from its model so the
bar and puja are furnished now. Sheets stay on disk (they contain your reference pictures). The gap left is in
bespoke pieces: curved and padded furniture, stone cladding, cascade chandeliers. Found and fixed on the way: hung
models (chandeliers, pendant clusters) were standing on the floor; they now hang from the ceiling.

## Finish

| Suite | Result |
|---|---|
| Backend (`TESTING=1 uv run pytest`) | **1365 passed, 4 skipped, 1 failed**: `test_fp_edit::test_locked_mode_refuses_instead_of_moving_others` failed once while the PlanTo3D suite ran alongside it (a time-limited solver test); it passes 3 of 3 runs on its own and passed in the run before |
| Frontend (`vitest run`) | **300 passed**; `tsc -b` clean; `vite build` OK |
| PlanTo3D (`tests/run_all.sh`) | all unit tests pass (test_space, test_curves new); the same three checks on old job data fail as before (two tours, one doorway of an old build; `dfd12ccd8e35` is your new job, built before this run) |
| Engineering snapshot | PDF, SVG, PNG byte for byte and DXF entity by entity equal to feat/pro for 5 sample plans |
| Ruff | every changed backend module clean; the repository-wide count (736) is the existing baseline |

**New dependencies**: none (OpenCV, OR-Tools, ezdxf, pymupdf, Pillow and Unreal's own Movie Render Queue plugin
were already in use).

**SQL to run**: none; this run added no migration.

**Timings (Apple M1 Pro, 10 CPU / 16 GPU cores, 32 GB, AC)**: 2D plans median 6 s, longest 20 s (random briefs);
Low build with light maps 160-185 s; Cycles stills 90-113 s a room, 22 s an elevation (1920 x 1080, 96 samples);
Unreal MRQ 29-74 s a still including start-up.

## What you need to decide

1. **Plan reader model**: claude-fable-5-2 reads scans far better (walls 95 % vs 69 %) at about 4x the cost
   ($0.84 vs $0.22 a plan) and minutes per plan. The default stays claude-opus-5-5.
2. **Setbacks default 0**: done as asked. The brief that worked now lays out a larger area, so its plan changes
   (with feat/pro's setbacks it reaches the solver exactly as before; even on feat/pro the solver returned a
   different plan on each run). DBC Table K.1 asks 3 m for a standalone villa; a warning is shown only when a
   setback is between 0 and 3 m.
3. **Walkthrough view**: 90 degrees across on every screen. On a 16:9 desktop the old view was wider (102) but
   stretched; say if you want 100 there.
4. **Small rooms**: under 120 sq ft furniture is held to 38 % of the floor, so a 117 sq ft bedroom lost its
   nightstands. The threshold is one number (`furnish.py`).
5. **Taller living rooms and majlis**: a storey has one height; tray ceilings make the middle read higher. A true
   double-height living room needs a plan-level "void above" decision.
6. **Unreal**: worth finishing (fix the mirror, the exposure and the server path) only if you want Lumen stills;
   the seat licence above USD 1 M revenue still applies.
7. **Presentation colours**: the palette is in `drawing/presentation.py` (`FLOOR`, `SITE`): approve or adjust.
