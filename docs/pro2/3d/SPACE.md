# Space: why rooms looked smaller, and what changed (C1)

Measured 2026-11-20 on two plans: the fresh plan from the internet (`~/Downloads/1000207168.pdf`, PlanTo3D job
`dfd12ccd8e35`, a 72 dpi scan read by the AI reader; the brief named `docs/reference/plans/<file name>`, which
does not exist, so this is the newest plan the owner built) and `docs/reference/floorplans/OPT 5 - GEETA JI GAUD.pdf`
(vector, read by PlanTo3D's detector). Tool: `services/planto3d/tools/space_check.py PLAN.json [META.json] --md`.

## Findings (before)

| What | Measured | Effect on how big a room reads |
|---|---|---|
| Walls eating into rooms | 0.0-0.6 % of each room's rectangle on both plans: rooms are read to the inside wall faces and walls are built outside them | none: the 3D keeps the drawing's sizes |
| Room size against its label, OPT 5 (vector) | 18 of 30 labelled rooms within 5 %; the misses are rooms split or merged by the reading (parking, sit-out, a wash room) | rooms really smaller only where the reading is wrong |
| Room size against its label, fresh plan (scan, AI reader) | **2 of 13 within 5 %**; BED 11'6"x12' built 8.2 x 12.0 ft (29 % narrow), DINING 22 %, a KITCHEN 52 %, the STAIR 41 % | **the main cause on this plan**: the AI reader's walls are rough (outer walls on the dimension lines, see C2) |
| Floor to ceiling | 10 ft = 3.05 m (the readers' default) | ordinary for a villa; rooms read low |
| Doors and window heads | 7 ft = 2.13 m | low doors make walls look tall and rooms small |
| Eye height | 1.6 m | right |
| Walkthrough field of view | 70 degrees vertical: 102 degrees across on a 16:9 window, 86 on 4:3, narrower in a tall iframe | inconsistent; on wide screens the edges stretch, on narrow ones the room is cropped |
| High stills | 16-24 mm, level cameras from a corner | 16 mm stretches small rooms at the edges |
| Furniture | queen bed in any room from 9 ft wide, 0.67 m at the bed's foot, every optional piece in small rooms (40-53 % of a bedroom's floor covered) | crowded small rooms |
| Finishes and light | scheme walls about 0.80-0.86 grey-beige; indoor lamps at the earlier strength | darker rooms read smaller |

Per room, fresh plan (before; walls inside the room = share of the room's rectangle that walls cover; pieces and
floor covered from the built house):

| Floor | Room | Label (ft) | Read inside the walls (ft) | Diff | Walls inside the room | Pieces | Floor covered | Widest free strip beside the tightest piece (m) |
|---|---|---|---|---|---|---|---|---|
| Typical Floor | BED 12'-0" x10'-0" | 10.0 x 12.0 | 9.8 x 11.9 | 2% | 0.0% | 4 | 40% | 0.86 |
| Typical Floor | TOILET 4'-10"x8'-0" | 4.8 x 8.0 | 5.2 x 8.0 | 7% | 0.0% | 3 | 35% | 0.81 |
| Typical Floor | BED 12'-2" x10'-6" | 10.5 x 12.2 | 10.2 x 12.0 | 3% | 0.0% | 3 | 43% | 1.10 |
| Typical Floor | LOBBY | - | 5.1 x 5.6 | - | 0.0% | 0 | 0% | - |
| Typical Floor | TOILET 8'-0"x3'-10" | 3.8 x 8.0 | 3.9 x 7.5 | 7% | 0.4% | 2 | 26% | 0.56 |
| Typical Floor | PASSAGE | - | 4.0 x 4.5 | - | 0.0% | 0 | 0% | - |
| Typical Floor | KITCHEN 8'-0"x5'-0" | 5.0 x 8.0 | 4.4 x 7.6 | 12% | 0.0% | 1 | 27% | 0.01 |
| Typical Floor | KITCHEN 8'-0"x5'-6" | 5.5 x 8.0 | 2.6 x 7.7 | 52% | 0.6% | 2 | 60% | 0.00 |
| Typical Floor | STAIR 15'-4"x7'-6" | 7.5 x 15.3 | 4.4 x 14.7 | 41% | 0.0% | 0 | 0% | - |
| Typical Floor | TOILET 8'-0"x4'-0" | 4.0 x 8.0 | 4.0 x 10.1 | 26% | 0.4% | 2 | 19% | 0.56 |
| Typical Floor | DINING 8'-9"x11'-7" | 8.8 x 11.6 | 8.2 x 9.0 | 22% | 0.0% | 0 | 0% | - |
| Typical Floor | BED 11'-6"x12'-0" | 11.5 x 12.0 | 8.2 x 12.0 | 29% | 0.0% | 3 | 53% | 1.08 |
| Typical Floor | BED 10'-1" x10'-0" | 10.0 x 10.1 | 9.0 x 10.1 | 10% | 0.0% | 3 | 41% | 0.76 |
| Typical Floor | VER. 7'-2"x2'-3" | 2.2 x 7.2 | 2.5 x 6.9 | 9% | 0.0% | 0 | 0% | - |
| Typical Floor | VER. 11'-2"x2'-6" | 2.5 x 11.2 | 0.6 x 11.3 | 78% | 0.0% | 0 | 0% | - |


Per room, OPT 5 (plan only):

| Floor | Room | Label (ft) | Read inside the walls (ft) | Diff | Walls inside the room | Pieces | Floor covered | Widest free strip beside the tightest piece (m) |
|---|---|---|---|---|---|---|---|---|
| Ground Floor | OPEN | - | 2.7 x 23.5 | - | 0.0% | - | - | - |
| Ground Floor | DRESS/TOI. 7'X11'6 | 7.0 x 11.5 | 6.9 x 9.8 | 14% | 0.0% | - | - | - |
| Ground Floor | WASH | - | 1.9 x 12.2 | - | 0.0% | - | - | - |
| Ground Floor | BEDROOM 15'9X11'6 | 11.5 x 15.8 | 11.4 x 15.7 | 1% | 0.0% | - | - | - |
| Ground Floor | KIT. 12'6X10' | 10.0 x 12.5 | 9.8 x 12.3 | 2% | 0.0% | - | - | - |
| Ground Floor | DRG./DIN. 17'9 X 21' | 17.8 x 21.0 | 16.0 x 17.7 | 16% | 0.0% | - | - | - |
| Ground Floor | TOI. 9'X5' | 5.0 x 9.0 | 4.9 x 8.9 | 2% | 0.0% | - | - | - |
| Ground Floor | OPEN 4'6X10'4 | 4.5 x 10.3 | 4.1 x 10.2 | 8% | 0.0% | - | - | - |
| Ground Floor | BEDROOM 13'4X10'4 | 10.3 x 13.3 | 10.2 x 13.2 | 2% | 0.0% | - | - | - |
| Ground Floor | DRESS/TOI. 6'X15'4 | 6.0 x 15.3 | 6.0 x 15.3 | 1% | 0.0% | - | - | - |
| Ground Floor | BEDROOM 11'4X15'4 | 11.3 x 15.3 | 11.2 x 15.3 | 1% | 0.0% | - | - | - |
| Ground Floor | PARKING 18X18'6 | 18.0 x 18.5 | 10.4 x 17.8 | 42% | 0.0% | - | - | - |
| Ground Floor | stair | - | 3.5 x 11.5 | - | 0.0% | - | - | - |
| Ground Floor | PARKING 6'X8'2 | 6.0 x 8.2 | 3.5 x 6.5 | 42% | 0.0% | - | - | - |
| First Floor | yard | - | 2.8 x 10.3 | - | 0.0% | - | - | - |
| First Floor | yard | - | 2.8 x 10.1 | - | 0.0% | - | - | - |
| First Floor | WASH 7'5X5' | 5.0 x 7.4 | 4.7 x 7.3 | 6% | 0.0% | - | - | - |
| First Floor | KIT. 7'5X9'6 | 7.4 x 9.5 | 7.3 x 9.8 | 4% | 0.0% | - | - | - |
| First Floor | DRG./DIN. 13'4X21' | 13.3 x 21.0 | 13.2 x 20.9 | 1% | 0.0% | - | - | - |
| First Floor | ENT.LOBBY 5'X10'4 | 5.0 x 10.3 | 4.8 x 10.3 | 4% | 0.0% | - | - | - |
| First Floor | WASH 7'5X5' | 5.0 x 7.4 | 2.7 x 7.4 | 46% | 0.0% | - | - | - |
| First Floor | KIT. 7'5X9'6 | 7.4 x 9.5 | 7.3 x 9.4 | 2% | 0.0% | - | - | - |
| First Floor | BEDROOM 10'X11'6 | 10.0 x 11.5 | 9.5 x 9.8 | 14% | 0.0% | - | - | - |
| First Floor | BEDROOM 10'X11'6 | 10.0 x 11.5 | 9.5 x 9.9 | 13% | 0.0% | - | - | - |
| First Floor | TOI. 4'X7' | 4.0 x 7.0 | 3.9 x 6.9 | 2% | 0.0% | - | - | - |
| First Floor | DRG./DIN. 13'4X21' | 13.3 x 21.0 | 13.3 x 20.9 | 0% | 0.0% | - | - | - |
| First Floor | ENT.LOBBY 5'X10'4 | 5.0 x 10.3 | 4.8 x 10.3 | 4% | 0.0% | - | - | - |
| First Floor | TOI. 4'X7' | 4.0 x 7.0 | 3.9 x 6.9 | 2% | 0.0% | - | - | - |
| First Floor | OPEN 4'X6'4 | 4.0 x 6.3 | 4.2 x 6.3 | 6% | 0.0% | - | - | - |
| First Floor | OPEN 4'X6'4 | 4.0 x 6.3 | 4.2 x 6.3 | 6% | 0.0% | - | - | - |
| First Floor | TOI. 4'X7' | 4.0 x 7.0 | 3.9 x 6.8 | 3% | 0.0% | - | - | - |
| First Floor | TOI. 4'X7' | 4.0 x 7.0 | 3.9 x 6.8 | 3% | 0.0% | - | - | - |
| First Floor | BEDROOM 12'6X10' | 10.0 x 12.5 | 9.9 x 12.3 | 2% | 0.0% | - | - | - |
| First Floor | BEDROOM 12'6X10' | 10.0 x 12.5 | 9.9 x 12.4 | 1% | 0.0% | - | - | - |
| First Floor | stair | - | 3.4 x 10.1 | - | 0.0% | - | - | - |
| First Floor | SITOUT 26' X 8' | 8.0 x 26.0 | 3.5 x 35.9 | 57% | 0.0% | - | - | - |


## What changed (every plan dimension kept exactly)

| Setting / change | Before | After |
|---|---|---|
| `PLAN3D_CEILING_M` floor to ceiling (villas; a plan that states its own height keeps it) | 3.05 m | **3.4 m** |
| `PLAN3D_DOOR_HEIGHT_M` | 2.13 m | **2.4 m** |
| `PLAN3D_WINDOW_HEAD_M` (level with the doors; sills unchanged) | 2.13 m | **2.4 m** |
| `PLAN3D_WALK_FOV_DEG` walkthrough field of view, set across the screen; "Wide view" button switches to 65 | 70 vertical (102 / 86 across) | **90 across on every window shape** |
| Eye height | 1.6 m | 1.6 m |
| High stills lens | 16-24 mm | **18-24 mm**, level (two-point perspective), from the corner along the longest diagonal; the corner is chosen from where the camera actually stands and the room's main piece counts most |
| Bed | queen from 9 ft, 0.67 m at its foot | **king from 13 ft, queen from 9 ft, single below; 0.9 m at the foot** wherever a wall allows |
| Small rooms (under 120 sq ft) | every optional piece | **optional pieces dropped while furniture covers more than 38 %** (48 % in larger rooms) |
| Mirrors | backlit vanity mirror in bathrooms | the same, **plus a full-length mirror in dressing rooms** |
| `PLAN3D_LIGHT_FINISHES` | scheme walls and wood as before | **45 % lighter towards warm white** |
| `PLAN3D_LAMP_GAIN` indoor lamps | 1x | **1.4x** |
| Taller living rooms and majlis | - | **not done as a taller storey**: a storey has one height. Round rooms get a lit cove ring; feature ceilings (C3.2) give living rooms and majlis a raised coffer |

After, fresh plan: room sizes are identical to before (the same reading); bedroom furniture covers 36-37 % instead
of 40-41 %; ceiling 3.40 m, doors 2.40 m.

## Before and after, three rooms ([space_compare/](space_compare/))

Fresh plan, built at Low with the feat/pro code and with this code (Apple M1 Pro, on AC power, `nice -n 10`):

| Room | Low (walkthrough, 1920 x 1080) | High (Cycles still, 1920 x 1080, 96 samples) |
|---|---|---|
| Bedroom 12'0" x 10'0" | [bedroom_low.jpg](space_compare/bedroom_low.jpg) | [bedroom_high.jpg](space_compare/bedroom_high.jpg) |
| Dining 8'9" x 11'7" | [dining_low.jpg](space_compare/dining_low.jpg) | [dining_high.jpg](space_compare/dining_high.jpg) |
| Toilet 4'10" x 8'0" | [toilet_low.jpg](space_compare/toilet_low.jpg) | [toilet_high.jpg](space_compare/toilet_high.jpg) |

Timings: Low build 160 s before, 178 s after (light maps baked); High stills 98-104 s before, 90-113 s after per
room. Note on the field of view: on a 16:9 screen the old camera saw wider (102 degrees) than the new 90, so the
Low pictures above are framed a little tighter; the room is no longer stretched at the edges, and on narrower
windows (the app's iframe) the new view is wider than before.

What the reading still gets wrong on the fresh plan (rooms 22-52 % short of their labels) is C2's subject: no
amount of height or lens makes a room built 8 ft wide look like 11'6".
