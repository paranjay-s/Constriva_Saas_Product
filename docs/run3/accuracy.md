
## Run 3: held-out after the verifier, size fit and library (26 fresh AI reads: regenerated PDFs missed the old cache) (held set, 50 plans, 26 fresh AI calls)

| style | plans | read | detector / ai / none | wall recall | wall precision | doors found | windows found | room type | specials | storeys | building type |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fills | 6 | 100% | 6 / 0 / 0 | 56% | 61% | 74% | 67% | 68% | 26% | 100% | 50% |
| hatched | 6 | 100% | 6 / 0 / 0 | 35% | 45% | 58% | 49% | 46% | 24% | 100% | 50% |
| lines | 6 | 100% | 6 / 0 / 0 | 63% | 65% | 75% | 71% | 73% | 23% | 100% | 50% |
| raster_fills | 7 | 100% | 0 / 7 / 0 | 54% | 40% | 29% | 37% | 82% | 44% | 100% | 71% |
| raster_hatched | 7 | 100% | 0 / 7 / 0 | 53% | 43% | 47% | 30% | 91% | 45% | 100% | 86% |
| raster_lines | 6 | 100% | 0 / 6 / 0 | 60% | 44% | 48% | 54% | 82% | 47% | 100% | 50% |
| raster_solid | 6 | 100% | 0 / 6 / 0 | 30% | 22% | 46% | 40% | 88% | 44% | 100% | 50% |
| solid | 6 | 100% | 6 / 0 / 0 | 51% | 62% | 67% | 59% | 58% | 30% | 100% | 83% |
| ALL | 50 | 100% | 24 / 26 / 0 | 50% | 45% | 53% | 48% | 75% | 36% | 100% | 62% |

## Scorer fix: wall spans inside door and window openings are neutral

The truth stops its walls at every opening; the readers run a wall through it. Until now that span counted as extra
wall (precision). A wall sample inside an opening of either plan, on the same line, now counts on neither side.
Same readings (the dump of one read pass, 0 fresh AI calls), scored by both rules:

### Old rule (spans across openings count)

| style | plans | read | detector / ai / none | wall recall | wall precision | doors found | windows found | room type | specials | storeys | building type |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fills | 6 | 100% | 6 / 0 / 0 | 56% | 61% | 74% | 67% | 68% | 26% | 100% | 50% |
| hatched | 6 | 100% | 6 / 0 / 0 | 35% | 45% | 58% | 49% | 46% | 24% | 100% | 50% |
| lines | 6 | 100% | 6 / 0 / 0 | 63% | 65% | 75% | 71% | 73% | 23% | 100% | 50% |
| raster_fills | 7 | 100% | 0 / 7 / 0 | 54% | 40% | 29% | 37% | 82% | 44% | 100% | 71% |
| raster_hatched | 7 | 100% | 0 / 7 / 0 | 53% | 43% | 47% | 30% | 91% | 45% | 100% | 86% |
| raster_lines | 6 | 100% | 0 / 6 / 0 | 60% | 44% | 48% | 54% | 82% | 47% | 100% | 50% |
| raster_solid | 6 | 100% | 0 / 6 / 0 | 30% | 22% | 46% | 40% | 88% | 44% | 100% | 50% |
| solid | 6 | 100% | 6 / 0 / 0 | 51% | 62% | 67% | 59% | 58% | 30% | 100% | 83% |
| ALL | 50 | 100% | 24 / 26 / 0 | 50% | 45% | 53% | 48% | 75% | 36% | 100% | 62% |

### New rule (openings neutral)

