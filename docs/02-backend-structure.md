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
| `security.py` | Verifies the Supabase JWT and provides the `current_user` dependency. Passwords are never handled here. |
| `db.py` | Async SQLAlchemy engine, session dependency and the declarative `Base` that every module's models inherit from. |
| `redis.py` | Shared Redis connection (used by Celery, pub/sub and rate limits). |
| `storage.py` | S3 helper: create presigned upload and download URLs, read and write objects. Works with MinIO locally. |
| `logging.py` | Structured logging setup. |

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
| `plans` | Stores plans and their versions. Owns the plan JSON model (`PlanJSON`) and applies edit operations (add wall, resize room, add door) to produce a new version. `export_schema.py` writes the JSON Schema of `PlanJSON` for the frontend types. |
| `parsing` | Turns an uploaded PDF into a plan JSON. See [04-parsing-module.md](04-parsing-module.md). |
| `sheets` | Computes material quantities from a plan version (`calculator.py`) and exports them (`export.py`: PDF report, xlsx). Marks sheets stale when the plan changes. |
| `materials` | Material catalogue and prices (prices have history, so old reports stay correct). |
| `ai` | Chat, conversations and messages. `chat.py` turns a request into structured edit operations; `edit_ops.py` defines them; `material_vision.py` estimates materials from a photo; `llm_client.py` is the provider-neutral LLM wrapper; `prompts/` holds prompt files. |
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

