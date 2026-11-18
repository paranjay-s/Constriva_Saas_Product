# 02 Backend structure

The backend is a modular monolith: one FastAPI application, split into feature modules, plus Celery workers that share the same code.

```
backend/
├── pyproject.toml        dependencies and tool config (uv, ruff, pytest)
├── alembic.ini           Alembic config
├── Dockerfile            image used by both the api and worker services
├── migrations/           database migrations (Alembic)
├── app/
│   ├── main.py
│   ├── core/
│   ├── events/
│   ├── workers/
│   └── modules/
└── tests/
```

## `app/main.py`

Creates the FastAPI app, configures CORS (using `FRONTEND_ORIGIN`), mounts each module's router under `/api/v1/<module>`, mounts the SSE endpoint, and exposes `GET /health`.

## `app/core/`

Cross-cutting infrastructure. Nothing here knows about floor plans.

| File | Purpose |
|---|---|
| `config.py` | Reads environment variables into one typed settings object. |
| `security.py` | Verifies the Supabase JWT and provides the `get_current_user` dependency. A request with no token gets `401`; see "Authentication" below. Passwords are never handled here. |
| `db.py` | Async SQLAlchemy engine, session dependency and the declarative `Base` that every module's models inherit from. |
| `redis.py` | Shared Redis connection (used by Celery, pub/sub and rate limits). |
| `storage.py` | S3 helper: create presigned upload and download URLs, read and write objects. Works with MinIO locally. |
| `logging.py` | `setup_logging()`: sends the app's own loggers (`construtiva.*`) to stderr at `LOG_LEVEL` (default INFO) when the API server starts. uvicorn configures only its own loggers, so without it the app's INFO lines, such as the one line per plan parse, would not be printed. |

### Authentication

Every endpoint except `/health`, `/health/deep`, the module `/ping` probes and the sign-in endpoints (`/auth/login`, `/auth/signup`, `/auth/refresh`) uses one dependency, `get_current_user`:

- A valid Supabase access token in `Authorization: Bearer ...` identifies the user.
- No token, or an expired or invalid one, gets `401`. There is no shared or fallback user.
- Endpoints that return a user's data also check that it is theirs, and answer someone else's data with the same `404` as data that does not exist. A parsing job belongs to the user who started it; a plan belongs to the owner of its project (`projects/service.user_owns_project`).

Browsers cannot attach the header to an `EventSource` or an `<img>` tag, so the frontend reads progress streams and protected images with `fetch()`.

**Demo access** is off by default. With `AUTH_ALLOW_DEMO_USER=true`, a request with no token acts as one dedicated demo profile, whose UUID is given in `AUTH_DEMO_USER_ID`. The server refuses to start when the flag is on and that UUID is missing. The code creates no account and holds no password; an operator creates the demo profile. Do not turn it on for a deployment with real customer data.

`tests/unit/test_auth.py` checks that every protected operation in the OpenAPI document refuses a request without a token, and `tests/unit/test_endpoint_ownership.py` pins the list of open endpoints and the ownership checks.

## `app/modules/`

One folder per feature. Every module uses the same file names, so you always know where to look.

| File | Purpose |
|---|---|
| `router.py` | HTTP endpoints. Thin: validate input, call the service, return the response. |
| `service.py` | Business logic. This is the only file other modules may import from. |
| `models.py` | SQLAlchemy tables owned by this module. |
| `schemas.py` | Pydantic request and response models. |

### The modules

| Module | Responsibility |
|---|---|
| `projects` | A user has many projects. Create, list, archive. |
| `files` | Issues presigned S3 URLs, records uploaded files (`kind`, `storage_key`, `mime_type`, `size`). |
| `plans` | Owns the plan JSON model (`PlanJSON`, schema 2.0, see [plan-json.md](plan-json.md)). Its router serves the PNG drawing stored with a generated plan. `room_kind.py` holds the room `kind` rules shared by the parser and the material calculator. `export_schema.py` writes the JSON Schema of `PlanJSON` for the frontend types. |
| `parsing` | The plan parser (PDF to PlanJSON) and the shared plan upload check. See [04-parsing-module.md](04-parsing-module.md). |
| `plan3d` | The gateway to the private PlanTo3D service, mounted at `/api/v1/3d`: sign-in, job ownership, quality names, and signed tokens for embedded pages. See [08-3d.md](08-3d.md). |
| `sheets` | Computes material quantities from a plan version and exports them. Marks sheets stale when the plan changes. See [07-boq.md](07-boq.md) for the BOQ flow (`llm_mapper.py`, `primitives.py`, `formulas.py`, `constants.py`, `boq_*.py`) and [materials_formula_spec.md](materials_formula_spec.md) for the formulas. |
| `materials` | Material catalogue and prices (prices have history, so old reports stay correct). |
| `ai` | Chat, conversations and messages. `chat.py` turns a request into structured edit operations; `edit_ops.py` defines them; `material_agent/` is the Material Finder (photo -> identified materials, quantities computed in Python from the person's own space; no money anywhere, see `docs/material-agent/PLAN.md`); `llm_client.py` is the provider-neutral LLM wrapper; `prompts/` holds prompt files. |
| `loan` | Placeholder for the bank-loan document extraction (design pending). |
| `jobs` | Reads job status (queued, running, done, failed, progress) for the UI. |

### Dependency rule

A module may import another module's `service.py`. It must not import another module's `models.py` or `router.py`. This keeps modules replaceable and avoids circular imports.

## `app/events/`

| File | Purpose |
|---|---|
| `pubsub.py` | Publish and subscribe helpers on Redis channels, one channel per job or project. |
| `sse.py` | The SSE endpoint. Subscribes to the right channel and forwards events to the browser. |

## `app/workers/`

Celery application and tasks. See [06-workers-and-realtime.md](06-workers-and-realtime.md).

## `migrations/`

Alembic is the single owner of the database schema. `env.py` imports every module's `models.py` so autogenerate sees all tables. Row-level security policies are written as raw SQL inside migrations.

## `tests/`

| Folder | Contents |
|---|---|
| `fixtures/pdfs/` | Sample plan PDFs from the firm, used to test extraction (keep real client files out of public repos). |
| `fixtures/plans/` | Hand-checked expected plan JSON for those PDFs. |
| `unit/` | Pure-logic tests: geometry, units parser, calculator. |
| `integration/` | API tests against the test database, with S3 mocked (`moto`). |

