# Merge plan: feat/run3 + origin/feature/new-ui-landing -> feat/merged

Written before merging (2026-11-20). The report of what actually happened is `REPORT.md`.

## What each side changed since the merge base

Merge base: `5631f72` (2026-11-18, "Floor plans live in projects; direction and edit tools; material chat history").

- **Ours (feat/run3):** 155 commits, 341 files. Backend: the 3D gateway and PlanTo3D (detector, library, lighting,
  creator agent), BOQ, the AI model clients, auth hardening, three Alembic migrations. Frontend: the 3D pages
  (`features/plan3d`), the BOQ page (`features/sheets`), the old in-browser viewer, plan editor and import page
  removed (54 files) with their nine npm packages.
- **His (origin/feature/new-ui-landing):** 2 commits, 899 files, of which 846 are images (843 landing tour frames
  re-encoded, 28.0 -> 38.7 MB; two hero images; one new dashboard image). Code: 53 files, all frontend except one
  backend test. New: the dashboard (`features/dashboard`), the chat studio shell (`features/studio`) that now hosts
  the 2D generator and the material finder full screen, a project flow, a new auth page, a new home page. Removed:
  `Navbar`, `AuthCinematic`, and six 2D-generator / material-finder components folded into the studio.

Every changed file, sorted by area: `files_by_area.md`.

## Features 1 and 2 (2D generator, material finder): whose backend

He changed **no backend code**: his only backend change is `backend/tests/material_agent/test_mat_guards.py`
(the material route count 6 -> 7). Our copy of both backends is therefore the newer one, with our changes since the
base on top (project ownership checks, the floor-plan-to-3D hand-off, the AI client layer). Decision: **ours for every
backend file of features 1 and 2.** For the test, both sides made the same fix (7 routes); ours names each route
instead of counting them, so ours is kept.

His frontend for both features (the studio) is taken, with our "Open in 3D" hand-off ported into it (below).

## Files expected to conflict, and how each is resolved

| File | Ours | His | Resolution |
|---|---|---|---|
| `backend/tests/material_agent/test_mat_guards.py` | lists the 7 routes | counts 7 routes | **ours** (stricter, same fix) |
| `frontend/src/app/router.tsx` | routes for `/3d`, `/3d/furniture`, `/3d/:jobId`, `/boq`; `/projects/import` and `/projects/3d-workspace` redirect to `/3d` | 2D generator and material finder moved out of the app layout into full-screen studio routes; keeps the import and workspace pages | **combined**: his studio routes and structure; our 3D and BOQ routes and the two redirects (the import and workspace pages no longer exist) |
| `frontend/src/app.test.tsx` | tests for 3D, BOQ, redirects | tests for the studio routes | **combined** |
| `frontend/src/components/ui/Navbar.tsx` | relinked "3D Workspace" to `/3d` | deleted (his dashboard header replaces it) | **his deletion**; our links move into his navigation |
| `frontend/src/features/home/HomePage.tsx` | relinked tiles to `/3d` and `/boq` | new dashboard | **his**, then BOQ and 3D added in his style (step 3) |
| `frontend/src/features/floorplan/FloorplanPage.tsx` | "Open in 3D" sends the stored plan to the 3D builder (`plan3dApi.fromFloorplan`) | studio layout; "Open in 3D" goes to the old workspace | **his**, with our `openIn3D` (3D builder hand-off) |
| `frontend/src/features/projects/ProjectOptionsPage.tsx` | relinked to `/3d` | redesigned | **his**, with our links |
| `frontend/src/features/plan-viewer/PlanViewer.tsx` | deleted | restyled | **deleted** (needs `three` and `@react-three/*`, removed; replaced by the 3D builder) |
| `frontend/src/features/plan-viewer/WorkspacePage.tsx` | deleted | restyled (3D model plus material sheet) | **deleted**; its two jobs are the 3D pages and the BOQ page. His restyle informs the restyle of those pages (step 3) |

Files only one side changed come in unchanged (git merges them cleanly). His router also imports
`features/files/ImportPlanPage`, which we deleted: that import is dropped with the route.

## Other decisions

- **Auth:** ours stays (401 without a token, the demo user only behind its flag, ownership checks, signed embed and
  share tokens). His `AuthPage` and `ProtectedRoute` changes are taken where they only change the look; anything that
  would weaken a check is not.
- **Dependencies:** his code adds none. The only file of his that uses a removed package is `PlanViewer.tsx`, which
  stays deleted. Nothing is reinstated.
- **Lock files:** pnpm is the project's manager (AGENTS.md, `pnpm-lock.yaml`, kept in step with `package.json` in
  `be65441`). `frontend/package-lock.json` is tracked (added in our `694a201`, "3-d edit"), not untracked as the brief
  says; it is removed with `git rm`. pnpm is not installed on this machine, so `node_modules` stays as installed;
  no dependency changes, so the pnpm lock needs no update.
- **Migrations:** only ours added any (`20261118_0001` plan3d_jobs, `20261119_0001` asset_library,
  `20261119_0002` plan3d_jobs.share_id): one chain, one head, no merge revision. The SQL goes in the report.
- **.env.example:** he did not change it; ours is kept as it is (already grouped by feature).
- **Docs:** he changed none; ours are kept, and `docs/merge/` is added.

## Risks

1. **His studio pages and our "Open in 3D".** His FloorplanPage is a rewrite; the hand-off must be re-wired by hand.
   Mitigation: our existing test for the hand-off (`floorplan.test.tsx`) is merged with his and must pass.
2. **Links to pages that no longer exist** (`/projects/3d-workspace`, `/projects/import`) in his new dashboard, studio
   and project flow. Mitigation: keep our redirects; search every `to=`/`navigate(` and point them at `/3d` or `/boq`.
3. **Full-screen studio routes outside the app layout** must still be protected. His routes wrap them in
   `ProtectedRoute`; the browser test checks that an unauthenticated visit goes to sign in.
4. **His larger landing images** (+10.7 MB) make the landing page heavier. Taken as his design; noted.
5. **Restyling BOQ and 3D** could change behaviour. Mitigation: restyle only (class names, wrappers, components);
   their existing tests (BOQ, plan3d: 86 + more) must pass unchanged.
6. **The 3D pages embed PlanTo3D's own pages in iframes** (review, walkthrough, library admin): their inside keeps its
   own style; only the frame around them is restyled.
7. **Live services for the browser test**: Supabase auth may be needed to sign in; if it cannot be reached, the
   local demo flag is used and that is stated.
