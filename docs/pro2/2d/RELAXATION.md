# Relaxation ladder: results (A1, task 8)

Measured on the Apple M1 Pro, 2026-11-20, with the default settings (no setbacks, 8 s per solver run),
no AI (typical room sizes), `tools/floorplan_cases/random_briefs.py 50 ... --seed 7`. Raw rows:
`random_briefs.json`.

Briefs: 1-12 rooms (counting a bedroom group as one entry; up to 5 bedrooms), plots of 1,000-15,000 sq ft (half
with a stated width and depth, half area-only), half with a stated built-up area of 40-95 % of the plot, a
random road side, and 0-4 random wishes (front / rear / left / right / centre, rooms touching, doors), some of
which contradict each other.

## Result

**50 of 50 briefs got a plan**; all 50 pass the validator (the two corridor-fallback plans pass only
because their remaining problems are turned into notes, see below).

| Where the plan came from | Briefs | Share |
|---|---|---|
| First pass (every wish as asked) | 42 | 84 % |
| Weighted wishes (some wishes given up) | 5 | 10 % |
| a. aspect and daylight dropped | 0 | 0 % |
| b. low-weight adjacencies and sides dropped | 1 | 2 % |
| c. rooms shrunk | 0 | 0 % |
| d. other plot proportions | 0 | 0 % |
| e. below the standard minimums | 0 | 0 % |
| f. corridor layout (last resort) | 2 | 4 % |

Time per brief: median 6.0 s, longest 14.1 s.

The two fallback briefs are physically too small: 5 bedrooms with attached baths, a majlis, living, kitchen,
utility, puja and courtyard on 1,200 sq ft, and 5 bedrooms with attached baths on 1,094 sq ft. Every solver
rung proves them infeasible in under 0.1 s (rung e times out at 6 s), so the corridor layout delivers them
with the rooms shrunk (49 % and 20 %) and the problems that remain listed in the chat ("Still to check on
this plan: MIN_AREA ..."). These are honest drafts to start a conversation, not finished plans.

Plain-word adjustments seen in this run, for example:
- "The living could not go at the rear; it is at the front instead."
- "The foyer could not open onto the master bed room; it is next to the kitchen instead."
- "The bed room could not go in the centre; it is at the front instead."

Every reply ends with: "Ask me to bring any of these back (for example “make the pool touch the garden”) and I
will re-plan with it."

## The owner's three briefs

| Brief | feat/pro | feat/pro_2 |
|---|---|---|
| 1 (6,000 sq ft plot, 5,000 built-up, 13 wishes) | refused after 44.5 s | plan in the first pass, every wish kept (51 s with the AI's room sizes; 12-28 s replayed) |
| 2 (7,000 sq ft plot, 5,000 built-up) | refused after 81.7 s | plan in the first pass (17 s) |
| 4,500 sq ft, 2 bedrooms (worked) | plan | same program, plot and solver calls as feat/pro under feat/pro's setbacks (golden test); with the new default of no setbacks the plot it lays out is larger, so the plan differs |

What fixed briefs 1 and 2: the stated built-up area is used as stated (A1.2), no setbacks by default
(A1.3), and rules now name the right room ("front yard lawn" vs "backyard garden", the common bath rather
than the master's attached bath; A1.7). Before those fixes the ladder alone already delivered both: brief 1
at rung a (12 s, 13 wishes reported as given up), brief 2 at the weighted rung (6 s, 1 wish given up).
