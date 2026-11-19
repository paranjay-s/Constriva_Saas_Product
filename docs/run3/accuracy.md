
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
