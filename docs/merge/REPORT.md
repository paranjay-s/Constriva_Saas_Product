# Merge report: feat/run3 + origin/feature/new-ui-landing -> feat/merged

Done on 2026-11-20. Branch `feat/merged` (from `feat/run3`, with `origin/feature/new-ui-landing` merged in).
Nothing pushed; `main` untouched. The plan written before merging is `PLAN.md`; every changed file by area is
`files_by_area.md`.

## Result in one paragraph

All four features work in his UI, end to end, in a real browser session (sign-up through your Supabase, then the
2D generator, material finder, BOQ and 3D, each with screenshots). His landing page, sign-in page, dashboard, chat
studio and navigation are taken whole. BOQ and 3D are in his header ("2D to 3D", "BOQ"), on his dashboard as tiles
beside his two studios, and 3D houses are listed in each project card the way his 2D plans are. The BOQ and 3D pages
are restyled in his palette and type without behaviour changes (all their tests pass unchanged). He changed no
backend code, so every backend file is ours. One auth gap in the frontend (an automatic demo user) was closed to
match our rule.

## What each side brought

- **His (2 commits):** a new dashboard (`features/dashboard`), a full-screen chat studio (`features/studio`) that
  now hosts the 2D generator and the material finder, a project flow, a new sign-in page and home page, re-encoded
  landing tour frames. Code: 53 files, all frontend, plus one backend test.
- **Ours (155 commits since the merge base):** BOQ and 3D (backend and frontend), auth hardening, the AI client
  layer, three migrations, PlanTo3D. The old in-browser 3D viewer, plan editor and import page had already been
  removed, with nine npm packages.

## Conflicting files: which side won, and why

| File | Won | Why |
|---|---|---|
| `backend/tests/material_agent/test_mat_guards.py` | ours | Both made the same fix (7 routes); ours names each route instead of counting them. |
| `frontend/src/app/router.tsx` | combined | His studio routes (2D generator and material finder full screen, still behind `ProtectedRoute`); our `/3d`, `/3d/furniture`, `/3d/:jobId`, `/boq` and the redirects of `/projects/import` and `/projects/3d-workspace` to `/3d`. |
| `frontend/src/app.test.tsx` | combined | Ours for the import and workspace pages (they no longer exist), the rest merged. |
| `frontend/src/components/ui/Navbar.tsx` | his (deleted) | His `DashHeader` replaces it; our one change (the "2D to 3D" link) moved into `DashHeader`. |
| `frontend/src/features/home/HomePage.tsx` | his | His dashboard, with our links (`/3d`) and then BOQ and 3D added (below). |
| `frontend/src/features/floorplan/FloorplanPage.tsx` | his | His studio page, with our "Open in 3D" behaviour (below). |
| `frontend/src/features/projects/ProjectOptionsPage.tsx` | his | His redesign, with our link to `/3d`. |
| `frontend/src/features/plan-viewer/PlanViewer.tsx` | ours (deleted) | It needs `three` and `@react-three/*`, which we removed; the 3D builder replaces it. |
| `frontend/src/features/plan-viewer/WorkspacePage.tsx` | ours (deleted) | Its two jobs (the 3D model, the material sheet) are now the 3D pages and the BOQ page. |

## Changed or dropped from his branch

1. `PlanViewer.tsx` and `WorkspacePage.tsx` (his restyle of the old 3D workspace) are not in the merge, nor the
   route to `ImportPlanPage` (we had deleted that page).
2. His **"Open in 3D"** stored the plan in the old viewer's cache and opened `/projects/3d-workspace`. It now hands
   the stored plan to the 3D builder (`plan3dApi.fromFloorplan`) and opens its job, as ours did; his button, icon and
   error style (a note in the thread) are kept.
3. Links to the removed pages, in his dashboard, project flow and options page, now point at `/3d` ("Open 2D to 3D").
   `DashHeader`'s "3D workspace" and "Import plan" entries became "2D to 3D" and "BOQ".
4. **7 tests of his** dashboard suite ("3D workspace": bill of materials, filters, recalculate, stale, missing plan,
   no project) are removed with the page they test, and their `SHEET` fixture. The BOQ page has its own tests.
5. His **"Instant architect demo access"** button is hidden, and a first visit is no longer signed in automatically
   as "Demo Architect", unless `VITE_ALLOW_DEMO_USER=true` (see Auth below).
6. Landing: the three feature chips (`Plan to 3D`, `BOQ sheets`, `Material AI`) linked to `#`; they now open
   `/3d`, `/boq` and `/materials/analyse`. The two BOQ chapter buttons pointed at the project options page; they open
   `/boq`. His wording is unchanged.
