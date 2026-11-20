# Why two briefs got "No valid plan could be made" (A1, task 1)

Reproduced on feat/pro (ef0faba) with the configured reader (anthropic, claude-opus-5-5). The AI answers
were recorded once (`backend/tests/floorplan/fixtures/llm_cache/`, 10 live calls) and every diagnosis below
replays them, so no further AI calls were needed. Tools: `tools/floorplan_cases/run_brief.py` (whole
pipeline) and `tools/floorplan_cases/diagnose.py` (re-solves the program with one constraint family removed).

## What the generator did

Both briefs went through the same path: the room program was made (1 AI call), then the CP-SAT layout ran
three times per attempt (exact tiling 6 s, relaxed seed 0 8 s, relaxed seed 1 8 s), and after each failed
attempt the AI was asked to resize the rooms with the validator's feedback. With no layout at all the
feedback is only "NO_LAYOUT", so the AI changed little. Three attempts later the brief was refused:

| Brief | Time to refuse | Solver runs | AI calls | Message |
|---|---|---|---|---|
| 1 (6,000 sq ft plot, 5,000 built-up) | 44.5 s | 9, all "no layout found in time" | 4 | "the rooms could not be arranged ... Try smaller setbacks" |
| 2 (7,000 sq ft plot, 5,000 built-up) | 81.7 s | 9, all "no layout found in time" | 4 | same |

There was no step that relaxed anything: every wish in the brief was a hard constraint, and a failed solve
could only end in a refusal.

## Brief 1: contradictory and over-tight hard rules

Plot 19.3 x 28.9 m (shape assumed 2:3 from the area) = 558 m². Program: 19 spaces, 382 m² enclosed, 191 m²
open (three gardens, pool, courtyard, parking). Fourteen rules, all hard.

1. **Rules bound to the wrong room.** A rule names rooms by type, and a type always meant "the first room
   of that type" (`schemas/rules.py::resolve_ref`):
   - "front yard lawn" and "backyard garden" both became rules on `garden_1`, so one garden had to be at
     the front and at the rear at once. The solver proves this impossible in 0.0 s.
   - "one common washroom accessible from the foyer and the courtyard" became a rule on `bath_1`, the
     master bedroom's attached bath, which then had to share walls (with doors) with the bedroom, the
     wardrobe, the foyer and the courtyard: an 8 m² room with four door walls.
   - "a garden attached with the swimming pool" (the backyard one) became `garden_1` again.
2. **Rules that are impossible even alone.** With the door tree the program makes (the living room is the
   door parent of the courtyard, dining, meeting, gaming, puja, home theatre and lobby: seven rooms that
   must each share a wall with it), five of the fourteen rules found no layout even on their own within
   3 s: courtyard in the centre, garden touching living + dining + kitchen, puja at the front, pool at the
   rear, and the common washroom between foyer and courtyard.
3. **Solver time.** Even with no rules at all, a layout needed the full 20 s (found at 20.0 s); the
   generator gives each run 6 or 8 s.
4. **The stated built-up area was clamped by the setbacks.** The reader turned "built-up area of 5000 ft²"
   into a share (0.83 of the plot) instead of an area. Inside the default setbacks (3 m front, 1.5 m sides
   and rear) the house could use only 398 m², so the 463 m² asked for was cut to 390 m² without telling the
   person. The 65-75 % band did not apply here (a share was given), but it would have overruled a share
   outside it if the reader had not given one.
5. **Words lost or misread.** "Four year" / "for year" (foyer) was read correctly by the AI here, but "Master
   bedroom 18" was dropped silently, "lawn" became a third garden, and puja and home theatre became the
   generic type "other".

Removing all rules or all setbacks did not help on its own: with rules the model is infeasible (proved in
0.0-0.1 s), and without rules it needs more time than an attempt gets.

## Brief 2: more area asked for than the plot holds

Plot 20.8 x 31.25 m (shape assumed) = 650 m², built-up asked 5,000 sq ft = 464 m² (read as a 0.71 share).
Program: 12 spaces, 453 m² enclosed and 300 m² open (garden 160, pool 70, courtyard 70): 753 m² on a 650 m²
plot.

1. **The open areas were sized as if the plot were empty.** With only seven rooms to reach the 464 m²
   built-up target, the program scaled every room up (living 147 m², meeting room 98 m², dining 74 m²) and
   the garden, pool and courtyard took their targets from the plot share, not from what the house left.
   The lower ends of the area bands (82 % of each target) still add up to more than the plot inside the
   setbacks.
2. **Setbacks.** With the default setbacks the enclosed rooms had to fit in 476 m² and the open areas in the
   174 m² of setback strips. With no setbacks a layout was found; with rooms at 80 % of their targets a
   layout was found too.
3. **Aspect limits on large rooms.** A 147 m² living room may be at most 1.8:1, so it needs about 9 m by
   16 m on a plot 17.8 m wide inside the setbacks, which leaves almost nothing beside it.
4. **Same retry loop with no relaxation**, so the person got a refusal after 82 s.
5. **Words lost.** "And four and courtyard in front" (foyer and courtyard at the front) lost the foyer; the AI
   noted it as unclear but nothing asked the person. "Lawn [and] garden in front yard and backyard
   respectively" became a pool at the front and one garden at the rear (the lawn was lost).

## The brief that worked

The 4,500 sq ft brief has no layout rules, 15 spaces and a 2:3 plot; the exact tiling timed out at 6 s and
the first relaxed solve passed. Its program, plot and solver calls on feat/pro are recorded in
`backend/tests/floorplan/fixtures/golden/works_solver_inputs.json`. Note: even on feat/pro the solver
returns a different (equally valid) plan on each run, because it is time-limited and uses 8 threads (three
runs gave three different files). "Identical output" is therefore tested as identical solver inputs and the
same first-pass path; see SUMMARY.md.

## Causes, by family

| Family | Brief 1 | Brief 2 |
|---|---|---|
| Built-up share band / clamp | stated built-up clamped by the setbacks (463 -> 390 m²) | stated built-up kept, but open areas sized from the whole plot |
| Setbacks | 3 / 1.5 / 1.5 m left 398 m² | left 476 m² for 453 m² of rooms |
| Room minimums and area bands | 82 % lower band on every room | lower bands add up to more than the plot |
| Hard adjacency and side rules | 14 hard rules, 3 bound to the wrong room, 5 impossible alone | 3 hard side rules |
| Door tree | living room is the door parent of 7 rooms | - |
| Aspect limits | habitable 1.8:1 | 147 m² living at 1.8:1 |
| Assumed plot shape | 2:3 only | 2:3 only |
| Solver time | 6-8 s per run; a rule-free layout needed 20 s | - |
| Retry loop | 3 AI resizes, no relaxation, then refusal | same |
| Reading | "Master bedroom 18" dropped, lawn -> garden | foyer and lawn lost |