| style | plans | read | detector / ai / none | wall recall | wall precision | doors found | windows found | room type | specials | storeys | building type |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fills | 6 | 100% | 6 / 0 / 0 | 56% | 62% | 74% | 67% | 68% | 26% | 100% | 50% |
| hatched | 6 | 100% | 6 / 0 / 0 | 34% | 45% | 58% | 49% | 46% | 24% | 100% | 50% |
| lines | 6 | 100% | 6 / 0 / 0 | 63% | 66% | 75% | 71% | 73% | 23% | 100% | 50% |
| raster_fills | 7 | 100% | 0 / 7 / 0 | 52% | 43% | 29% | 37% | 82% | 44% | 100% | 71% |
| raster_hatched | 7 | 100% | 0 / 7 / 0 | 51% | 47% | 47% | 30% | 91% | 45% | 100% | 86% |
| raster_lines | 6 | 100% | 0 / 6 / 0 | 58% | 48% | 48% | 54% | 82% | 47% | 100% | 50% |
| raster_solid | 6 | 100% | 0 / 6 / 0 | 28% | 23% | 46% | 40% | 88% | 44% | 100% | 50% |
| solid | 6 | 100% | 6 / 0 / 0 | 50% | 63% | 67% | 59% | 58% | 30% | 100% | 83% |
| ALL | 50 | 100% | 24 / 26 / 0 | 49% | 48% | 53% | 48% | 75% | 36% | 100% | 62% |

The bias was smaller than estimated: vector precision moves about 1 point, raster 3-4. The vector losses were
elsewhere (next section).

## Vector fix 1: the scale

Cause (tools/testplans/causes.py on the five worst vector plans and overlays): on 10 of 24 held-out vector plans the
scale was 2.0x the truth, so every wall was half size and scored as "absent". No room-size label could be measured
(a label ray through a door or window gap found no wall), and the fallback assumed the main wall is 4.5" when it was
the 9" outer wall. Fixes in detect.py, both general: a label ray that finds no wall looks for the nearest wall running
the right way within 8 wall thicknesses (wider than any opening); and with no measurable label, the main wall is
taken as 9" when 15 % or more of the wall length is about half as thick (4.5" partitions). Reference plans: the two
vector ones read the same walls and rooms (scale moved 0.03 %); the five scanned ones are refused before and after.

### Held-out after fix 1 (openings neutral, readers only)

| style | plans | read | detector / ai / none | wall recall | wall precision | doors found | windows found | room type | specials | storeys | building type |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fills | 6 | 100% | 6 / 0 / 0 | 98% | 97% | 99% | 99% | 86% | 47% | 100% | 50% |
| hatched | 6 | 100% | 6 / 0 / 0 | 64% | 74% | 72% | 81% | 61% | 41% | 100% | 33% |
| lines | 6 | 100% | 6 / 0 / 0 | 100% | 99% | 98% | 100% | 83% | 36% | 100% | 50% |
| raster_fills | 7 | 100% | 0 / 7 / 0 | 52% | 43% | 29% | 37% | 82% | 44% | 100% | 71% |
| raster_hatched | 7 | 100% | 0 / 7 / 0 | 51% | 47% | 47% | 30% | 91% | 45% | 100% | 86% |
| raster_lines | 6 | 100% | 0 / 6 / 0 | 58% | 48% | 48% | 54% | 82% | 47% | 100% | 50% |
| raster_solid | 6 | 100% | 0 / 6 / 0 | 28% | 23% | 46% | 40% | 88% | 44% | 100% | 50% |
| solid | 6 | 100% | 6 / 0 / 0 | 84% | 83% | 100% | 100% | 83% | 43% | 100% | 83% |
| ALL | 50 | 100% | 24 / 26 / 0 | 64% | 60% | 63% | 63% | 82% | 43% | 100% | 60% |

## Vector fix 2: the scale, per-axis votes

Cause: with a partition the reader missed, a label's width ray crosses into the next room, so its width and depth
disagree and the label was dropped; the scale then came from two labels that agreed by chance (3x on one plan).
Fix (detect.py): each axis votes on its own (a label whose width and depth agree is two votes, a single axis half a
vote per orientation); between the clear and the centre-line readings, the one with more labels that agree with each
other wins, then the one with 1.5x the support, then the one nearer the scale from the wall thickness.
tests/test_scale.py covers both fixes on synthetic walls (it fails on the detector before run 3).