7. His backend test change (route count) is replaced by ours (same fix).

Kept from his branch as is: everything else, including the re-encoded landing tour frames (28.0 MB -> 38.7 MB: the
landing page is about 10.7 MB heavier).

## Changed or dropped from ours

1. `frontend/package-lock.json` removed (`git rm`). It was tracked (added in our `694a201`, "3-d edit"), not
   untracked as the brief said. pnpm is the project's manager (`AGENTS.md`; `pnpm-lock.yaml` is current).
2. The shared `Button`, `Card` and `Input` (`components/ui`) now look like his dashboard (pills, the cyan gradient,
   rounded cards, his inputs). The loan page and the legacy generator use them too, so they changed look as well.
   `Button`'s small size grew from 32 to 36 px.
3. Our old gold-and-grey palette in `features/sheets` and `features/plan3d` is mapped to his tokens; their page
   titles use his light display type; square corners became his rounded ones. Class names only.
4. `floorplan/index.ts` re-exports `isSavedProject` from his `studio/ProjectMenu` (he moved it there).
5. The backend guard `test_no_sample_content` now also scans his `features/studio` (it now holds the 2D generator's
   brief form and edit chat). That raised the backend test count from 1145 to 1161.
6. PlanTo3D's library admin page (`web/library.html`) takes his palette.

Not changed: the BOQ calculations, the 3D pipeline, the plan parser, PlanJSON and the API contracts. No backend code
changed in the merge.

## Auth

Our backend rules stand (401 without a token, the demo user only behind `AUTH_ALLOW_DEMO_USER`, ownership checks,
signed embed and share tokens); he changed none of them (his `ProtectedRoute` change is colours only).

