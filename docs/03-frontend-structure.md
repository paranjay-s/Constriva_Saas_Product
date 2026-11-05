# 03 Frontend structure

React 19 + Vite + TypeScript. Server state uses TanStack Query, UI state uses zustand, 3D uses React Three Fiber.

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
| `lib/sse.ts` | Small client that subscribes to job progress events. |
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
| `files` | Upload flow: ask the API for a presigned URL, upload straight to S3, then start parsing. |
| `plan-viewer` | The 3D viewer (see below). |
| `plan-editor` | 2D editing on top of the original PDF. |
| `sheets` | Material sheet table with editable rows and export buttons. |
| `chat` | Chat panel; sends messages and applies returned edit operations. |
| `loan` | Loan document upload and results (pending design). |
| `reports` | Report generation and download. |

## `plan-viewer`

```
plan-viewer/
├── PlanViewer.tsx     canvas, lights, orbit controls, camera presets (top, front, isometric)
├── builders/          pure functions: plan JSON in, Three.js geometry out
│   ├── buildWalls.ts      merges wall footprints, extrudes, cuts openings
│   ├── buildFloors.ts     room polygons to floor meshes
│   └── buildOpenings.ts   door and window frames
└── controls/          view toggles (hide roof, hide walls), wall-height input
```

Rule: **the scene is a pure function of the plan JSON.** When the plan changes, the viewer rebuilds geometry. No server round trip is needed for an edit, and no mesh is stored.

## `plan-editor`

```
plan-editor/
├── PlanEditor.tsx     PDF page as an underlay with the detected plan drawn over it (react-konva)
└── tools/             drag wall endpoints, add or remove openings, set scale by two clicks
```

Low-confidence elements from the plan JSON are highlighted so the user knows what to verify first. Every edit creates a new plan version through the API.

