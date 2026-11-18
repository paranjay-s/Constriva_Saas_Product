# Patches to the vendored PlanTo3D

This folder is a `git subtree` of https://github.com/23f2005639/planTo3D (branch `main`).
Every change made here, and not yet upstream, is listed below so it can be re-checked after a pull:

    git subtree pull --prefix=services/planto3d https://github.com/23f2005639/planTo3D.git main --squash

Vendored from upstream commit `5456ab8`. Upstream has no licence file.

## 1. Page URLs are relative (web/edit.html, edit.js, view.html, view.js, furniture.html)

Why: the pages are served behind our backend at `/api/v1/3d/embed/<token>/web/...`. Their requests used
root paths (`/api/...`, `/jobs/...`, `/three/...`, `/thumbs/...`, `/web/...`), which would leave that prefix
and lose the token.

What: every such path is now relative to the page (`../api/...`, `../jobs/...`, `../three/...`,
`../thumbs/...`, `style.css`, `edit.js`, `./walk.js`, `view.html?job=...`), including the import map in
`view.html` and the Draco decoder path. `view.js` prefixes the export URL the server returns (`/jobs/...`)
with `..`. The Home links point to `../`.

Standalone use is unchanged: from `/web/edit.html`, `../api/x` is `/api/x`. `web/index.html` is served at
`/` and is not embedded, so it is untouched.

## 2. Review page embed mode (web/edit.html, web/edit.js)

Why: in our product the options (furniture, quality) and the build progress belong to the page that frames
the review page, so the review page must not show a second set of build controls.

What: with `?embed` and a parent window, the body gets class `embed`, which hides the Home link, the
quality list, the Build button, the Furnish checkbox and the build box. The page posts
`{source: 'planto3d', job, type: 'ready' | 'failed' | 'saved', ...}` to its parent, and saves the plan when
the parent posts `{source: 'planto3d-host', type: 'save', furnish: true | false}` (only messages from the
framing window are accepted). Without `?embed` nothing changes.

## 3. Live queue position (server.py)

Why: our build screen shows where a job is in the queue. Upstream writes "N ahead" once, when the job is
queued, and it never changes.

What: `waiting` lists the queued job ids in order. `GET /api/jobs/{id}` adds `queue_position` (1 = next)
while the job's stage is `queued`.

## 4. The browser test finds itself in a folder with a space (tests/test_site.mjs)

Why: the test uploads its own source file as the "not a PDF" case and took its path from
`new URL(import.meta.url).pathname`, which keeps `%20` for a space. In a checkout such as
`.../constriva saas/...` the browser was handed a file that does not exist and the first
assertion failed with "Failed to fetch".

What: the path now comes from `fileURLToPath(import.meta.url)`.

## 5. Headless WebGL backend follows the platform (tests/test_site.mjs, tools/record.mjs)

Why: both start Chromium with `--use-angle=gl-egl`, which exists on Linux only. On macOS
WebGL then never starts, the walkthrough stays on "Loading…" and the test fails at the
recording step.

What: the backend is `gl-egl` on Linux and `metal` on macOS, or whatever `ANGLE` is set to.

## 6. A plan whose build failed can be opened for review again (web/edit.js)

Why: a freshly loaded review page treated every failed job as a failed detection and never
loaded the plan. After a failed build, or a build interrupted by a server restart (whose
message is "press Build again"), the plan could not be opened to build it again.

What: the page stops with the failure message only when the job has no detected floors
(`status.floors` is set when detection succeeds and is kept afterwards). Otherwise it loads
the plan as usual.