**Caution on the held-out numbers below:** fixes 1 and 2 were found by looking at held-out plans (p162, p186, p195,
p177), so the held-out set is no longer a clean measure of them. The 150 tuning plans were not looked at during this
work: they are the clean check, scored with the detector before run 3 and after (vector styles only; the raster
tuning plans have no cached AI reply and were not read).

### HELD after fixes 1-2 (held set, 50 plans, 0 fresh AI calls)

| style | plans | read | detector / ai / none | wall recall | wall precision | doors found | windows found | room type | specials | storeys | building type |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fills | 6 | 100% | 6 / 0 / 0 | 100% | 99% | 99% | 99% | 86% | 47% | 100% | 50% |
| hatched | 6 | 100% | 6 / 0 / 0 | 100% | 99% | 99% | 100% | 82% | 55% | 100% | 50% |
| lines | 6 | 100% | 6 / 0 / 0 | 100% | 99% | 98% | 100% | 83% | 36% | 100% | 50% |
| raster_fills | 7 | 100% | 0 / 7 / 0 | 52% | 43% | 29% | 37% | 82% | 44% | 100% | 71% |
| raster_hatched | 7 | 100% | 0 / 7 / 0 | 51% | 47% | 47% | 30% | 91% | 45% | 100% | 86% |
| raster_lines | 6 | 100% | 0 / 6 / 0 | 58% | 48% | 48% | 54% | 82% | 47% | 100% | 50% |
| raster_solid | 6 | 100% | 0 / 6 / 0 | 28% | 23% | 46% | 40% | 88% | 44% | 100% | 50% |
| solid | 6 | 100% | 6 / 0 / 0 | 100% | 99% | 100% | 100% | 83% | 43% | 100% | 83% |
| ALL | 50 | 100% | 24 / 26 / 0 | 71% | 65% | 66% | 66% | 85% | 45% | 100% | 62% |

### TUNE vector, detector before run 3 fixes (tune set, 150 plans, 0 fresh AI calls)

| style | plans | read | detector / ai / none | wall recall | wall precision | doors found | windows found | room type | specials | storeys | building type |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fills | 19 | 100% | 19 / 0 / 0 | 35% | 44% | 57% | 45% | 52% | 29% | 100% | 58% |
| hatched | 19 | 100% | 19 / 0 / 0 | 49% | 56% | 58% | 55% | 61% | 29% | 100% | 37% |
| lines | 19 | 100% | 19 / 0 / 0 | 47% | 62% | 56% | 47% | 47% | 24% | 100% | 58% |
| raster_fills | 18 | 0% | 0 / 0 / 18 | 0% | - | 0% | 0% | 0% | 0% | 0% | 0% |
| raster_hatched | 18 | 0% | 0 / 0 / 18 | 0% | - | 0% | 0% | 0% | 0% | 0% | 0% |
| raster_lines | 19 | 0% | 0 / 0 / 19 | 0% | - | 0% | 0% | 0% | 0% | 0% | 0% |
| raster_solid | 19 | 0% | 0 / 0 / 19 | 0% | - | 0% | 0% | 0% | 0% | 0% | 0% |
| solid | 19 | 100% | 19 / 0 / 0 | 34% | 42% | 45% | 38% | 52% | 24% | 100% | 63% |
| ALL | 150 | 51% | 76 / 0 / 74 | 20% | 51% | 26% | 22% | 26% | 14% | 51% | 27% |

### TUNE vector, detector after fixes 1-2 (tune set, 150 plans, 0 fresh AI calls)

