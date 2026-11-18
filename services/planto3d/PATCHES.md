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
