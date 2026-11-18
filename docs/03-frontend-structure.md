# 03 Frontend structure

React 19 + Vite + TypeScript. Server state uses TanStack Query, UI state uses zustand. The 3D houses are PlanTo3D's own pages, framed in iframes.

```
frontend/
├── package.json  vite.config.ts  tsconfig.json  index.html
└── src/
    ├── main.tsx
    ├── app/
    ├── lib/
    ├── components/ui/
    ├── types/
    └── features/
```

## Top-level folders in `src/`

| Path | Purpose |
|---|---|
| `main.tsx` | Entry point. Mounts the app. |
| `app/router.tsx` | Route table (dashboard, project, plan viewer, sheets, chat, loan, reports). |
| `app/providers.tsx` | Wraps the app with the query client, Supabase session and theme. |
| `lib/api.ts` | Typed fetch wrapper that attaches the Supabase access token and handles errors. |
| `lib/supabase.ts` | Supabase client, used for sign-in only. All data goes through our API. |
| `lib/sse.ts` | `parseSse`: splits the text of a Server-Sent Events stream into messages. Streams are read with `fetch()` and the session's token, because `EventSource` cannot send an `Authorization` header. |
| `components/ui/` | Shared, feature-independent UI pieces (buttons, dialogs, inputs). |
| `types/plan.ts` | **Generated** from the backend plan schema. Never edit by hand; run `uv run python -m app.modules.plans.export_schema` in `backend/`, then `pnpm gen:types` in `frontend/`. |

## `features/`

Each feature is a self-contained folder:

```
features/<name>/
├── components/   React components for this feature
├── hooks/        data hooks (TanStack Query) and local logic
├── api.ts        calls to the backend for this feature
└── index.ts      the only file other features may import from
```

| Feature | Purpose |
|---|---|
| `auth` | Sign in, sign up, session handling. |
| `projects` | Project list and project dashboard. |
| `files` | The plan upload checks every upload screen shares: the size and page limits from the API and the client-side PDF check. |
| `plan3d` | The 2D-to-3D flow (`/3d`): upload, detection, review, options, build progress, walkthrough, downloads and the furniture models page. See below and [08-3d.md](08-3d.md). |
| `sheets` | The BOQ page (`/boq`): upload a plan PDF, follow progress, then an interactive material table with search, filters, grouping and PDF / Excel export. Also the earlier per-project sheet API client. See [07-boq.md](07-boq.md). |
| `chat` | Chat panel; sends messages and applies returned edit operations. |
| `loan` | Loan document upload and results (pending design). |
| `reports` | Report generation and download. |

## `plan3d`

The pages do not draw 3D themselves. They call the gateway (`/api/v1/3d`) and frame PlanTo3D's own pages:

| Step | What our page shows |
|---|---|
| Upload | PDF drop zone with the shared limits, "Try the sample plan", and the user's jobs |
| Detect | Progress while PlanTo3D reads the drawing |
| Review | PlanTo3D's review page in an iframe (fix walls, doors, windows, rooms, scale) |
| Options | Furniture on or off, and the quality: Low, Medium, High |
| Build | Stage, percent, time left, queue position |
| Walkthrough | PlanTo3D's walkthrough in an iframe, the Blender file download, the furniture models page, delete |

An iframe cannot send the session's Bearer token, so its URL comes from `POST /api/v1/3d/jobs/{id}/embed` and carries a short-lived signed token. Our page and the review page talk with `postMessage`: we ask it to save the reviewed plan, then start the build ourselves.

The earlier in-browser viewer (`viewer3d`, `plan-viewer`, `plan-editor`) was removed.