| style | plans | read | detector / ai / none | wall recall | wall precision | doors found | windows found | room type | specials | storeys | building type |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fills | 19 | 100% | 19 / 0 / 0 | 93% | 92% | 95% | 95% | 82% | 47% | 100% | 53% |
| hatched | 19 | 100% | 19 / 0 / 0 | 99% | 98% | 100% | 100% | 84% | 48% | 100% | 42% |
| lines | 19 | 100% | 19 / 0 / 0 | 92% | 95% | 94% | 92% | 80% | 49% | 100% | 63% |
| raster_fills | 18 | 0% | 0 / 0 / 18 | 0% | - | 0% | 0% | 0% | 0% | 0% | 0% |
| raster_hatched | 18 | 0% | 0 / 0 / 18 | 0% | - | 0% | 0% | 0% | 0% | 0% | 0% |
| raster_lines | 19 | 0% | 0 / 0 / 19 | 0% | - | 0% | 0% | 0% | 0% | 0% | 0% |
| raster_solid | 19 | 0% | 0 / 0 / 19 | 0% | - | 0% | 0% | 0% | 0% | 0% | 0% |
| solid | 19 | 100% | 19 / 0 / 0 | 91% | 96% | 92% | 89% | 77% | 39% | 100% | 79% |
| ALL | 150 | 51% | 76 / 0 / 74 | 46% | 95% | 47% | 46% | 40% | 25% | 51% | 30% |

## Causes after fixes 1-2 (tools/testplans/causes.py; overlays in docs/run3/accuracy_overlays/, git-ignored)

| group | miss offset | miss short/long | miss absent | extra offset | extra short/long | extra absent |
|---|---|---|---|---|---|---|
| vector (held-out) | - | 0% | 0% | 0% | 1% | - |
| raster (held-out) | 41% | 1% | 9% | 34% | 4% | 20% |

Five worst vector plans (held-out): recall 0.99-1.00, precision 0.97-0.99; what is left is 2-4 ft of wall ends
running short or long per plan. Five worst raster plans (all AI reads): recall 0.18-0.21, precision 0.14-0.18.

Raster: "offset" (a wall read beside where it is) dominates. Removing one shift per plan (the same for every storey)
raises recall only partly (raster_solid 28 -> 45 %, raster_fills 52 -> 60 %, raster_hatched 51 -> 53 %,
raster_lines 58 -> 55 %), so it is mostly wall-by-wall position error of the AI plan reader, plus a plan-wide shift of
about 1.1 ft on solid walls (the outer face read as the wall line). The scorer is not changed for this: a shift-aligned
score would hide real per-storey errors. The fix is a deterministic scanned reader (Stage 2), which keeps the rule that
the AI never supplies geometry.

## Vector fixes 3-4: choosing the size convention, and the nearest wall beside a gap

Fix 3 (detect.py): between the clear and the centre-line readings of the labels, the one with more labels whose width
and depth agree at its scale wins; on a tie, the one whose agreeing labels agree more tightly (the right convention
gives the same scale on every label); the wall-thickness scale decides only without such labels and within 3 % of a
reading. (A first version that used the wall-thickness scale earlier broke the sample plan: 12.55 instead of 12.0.)
Fix 4 (detect.py and fit.py): a ray from a label takes the nearest of the walls on its line and the walls running the
right way within the band; before, a ray through a door that reached a wall of the next room kept that wall.

Tuning set (clean, not looked at) after fixes 1-4, vector, readers only, openings neutral:

### held: after fixes 1-4 (scale; nearest wall beside a gap) (held set, 50 plans, 0 fresh AI calls)

| style | plans | read | detector / ai / none | wall recall | wall precision | doors found | windows found | room type | specials | storeys | building type |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fills | 6 | 100% | 6 / 0 / 0 | 100% | 99% | 99% | 99% | 86% | 47% | 100% | 50% |
| hatched | 6 | 100% | 6 / 0 / 0 | 100% | 99% | 99% | 100% | 82% | 55% | 100% | 50% |
| lines | 6 | 100% | 6 / 0 / 0 | 100% | 99% | 98% | 100% | 83% | 36% | 100% | 50% |
| raster_fills | 7 | 100% | 0 / 7 / 0 | 52% | 43% | 29% | 37% | 82% | 44% | 100% | 71% |
| raster_hatched | 7 | 100% | 0 / 7 / 0 | 51% | 47% | 47% | 30% | 91% | 45% | 100% | 86% |
| raster_lines | 6 | 100% | 0 / 6 / 0 | 58% | 48% | 48% | 54% | 82% | 47% | 100% | 50% |
| raster_solid | 6 | 100% | 0 / 6 / 0 | 28% | 23% | 46% | 40% | 88% | 44% | 100% | 50% |
| solid | 6 | 100% | 6 / 0 / 0 | 100% | 99% | 100% | 100% | 83% | 43% | 100% | 83% |
| ALL | 50 | 100% | 24 / 26 / 0 | 71% | 65% | 66% | 66% | 85% | 45% | 100% | 62% |

