# Reference PDFs: what is still wrong (Stage 2)

Read with the current detector. Where the detector refuses a drawing (the four scans), the cached AI read is used, so
no fresh calls were made. Checks and confidence come from `checks.py` (PATCHES §17, §25). These drawings were never used
for tuning, and there is no hand-made truth for the four scans, so "no checks" there does not mean the plan is right.

### 1000205346.pdf
reader: ai (cached); storeys 1 (Ground Floor); walls 17, doors 13, windows 8, rooms 15; confidence rooms 0.81, openings 0.6
checks: none
least sure rooms: none

### 1000205542.pdf
reader: ai (cached); storeys 1 (Ground Floor); walls 18, doors 14, windows 15, rooms 15; confidence rooms 0.81, openings 0.62
checks: none
least sure rooms: none

### OPT 5 - GEETA JI GAUD.pdf
reader: detector; storeys 2 (Ground Floor, First Floor); walls 138, doors 21, windows 22, rooms 36; confidence rooms 0.85, openings 0.73
checks: {'multi_label': 5, 'area_mismatch': 1}
least sure rooms: none

### antonovich-design-20250DjgFZYRphpj.pdf
reader: ai (cached); storeys 1 (Ground Floor); walls 27, doors 13, windows 4, rooms 30; confidence rooms 0.81, openings 0.58
checks: none
least sure rooms: none

### antonovich-design-2025fMhHtV8AHyLf.pdf
reader: ai (cached); storeys 1 (Ground Floor); walls 17, doors 7, windows 1, rooms 17; confidence rooms 0.41, openings 0.57
checks: {'multi_label': 2, 'unknown_label': 1}
least sure rooms: 8 25,00, 9 48,50, 7 18,75, 1 18,00, 6 4,30, 11 5,20, 12 7,80, 4 6,30, 5 3,60, 3 5,70, 10 20,00, 2 32,70

### paranjay-villa.pdf
reader: detector; storeys 1 (Ground Floor); walls 53, doors 10, windows 12, rooms 12; confidence rooms 0.95, openings 0.84
checks: none
least sure rooms: none

## What is still wrong, as far as can be seen without truth files

- **antonovich-design-2025fMhHtV8AHyLf**: rooms are labelled with a number and an area ("8 25,00"). The names
  presumably sit in a legend table elsewhere on the sheet. Twelve rooms are built as generic rooms (average confidence
  0.41). Fix to make, not done: have the AI reader map legend numbers to names. That changes the parser prompt and needs
  live calls, so it is left for you to approve.
- **OPT 5**: 5 rooms name two uses ("KITCHEN / DINING" style), each built as one space with zones, and 1 area mismatch.
  The two rooms the tour could not reach before now get a jump (PATCHES §21).
- **SF plan (stored job)**: door 9 is fixed in the detector (PATCHES §24), but the stored job keeps its old plan until
  it is read again.
- **AI-read scans (1000205346, 1000205542, antonovich 0Djg…)**: openings average 0.57-0.62 confidence. The AI reader
  gives no door leaves, so every door scores 0.65 × 0.85. Doors and windows on these plans are the first thing to
  check on the review page.
- To measure these plans properly, save a corrected plan with the dev "Save as reference" button and run
  `tools/score_plan.py`.
