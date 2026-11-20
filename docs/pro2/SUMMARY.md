# feat/pro_2 summary

Branch feat/pro_2, made from feat/pro (ab053ee). Every task is committed on its own; nothing pushed; main
untouched. Hardware for every timing: Apple M1 Pro (10 CPU cores, 16-core GPU, 32 GB), macOS, on AC power.
Task-by-task status and commits: [LOG.md](LOG.md).

Budgets so far: live AI calls 14 of 100 (all claude-opus-5-5, the configured reader); rendering 0 of 180 min.

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

The engineering drawing is unchanged: PDF, SVG, PNG and DXF of the five sample plans are byte for byte the
feat/pro files once the run stamps are blanked (PDF dates and file ID, DXF GUIDs and creation stamps) - 20
files, tested on every run (`test_fp_engineering_snapshot.py`; 200 repeated PDF exports all matched).

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

Not started yet.