One frontend change, to fit his pages to those rules: since the first frontend commit (2026-11-10, before both
branches), `AuthContext` signed every first visit in as a "Demo Architect" with no token, so the protected pages
opened and then failed with 401s, and the sign-in page offered demo access. Now that only happens with
`VITE_ALLOW_DEMO_USER=true` (pair it with the API's `AUTH_ALLOW_DEMO_USER`). Without it, a signed-out visit to any
feature goes to sign in (tested in the browser and in `app.test.tsx`).

## .env.example

He did not change it. Two frontend lines added: `VITE_API_BASE_URL` (the name the code actually reads; the file
listed `VITE_API_URL`, which nothing reads, kept as asked) and `VITE_ALLOW_DEMO_USER=false`. `.env` not touched.

## Dependencies

None added or reinstated. His code uses none of the removed packages except in `PlanViewer.tsx`, which stays deleted.

## SQL to run in Supabase, in order

The full, paste-ready file is `docs/merge/supabase.sql` (generated offline with `alembic upgrade head --sql`;
nothing was applied). Only our branch added migrations: one chain, one head (`20261119_0002`), no merge revision.

**First check:** if you already created `plan3d_jobs` from `docs/08-3d.md`, skip step 1 and only record it:
`CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY);
INSERT INTO alembic_version (version_num) VALUES ('20261118_0001');`

1. `20261118_0001` plan3d_jobs: the table (id, user_id, project_id -> projects, name, source, quality, created_at,
   updated_at, with checks), two indexes, row-level security and the owner-read policy.
2. `20261119_0001` asset_library: the table for the 3D library (kind, room types, fits, models, review status,
   cost), two indexes.
3. `20261119_0002` `ALTER TABLE plan3d_jobs ADD COLUMN share_id TEXT` and its check (share links).

Until step 1 is applied, the API needs `PLAN3D_STORE=memory` for 3D jobs (jobs are then forgotten when the API
restarts); with the default `supabase` store, 3D uploads fail.

## Tests

| Suite | Result |
|---|---|
| Backend (`TESTING=1 pytest`) | 1142 passed, 3 skipped (before the guard extension); the guard alone after it: 116 passed. The 4 fewer than on feat/run3 were the guard's checks of his 4 deleted components (shown by comparing the collected tests). |
| Frontend (`vitest run`) | 294 passed (21 files): ours 257 + his dashboard and studio tests + new merge tests, minus his 7 workspace tests |
| Type check (`tsc -b`) | clean |
| Frontend lint (oxlint) | no errors; warnings only, in his studio and dashboard files and two older files (not changed) |
| Frontend build (`vite build`) | ok |
| Backend lint (ruff) | the files changed in the merge are clean (the repository's older findings remain) |
| PlanTo3D (`tests/run_all.sh`) | every Python test passes; 2 Node failures from before the merge: `test_openings` on job `0bdaca14d7bf` (a door onto a wall 0.84 ft behind it; the verifier marks it critical) and `test_tour` on `cb07bf88a61e` (reported, not required) |

New tests from the merge: the dashboard's BOQ and 3D tiles and each project's 3D houses; a signed-out visit to each
of 7 feature routes goes to sign in; the 3D route tests sign in with a token.

### Browser test (headless Chrome, three services on test ports, real sign-up)

API on 8010 (no demo access, `PLAN3D_STORE=memory`), PlanTo3D on 8081 (developer mode), frontend on 5181. Your own
servers (8000, 5173, 8080) were left alone and no build of yours was running. All passed:

- Landing page (desktop, phone); sign-in page; **sign up** (`POST /auth/signup` 201, lands on the dashboard);
  **sign out** (the session is gone: `/home` goes to sign in); **sign in** again; the dashboard; keyboard: Tab reaches
  every header link, then the four tiles.
- **Signed out**, `/home`, `/projects/ai-generator`, `/materials/analyse`, `/boq`, `/3d`, `/3d/<job>` and
  `/projects/new` all go to sign in.
- **2D generator:** new project, a brief (2 bedrooms, 30 x 40 ft, east facing), the confirmation card, generate, an
  edit ("living room 2 feet wider": v2, the other rooms adjusted), saved (listed on the dashboard), **Open in 3D**
  (a 3D job opened with the plan ready for review, "nothing was read from the drawing").
- **Material finder:** a facade photo (3 materials, identified only: the quantity engine covers room surfaces, so
  facade and window materials get no quantities; that is how the feature works today) and a dining-room photo with
  its size: materials and quantities (tiles, plaster, paint, adhesive, grout, primer, putty).
- **BOQ:** upload (`sample_plan.pdf`), progress, the table and summary, assumptions (Villa -> Apartment recalculated
  the table), **PDF** (a valid PDF) and **Excel** (a valid two-sheet workbook) downloads.
- **3D:** upload (`docs/reference/plans/paranjay-villa.pdf`), the review page with its checklist, options (Low),
  build progress, built in 2 min 26 s, the walkthrough, a **share link** (opened by a signed-out guest: the
  walkthrough loads, Record / Blender file / Home are hidden; after **Turn link off** the old and new links answer
  410), the furniture models page, the plans list, the library admin page.
- Every page at phone width (390 px).

Screenshots: `docs/merge/screens/` (49 images, 19 MB). They are git-ignored, so they are on this Mac only.

Live AI calls: about 7 of the 10 allowed (2D: parse, generate, edit; material finder: two analyses and one chat;
BOQ: one parse, the second upload came from the cache).

**Left behind by the test (yours to delete):** a Supabase account `merge-test-20261120@example.com` with a project
"Merge test villa", one 2D plan and two image analyses; two PlanTo3D jobs on disk (`8128019fa784`,
`3b0de3ba2940` in `services/planto3d/jobs`).

## Commits on feat/merged

`e887d1c` plan · `1324dc8` the merge (conflicts resolved) · `57b87e6` Supabase SQL · `b77c48d` BOQ and 3D in his UI ·
`6d5cc72` auth: demo user behind a flag · `1f25ca6` guard test scope · this report.

## What does not work, or is yours to decide

1. **Apply the SQL** above (until then run the API with `PLAN3D_STORE=memory`).
2. **BOQ is not in the dashboard's lists:** a BOQ is a one-off job, the API has no list of past BOQs and none is
   kept per project. Showing them would need a new backend endpoint (an API change, so not done). BOQ appears as a
   tile and a header link.
3. **Demo access:** off by default now (`VITE_ALLOW_DEMO_USER`, `AUTH_ALLOW_DEMO_USER`). Turn both on only for demos.
4. **The pages inside iframes** (the review page, the walkthrough, the furniture models) keep PlanTo3D's own look;
   only the frame around them is in his style.
5. **Landing feature chips** list three features (his wording: Plan to 3D, BOQ sheets, Material AI); the 2D
   generator has a tour chapter but no chip. Add a fourth if you want it there.
6. **Heavier landing page** (+10.7 MB of tour frames from his branch).
7. **Lint warnings** in his studio and dashboard files (refs read during render, state set in an effect), left as
   they are.
8. **The PlanTo3D Node failure** on job `0bdaca14d7bf` (from before the merge) needs that plan fixed on its review
   page, or the job deleted.