### tune: after fixes 1-4 (scale; nearest wall beside a gap) (tune set, 150 plans, 0 fresh AI calls)

| style | plans | read | detector / ai / none | wall recall | wall precision | doors found | windows found | room type | specials | storeys | building type |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fills | 19 | 100% | 19 / 0 / 0 | 100% | 99% | 100% | 99% | 82% | 47% | 100% | 53% |
| hatched | 19 | 100% | 19 / 0 / 0 | 97% | 96% | 99% | 98% | 84% | 48% | 100% | 42% |
| lines | 19 | 100% | 19 / 0 / 0 | 100% | 98% | 99% | 100% | 84% | 51% | 100% | 58% |
| raster_fills | 18 | 0% | 0 / 0 / 18 | 0% | - | 0% | 0% | 0% | 0% | 0% | 0% |
| raster_hatched | 18 | 0% | 0 / 0 / 18 | 0% | - | 0% | 0% | 0% | 0% | 0% | 0% |
| raster_lines | 19 | 0% | 0 / 0 / 19 | 0% | - | 0% | 0% | 0% | 0% | 0% | 0% |
| raster_solid | 19 | 0% | 0 / 0 / 19 | 0% | - | 0% | 0% | 0% | 0% | 0% | 0% |
| solid | 19 | 100% | 19 / 0 / 0 | 100% | 99% | 99% | 100% | 84% | 45% | 100% | 79% |
| ALL | 150 | 51% | 76 / 0 / 74 | 49% | 98% | 49% | 49% | 42% | 25% | 51% | 29% |

## Step 3: the size-fit pass

The fit had become harmful once the scale was right: with it, held-out vector wall recall fell from 100 % to 70-86 %
(p162: 0.998 -> 0.217). Causes, all fixed in fit.py: the clear/centre-line convention was chosen per room (one drawing
uses one); the centre-line size used one wall thickness for 9" outer walls and 4.5" partitions alike; the storey was
rescaled for differences of 0.5 % (labels rounded to the inch are that noisy; now 1.5 %); and rooms were measured from
the reader's room rectangle, which can span two rooms or stop at a wall centre. Rooms are now measured between the
walls, from where the name is written (detect.py writes  for each room).

Labelled rooms within 2 % of their label (measured between the walls, with the storey's convention) and wall recall,
without and with the fit:

| set | style | labelled rooms | within 2 % | with fit | wall recall | with fit |
|---|---|---|---|---|---|---|
| held-out | fills | 94 | 91% | 91% | 100% | 100% |
| held-out | hatched | 94 | 79% | 79% | 100% | 100% |
| held-out | lines | 58 | 93% | 93% | 100% | 100% |
| held-out | solid | 87 | 92% | 92% | 100% | 100% |
| held-out | vector | 333 | 88% | 88% | 100% | 100% |
| tuning | fills | 250 | 89% | 89% | 100% | 100% |
| tuning | hatched | 254 | 89% | 89% | 97% | 97% |
| tuning | lines | 309 | 87% | 86% | 100% | 100% |
| tuning | solid | 331 | 91% | 91% | 100% | 100% |
| tuning | vector | 1144 | 89% | 89% | 99% | 99% |

Before fixes 1-4 about 20 % of labelled rooms were within 2 %. The fit now leaves correct readings as they are (it
still removes a planted 3 % scale error, tests/test_fit.py); the rooms still more than 2 % off are where a room is not
a rectangle between four walls (L-shapes, open plan) or its label is rounded. The Stage 5 target (every room within
2 %) is not met: 88-89 %.
