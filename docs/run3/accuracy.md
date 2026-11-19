
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
