# 01 Repository layout

The repository is a monorepo with three code areas (`backend`, `frontend`, `shared`) plus supporting files.

```
.                    repository root
├── AGENTS.md            instructions for coding agents
├── README.md            quick start and the commands to run everything
├── docker-compose.yml   local services: redis, minio, test-db, api, worker
├── .env.example         every config key the project reads (no real values)
├── docs/                this documentation
├── backend/             FastAPI app, Celery workers, migrations, tests
├── frontend/            React app and the 3D viewer
└── shared/plan-schema/  JSON Schema of the plan, shared by both sides
```

## Root files

| File | Purpose |
|---|---|
| `AGENTS.md` | Setup steps, architecture rules and boundaries for AI coding agents. Humans can read it as a short architecture brief. |
| `docker-compose.yml` | Starts Redis (queue and pub/sub), MinIO (an S3-compatible store for local development), a test Postgres on port 5433, and optionally the API and worker containers. Production Postgres is Supabase, not this file. |
| `.env.example` | The list of environment variables. Copy it to `.env` and fill in values. Add every new key here. |

## `shared/plan-schema/`

`plan.schema.json` describes the plan JSON (walls, openings, rooms, scale, confidence). It is **generated** from the Pydantic model in `backend/app/modules/plans/schemas.py` by `uv run python -m app.modules.plans.export_schema` (run in `backend/`). Then `pnpm gen:types` (run in `frontend/`) writes `frontend/src/types/plan.ts` from it. This keeps the backend and frontend from drifting apart. Do not edit generated files by hand.

## Commands

The commands to run the frontend, backend, worker and Docker services are in the root `README.md`. There are no shell scripts or Makefile; every command is a plain `uv`, `pnpm` or `docker compose` command.

## Why this shape

1. **One plan format.** Everything (parser, editor, 3D viewer, material sheets) depends on the plan JSON, so it lives in one place and is shared.
2. **Modules by feature.** Both backend and frontend are organised by feature (projects, plans, parsing, sheets...), not by technical layer, so a feature's code stays together.
3. **Heavy work is isolated.** Anything slow runs in Celery workers, which are built from the same backend code but run as a separate process.

