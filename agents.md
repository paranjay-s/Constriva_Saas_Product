# AGENTS.md

Instructions for coding agents working in this repository. Read this file fully before doing anything. It is self-contained: every file you need to create is either listed with its exact content below or in the appendices at the end.

## 1. What this project is

A web platform for an architectural firm. A user uploads a 2D floor-plan PDF and sees an interactive 3D model in the browser, verifies and edits it, and gets a raw-material sheet and a downloadable report. Other features: create a plan from scratch (drag and drop plus a chatbot), estimate materials from a photo, and extract data from a 15-page bank-loan PDF.

Stack: React + Vite + TypeScript (frontend), FastAPI + Celery + Redis (backend), Supabase Postgres (data and auth), Amazon S3 (files), Three.js via React Three Fiber (3D viewer).

## 2. Your task: scaffold only

Work through section 6 in order. In total you will:

1. Create the repository structure in section 5.
2. Install all dependencies.
3. Create every file listed in section 6 with the exact content given, and minimal stubs for everything else (a one-line docstring or comment saying `TODO`).
4. Create the `docs/` folder from Appendix A.
5. Make every check in section 8 pass.

Do **not** implement feature logic (extraction, geometry, 3D building, calculations, chat), and do **not** create database tables or models yet. Feature work and the schema migration come later with their own instructions.

## 3. Architecture rules (these must hold for all future code)

1. **Plan JSON is the single source of truth.** Walls, openings, rooms, scale and confidence live in a versioned JSON document (`plan_versions.plan_json`). The 3D scene, editor, material sheets and reports are all derived from it.
2. **The LLM never produces geometry.** Vision/LLM calls are for meaning only (which page is the plan, room names, scale text, sanity checks). Coordinates come from deterministic extractors.
3. **No hard-coded extraction.** Extractors are plugins that implement one interface (`extractors/base.py`) and all output the same plan JSON. CAD layer names may be used as an optional feature, never as a required rule.
4. **3D is built in the browser** from the plan JSON. The backend never generates meshes.
5. **Heavy work runs in Celery**, never in a request handler: PDF parsing, segmentation, report generation, loan extraction.
6. **Progress reaches the UI through SSE.** Workers publish to Redis pub/sub, and the FastAPI SSE endpoint forwards the events.
7. **Uploads use presigned S3 URLs.** Files do not stream through FastAPI. Store the S3 key, not a URL.
8. **Auth is Supabase Auth.** The frontend signs in with Supabase, and FastAPI verifies the JWT. Never store passwords in our tables.
9. **Alembic owns the database schema.** Do not use `create_all` and do not edit tables by hand.
10. **Sheets are computed from a specific plan version** and are marked stale when the plan changes.
11. **Module boundaries:** a module may call another module's `service.py`, never its `models.py` or `router.py`.

## 4. Prerequisites

Check these first and report any that are missing. Do not install system-level software without asking.

- Node.js 20+ and pnpm 9+
- Python 3.12 and `uv`
- Docker with Docker Compose v2
- git

## 5. Repository layout

```
.                                  # repository root (the cloned repo)
├── AGENTS.md
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── docs/                          # created from Appendix A
├── backend/
│   ├── pyproject.toml  uv.lock  alembic.ini  Dockerfile
│   ├── migrations/{env.py,versions/}
│   ├── app/
│   │   ├── main.py
│   │   ├── core/{config,security,db,redis,storage,logging}.py
│   │   ├── events/{pubsub,sse}.py
│   │   ├── workers/
│   │   │   ├── celery_app.py
│   │   │   └── tasks/{parse_plan,build_report,extract_loan}.py
│   │   └── modules/
│   │       ├── projects/  files/  plans/  sheets/  materials/  ai/  loan/  jobs/
│   │       │     (each: __init__.py router.py service.py models.py schemas.py)
│   │       ├── parsing/
│   │       │   ├── __init__.py router.py service.py schemas.py
│   │       │   ├── pdf_inspect.py scale.py units.py validate.py pipeline.py
│   │       │   ├── extractors/{__init__,base,vector,raster,semantics}.py
│   │       │   └── geometry/{__init__,snap,walls,rooms,openings}.py
│   │       ├── sheets/ also has calculator.py and export.py
│       ├── plans/ also has export_schema.py
│   │       └── ai/ also has chat.py edit_ops.py material_vision.py llm_client.py prompts/
│   └── tests/{fixtures/{pdfs,plans},unit,integration}/
├── frontend/
│   ├── package.json  vite.config.ts  tsconfig.json  index.html
│   └── src/
│       ├── main.tsx
│       ├── app/{router.tsx,providers.tsx}
│       ├── lib/{api.ts,supabase.ts,sse.ts}
│       ├── components/ui/
│       ├── types/plan.ts                # generated, do not edit by hand
│       └── features/
│           ├── auth/ projects/ files/ sheets/ chat/ loan/ reports/
│           ├── plan-viewer/{PlanViewer.tsx,builders/,controls/}
│           └── plan-editor/{PlanEditor.tsx,tools/}
└── shared/plan-schema/{plan.schema.json,README.md}
```

Each frontend feature folder contains `components/`, `hooks/`, `api.ts`, and `index.ts` (its public exports).

## 6. Setup steps

Run from the repository root unless a step says otherwise. Stop and report if a command fails; do not work around it silently. When a step says "create a file with this content", write it exactly, overwriting any stub made earlier.

### 6.1 Prepare the repository

The repository is already cloned and empty. Work inside it. Do not run `git init` and do not create a wrapper folder. All paths in this file are relative to the repository root; the tree in section 5 shows the root as `.`, which is the current directory.

```bash
git status                       # confirm you are inside the cloned repo
mkdir -p docs shared/plan-schema
```

### 6.2 Backend: dependencies and scaffold

```bash
mkdir -p backend && cd backend
uv init --bare --name archplan-api --python 3.12

uv add fastapi "uvicorn[standard]" pydantic pydantic-settings \
       "sqlalchemy[asyncio]" asyncpg alembic \
       "celery[redis]" redis boto3 pyjwt httpx sse-starlette python-multipart \
       pymupdf shapely numpy opencv-python-headless scikit-image pillow \
       reportlab openpyxl

uv add --dev pytest pytest-asyncio pytest-cov "moto[s3]" ruff mypy

uv add --optional ml onnxruntime     # segmentation models, installed only when needed

uv run alembic init -t async migrations
```

Now create the folders and stubs. Run this from `backend/`:

```bash
stub() { mkdir -p "$(dirname "$1")"; printf '"""%s - TODO."""\n' "$1" > "$1"; }

touch app/__init__.py app/modules/__init__.py 2>/dev/null || { mkdir -p app/modules; touch app/__init__.py app/modules/__init__.py; }

for f in __init__ config security db redis storage logging; do stub app/core/$f.py; done
for f in __init__ pubsub sse; do stub app/events/$f.py; done
for f in __init__ celery_app; do stub app/workers/$f.py; done
for f in __init__ parse_plan build_report extract_loan; do stub app/workers/tasks/$f.py; done

for m in projects files plans parsing sheets materials ai loan jobs; do
  for f in __init__ service models schemas; do stub app/modules/$m/$f.py; done
  cat > app/modules/$m/router.py <<PY
from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def ping() -> dict[str, str]:
    return {"module": "$m", "status": "ok"}
PY
done

for f in pdf_inspect scale units validate pipeline; do stub app/modules/parsing/$f.py; done
for f in __init__ base vector raster semantics; do stub app/modules/parsing/extractors/$f.py; done
for f in __init__ snap walls rooms openings; do stub app/modules/parsing/geometry/$f.py; done
for f in calculator export; do stub app/modules/sheets/$f.py; done
stub app/modules/plans/export_schema.py
for f in chat edit_ops material_vision llm_client; do stub app/modules/ai/$f.py; done

mkdir -p app/modules/ai/prompts tests/fixtures/pdfs tests/fixtures/plans tests/unit tests/integration
touch app/modules/ai/prompts/.gitkeep tests/fixtures/pdfs/.gitkeep tests/fixtures/plans/.gitkeep tests/integration/.gitkeep
```

### 6.3 Backend: files to write with exact content

Append this to `backend/pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
pythonpath = ["."]
```

`backend/app/core/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/archplan_test"
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwks_url: str = ""
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_bucket: str = "archplan"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    llm_provider: str = ""
    llm_api_key: str = ""
    frontend_origin: str = "http://localhost:5173"


settings = Settings()
```

`backend/app/core/db.py`:

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for every module's models."""


engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
```

`backend/app/main.py`:

```python
import importlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

MODULES = ["projects", "files", "plans", "parsing", "sheets", "materials", "ai", "loan", "jobs"]


def create_app() -> FastAPI:
    app = FastAPI(title="Arch Platform API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for name in MODULES:
        module = importlib.import_module(f"app.modules.{name}.router")
        app.include_router(module.router, prefix=f"/api/v1/{name}", tags=[name])

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

`backend/app/workers/celery_app.py`:

```python
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "archplan",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.tasks.parse_plan",
        "app.workers.tasks.build_report",
        "app.workers.tasks.extract_loan",
    ],
)

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_routes = {
    "app.workers.tasks.parse_plan.*": {"queue": "parsing"},
    "app.workers.tasks.build_report.*": {"queue": "reports"},
}
celery_app.conf.task_time_limit = 600
```

`backend/app/modules/plans/schemas.py` (the plan JSON model; this is the one real model in the scaffold):

```python
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Point = Annotated[list[float], Field(min_length=2, max_length=2)]


class Wall(BaseModel):
    id: str
    start: Point
    end: Point
    thickness: float = 0.2


class Opening(BaseModel):
    id: str
    wall_id: str
    type: Literal["door", "window"]
    offset: float
    width: float
    height: float
    sill: float = 0.0


class Room(BaseModel):
    id: str
    name: str | None = None
    polygon: list[Point]


class Level(BaseModel):
    elevation: float = 0.0
    wall_height: float = 3.0
    walls: list[Wall] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)
    rooms: list[Room] = Field(default_factory=list)


class PlanJSON(BaseModel):
    version: int = 1
    units: Literal["m"] = "m"
    scale_source: Literal["scale_text", "dimension_label", "user_reference", "assumed"] = "assumed"
    levels: list[Level] = Field(default_factory=list)
    confidence: dict[str, float] = Field(default_factory=dict)
```

`backend/app/modules/plans/export_schema.py` (writes the JSON Schema that the frontend types are generated from):

```python
"""Write the PlanJSON schema to shared/plan-schema/plan.schema.json."""

import json
from pathlib import Path

from app.modules.plans.schemas import PlanJSON

# backend/app/modules/plans/export_schema.py -> repository root is parents[4]
OUTPUT = Path(__file__).resolve().parents[4] / "shared" / "plan-schema" / "plan.schema.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(PlanJSON.model_json_schema(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
```

`backend/tests/unit/test_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app

MODULES = ["projects", "files", "plans", "parsing", "sheets", "materials", "ai", "loan", "jobs"]
client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("name", MODULES)
def test_module_ping(name: str) -> None:
    response = client.get(f"/api/v1/{name}/ping")
    assert response.status_code == 200
    assert response.json()["module"] == name
```

`backend/tests/unit/test_plan_schema.py`:

```python
from app.modules.plans.schemas import PlanJSON


def test_empty_plan_is_valid() -> None:
    plan = PlanJSON()
    assert plan.units == "m"
    assert plan.levels == []
```

Alembic wiring. Edit `backend/migrations/env.py` (generated in 6.2): near the top, after the existing imports, add the block below; then make sure `target_metadata = Base.metadata` replaces the generated `target_metadata = None`. Leave `sqlalchemy.url` empty in `alembic.ini`. Do not generate any migration yet.

```python
import importlib

from app.core.config import settings
from app.core.db import Base

for _name in ["projects", "files", "plans", "parsing", "sheets", "materials", "ai", "loan", "jobs"]:
    importlib.import_module(f"app.modules.{_name}.models")

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

`backend/Dockerfile`:

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.4 Frontend: dependencies and scaffold

```bash
cd ..        # back to the repository root
pnpm create vite@latest frontend --template react-ts
cd frontend
pnpm install

pnpm add react-router-dom @tanstack/react-query zustand zod @supabase/supabase-js \
         three @react-three/fiber @react-three/drei three-mesh-bvh three-bvh-csg \
         pdfjs-dist konva react-konva

pnpm add -D @types/three tailwindcss @tailwindcss/vite \
            vitest jsdom @testing-library/react @testing-library/jest-dom \
            prettier json-schema-to-typescript
```

Use `@react-three/fiber` v9 with React 19. If the Vite template installed an older React, keep the template's versions and report any peer-dependency warning. Do not run `shadcn init` (it is interactive); see section 10.

Create the folders and stubs. Run this from `frontend/`:

```bash
tsstub() { mkdir -p "$(dirname "$1")"; printf '// %s - TODO\nexport {}\n' "$1" > "$1"; }

mkdir -p src/components/ui src/types
touch src/components/ui/.gitkeep

for f in router providers; do tsstub src/app/$f.tsx; done
for f in api supabase sse; do tsstub src/lib/$f.ts; done

for feat in auth projects files sheets chat loan reports; do
  mkdir -p src/features/$feat/components src/features/$feat/hooks
  touch src/features/$feat/components/.gitkeep src/features/$feat/hooks/.gitkeep
  tsstub src/features/$feat/api.ts
  tsstub src/features/$feat/index.ts
done

for feat in plan-viewer plan-editor; do
  mkdir -p src/features/$feat
  tsstub src/features/$feat/api.ts
  tsstub src/features/$feat/index.ts
done
tsstub src/features/plan-viewer/PlanViewer.tsx
for f in buildWalls buildFloors buildOpenings; do tsstub src/features/plan-viewer/builders/$f.ts; done
mkdir -p src/features/plan-viewer/controls src/features/plan-editor/tools
touch src/features/plan-viewer/controls/.gitkeep src/features/plan-editor/tools/.gitkeep
tsstub src/features/plan-editor/PlanEditor.tsx
```

### 6.5 Frontend: config files

Replace `frontend/vite.config.ts` with the following. If the template uses a different React plugin import (for example `@vitejs/plugin-react-swc`), keep the template's import and only add the Tailwind plugin and the `test` block.

```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
  test: { environment: 'jsdom', globals: true },
})
```

Replace the contents of `frontend/src/index.css` with:

```css
@import "tailwindcss";
```

Create `frontend/src/smoke.test.ts`:

```ts
import { describe, expect, it } from 'vitest'

describe('smoke', () => {
  it('runs the test runner', () => {
    expect(1 + 1).toBe(2)
  })
})
```

Add this entry to the `"scripts"` section of `frontend/package.json` (keep the existing entries):

```json
"gen:types": "json2ts -i ../shared/plan-schema/plan.schema.json -o src/types/plan.ts"
```

### 6.6 Shared plan schema

Run `cd ..` to return to the repository root, then create `shared/plan-schema/README.md`:

```markdown
# Plan schema

`plan.schema.json` is generated from the Pydantic model `PlanJSON` in
`backend/app/modules/plans/schemas.py`. Do not edit it by hand.

Regenerate it, and the TypeScript types in `frontend/src/types/plan.ts`, with:

    uv --directory backend run python -m app.modules.plans.export_schema
    pnpm --dir frontend gen:types
```

There are no shell scripts and no Makefile in this project. Every command is a plain `uv`, `pnpm` or `docker compose` command, listed in the root `README.md` (section 6.7).

### 6.7 Infrastructure and root files

`docker-compose.yml`:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports: ["9000:9000", "9001:9001"]
    volumes: ["minio_data:/data"]

  minio-init:
    image: minio/mc
    depends_on: [minio]
    entrypoint: >
      /bin/sh -c "until mc alias set local http://minio:9000 minioadmin minioadmin; do sleep 1; done;
      mc mb --ignore-existing local/archplan;"

  test-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: archplan_test
    ports: ["5433:5432"]

  api:
    build: ./backend
    env_file: .env
    environment:
      REDIS_URL: redis://redis:6379/0
      S3_ENDPOINT_URL: http://minio:9000
    ports: ["8000:8000"]
    depends_on: [redis, minio]
    profiles: ["full"]

  worker:
    build: ./backend
    env_file: .env
    environment:
      REDIS_URL: redis://redis:6379/0
      S3_ENDPOINT_URL: http://minio:9000
    command: celery -A app.workers.celery_app:celery_app worker -Q default,parsing,reports --loglevel=info
    depends_on: [redis, minio]
    profiles: ["full"]

volumes:
  minio_data:
```

`.env.example` (no real secrets; these are local development defaults):

```
# Backend
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/archplan_test
SUPABASE_URL=
SUPABASE_JWT_SECRET=
SUPABASE_JWKS_URL=
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT_URL=http://localhost:9000
S3_BUCKET=archplan
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_REGION=us-east-1
LLM_PROVIDER=
LLM_API_KEY=
FRONTEND_ORIGIN=http://localhost:5173

# Frontend
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
```

`.gitignore`:

```
.env
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
.mypy_cache/
node_modules/
dist/
.DS_Store
```

`README.md`:

```markdown
# Arch Platform

Floor-plan PDF to interactive 3D model, with material sheets and reports, for an architectural firm.

Read `AGENTS.md` for the architecture rules and `docs/` for the structure of the code.

## Run it locally

Prerequisites: Node.js 20+, pnpm, Python 3.12, uv, Docker. Run every command from the repository root.

First time only:

    cp .env.example .env
    uv --directory backend sync
    pnpm --dir frontend install

Start the Docker services (Redis, MinIO for local S3, test database):

    docker compose up -d redis minio minio-init test-db

Then run each of these in its own terminal:

    # Backend API  (http://localhost:8000, docs at /docs)
    uv --directory backend run uvicorn app.main:app --reload --port 8000

    # Background worker
    uv --directory backend run celery -A app.workers.celery_app:celery_app worker -Q default,parsing,reports --loglevel=info

    # Frontend  (http://localhost:5173)
    pnpm --dir frontend dev

Stop the Docker services:

    docker compose down

## Other commands

    # Tests
    uv --directory backend run pytest
    pnpm --dir frontend vitest run

    # Lint
    uv --directory backend run ruff check .
    pnpm --dir frontend lint

    # Database migrations
    uv --directory backend run alembic upgrade head

    # Regenerate plan types (after changing the PlanJSON model)
    uv --directory backend run python -m app.modules.plans.export_schema
    pnpm --dir frontend gen:types

    # Run the API and worker in Docker instead of locally
    docker compose --profile full up --build
```

### 6.8 Documentation

Create the `docs/` folder with the seven files in Appendix A, each with exactly the content shown, at the path shown in its heading.

## 7. Conventions

- Python: 3.12, type hints everywhere, `ruff` for lint and format, async endpoints, Pydantic v2 schemas. snake_case.
- TypeScript: strict mode, function components, no `any`. One feature per folder under `features/`. Server state in TanStack Query, UI state in zustand.
- IDs are UUIDs, timestamps are `timestamptz`, status columns use enums or constrained text.
- Request and response models must match between Pydantic and zod. Do not hand-write duplicate types for the plan JSON; use the generated file.
- Never commit `.env` or secrets. Add new config keys to `.env.example`.
- Commit in small steps with clear messages. Do not commit `node_modules`, `.venv` or build output.

## 8. Verification (all must pass before you finish)

```bash
cp -n .env.example .env

# Backend
cd backend
uv run ruff check .
uv run pytest                                   # test_api.py and test_plan_schema.py must pass
uv run uvicorn app.main:app --port 8000 &       # then: curl localhost:8000/health -> {"status":"ok"}
kill %1

# Frontend
cd ../frontend
pnpm build
pnpm vitest run

# Infra and shared schema
cd ..
docker compose config > /dev/null                                        # must validate
uv --directory backend run python -m app.modules.plans.export_schema    # must write shared/plan-schema/plan.schema.json
pnpm --dir frontend gen:types                                            # must write frontend/src/types/plan.ts
pnpm --dir frontend build                                                # must still pass with the generated types
```

Also confirm that `docs/` contains `README.md` and the six numbered files, and that every path in section 5 exists.

In your final report, list what you created, anything you skipped and why, any warnings from dependency installs, and the exact commands to start the dev environment.

## 9. Boundaries

**Always**
- Follow section 3 when adding any code.
- Keep stubs minimal and clearly marked `TODO`.
- Update `docs/` when you add or move folders.

**Ask first**
- Adding a dependency not listed in section 6.
- Changing the folder layout, the plan JSON shape or the database schema.
- Choosing an LLM provider or installing an LLM SDK.

**Never**
- Implement extraction, geometry or calculation logic as part of the scaffold.
- Create database tables, models or migrations as part of the scaffold.
- Hard-code CAD layer names, drawing scales or any other assumption about one specific PDF.
- Put secrets in code, docs or `.env.example`.
- Run `git init`, add a remote, or change git configuration. The repository already exists.
- Run destructive commands (`git reset --hard`, dropping tables, deleting folders outside this repo).

## 10. Open decisions (ask the owner; do not guess)

- LLM provider and SDK for `ai/llm_client.py`. Keep it behind a provider-neutral interface until decided.
- UI kit: Tailwind only for now; shadcn/ui is optional.
- Hosting targets for the API, worker and frontend.
- Loan module data model and extraction approach (listed as "to be discussed").
- The database schema migration (tables for profiles, projects, files, plans, plan versions, sheets, materials, conversations, jobs) is a separate task.

---

# Appendices

## Appendix A: contents of the `docs/` folder

Create each file below at the path in its heading, with exactly the content in the fenced block (the outer four-backtick fence is not part of the file).

### A.1 `docs/README.md`

````markdown
# Documentation

This folder explains how the repository is organised and why. Read the files in order if you are new to the project.

| File | What it explains |
|---|---|
| [01-repository-layout.md](01-repository-layout.md) | Top-level folders and root files, and the rules that shape them |
| [02-backend-structure.md](02-backend-structure.md) | The FastAPI app: `core`, `modules`, `events`, `workers`, tests |
| [03-frontend-structure.md](03-frontend-structure.md) | The React app: `app`, `lib`, `features`, and how the 3D viewer is organised |
| [04-parsing-module.md](04-parsing-module.md) | The PDF-to-plan pipeline, file by file |
| [05-data-and-storage.md](05-data-and-storage.md) | Database tables, plan JSON, S3 layout, migrations |
| [06-workers-and-realtime.md](06-workers-and-realtime.md) | Celery queues, job lifecycle and SSE progress events |

Keep these files in sync with the code. When you add, move or remove a folder, update the matching file in the same commit.
````

### A.2 `docs/01-repository-layout.md`

````markdown
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
````

### A.3 `docs/02-backend-structure.md`

````markdown
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
````

### A.4 `docs/03-frontend-structure.md`

````markdown
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
````

### A.5 `docs/04-parsing-module.md`

````markdown
# 04 Parsing module

Location: `backend/app/modules/parsing/`. This module converts an uploaded PDF into a **plan JSON**. It is the hardest part of the product, so it is built to work on PDFs in many formats instead of one.

## Design

```
PDF -> pdf_inspect -> extractors (several) -> geometry cleanup -> scale -> validate -> best result -> plan JSON
```

1. Every extractor implements the same interface and outputs the same plan JSON.
2. The pipeline runs the extractors that apply, scores each result, and keeps the best one.
3. No extractor is required to succeed. If all fail or confidence is low, the user fixes the plan in the editor, or traces walls manually.
4. The LLM is used for meaning only (page choice, room names, scale text). It never supplies coordinates.

## Files

| File | Purpose |
|---|---|
| `router.py` | Endpoints to start parsing a file and to read the result. Starting a parse creates a job and enqueues a Celery task. |
| `service.py` | Entry point used by the worker task and by other modules. Calls `pipeline.py`. |
| `schemas.py` | Request and response models (parse options, job info). The plan model itself lives in `modules/plans/schemas.py`. |
| `pdf_inspect.py` | Looks at the PDF: page count, whether a page is vector or scanned, and which page is the floor plan (with LLM help if there are several). |
| `pipeline.py` | Orchestrator. Chooses extractors, runs them, applies geometry cleanup, scale and validation, picks the best result, reports progress. |
| `scale.py` | Finds real-world scale: from scale text such as `1:100`, from dimension labels, or from a user-provided reference. Records `scale_source`. |
| `units.py` | Parses dimension strings such as `12'8 X 11'`, `3'4 WD.` and metric labels into metres. |
| `validate.py` | Scores a result: rooms closed, walls connected, measured room sizes versus printed sizes, plausible areas. Produces per-element `confidence`. |

## `extractors/`

| File | Purpose |
|---|---|
| `base.py` | The `Extractor` interface: `can_handle(pdf_info) -> score` and `extract(pdf, page) -> PlanJSON`. |
| `vector.py` | Reads vector drawing paths (PyMuPDF `get_drawings()`) and decides which are walls, doors and windows from how they look: stroke width, fill, length, orientation, parallel partners, connections. CAD layer names are one optional input feature, never a requirement. |
| `raster.py` | Renders the page to an image and finds walls, doors and windows with image processing and a segmentation model, then vectorises the masks. Works on scanned PDFs. |
| `semantics.py` | Uses a vision LLM to read room names, scale text and printed dimensions, and to sanity-check the result. Output is labels and numbers, not coordinates. |

To add a new extraction method, add a file implementing `Extractor` and register it in `pipeline.py`. Nothing else changes.

## `geometry/`

Deterministic helpers shared by all extractors, so cleanup does not depend on where the lines came from.

| File | Purpose |
|---|---|
| `snap.py` | Snaps nearly-touching endpoints together, straightens near-axis-aligned lines, removes duplicates. |
| `walls.py` | Pairs parallel lines into wall centrelines with thickness, merges collinear segments. |
| `rooms.py` | Builds closed room polygons from wall centrelines (Shapely `polygonize`) and attaches labels to the polygon that contains them. |
| `openings.py` | Finds gaps and door/window marks along walls and records them as openings with offset, width and height. |

## Output

A plan JSON (see [05-data-and-storage.md](05-data-and-storage.md)) with:

- `walls`, `openings`, `rooms` in metres,
- `scale_source` (`scale_text`, `dimension_label`, `user_reference` or `assumed`),
- `confidence` per element, which drives the highlighting in the editor.

The task saves it as a new plan version with `origin = "extracted"`.

## Testing

Put sample PDFs in `backend/tests/fixtures/pdfs/` with a hand-checked expected plan in `fixtures/plans/`. Tests compare room count, room areas and wall lengths within tolerances. When a real drawing fails, add it as a fixture before fixing the code.
````

### A.6 `docs/05-data-and-storage.md`

````markdown
# 05 Data and storage

Postgres is hosted on Supabase. Alembic (`backend/migrations/`) owns the schema. Files live in S3.

## Tables

| Table | Purpose |
|---|---|
| `profiles` | One row per user, keyed by the Supabase `auth.users.id`. Name and phone. No passwords. |
| `projects` | A user has many projects. Name, description, status. |
| `files` | Every uploaded or generated file: `kind`, `storage_key`, `mime_type`, `size_bytes`, `status`. |
| `plans` | A plan inside a project. Optional link to its source PDF in `files`. |
| `plan_versions` | Versions of a plan: `plan_json`, `origin` (`extracted`, `chat`, `user_edit`), optional preview image. |
| `sheets` | A material sheet computed from one plan version. Has a `stale` flag. |
| `sheet_items` | One row per material line: quantity, unit, `source` (`computed_from_plan` or `photo_estimate`), `user_overridden`. |
| `materials` | The material catalogue: name, category, unit, waste factor. |
| `material_prices` | Price history per material. |
| `conversations`, `messages` | Chat history. `messages.metadata` holds structured edit operations. |
| `message_attachments` | Join table linking messages to `files`. |
| `jobs` | Celery job state: type, status, progress, error. |

Ownership flows downwards: `profiles -> projects -> everything else`. Row-level security policies enforce that a user only sees rows in their own projects.

## Plan JSON

The plan JSON is the source of truth for geometry. Units are metres.

```json
{
  "version": 1,
  "units": "m",
  "scale_source": "dimension_label",
  "levels": [
    {
      "elevation": 0,
      "wall_height": 3.0,
      "walls":    [{ "id": "w1", "start": [0, 0], "end": [5, 0], "thickness": 0.2 }],
      "openings": [{ "id": "o1", "wall_id": "w1", "type": "door", "offset": 1.2, "width": 0.9, "height": 2.1 }],
      "rooms":    [{ "id": "r1", "name": "Living Room", "polygon": [[0, 0], [5, 0], [5, 4], [0, 4]] }]
    }
  ],
  "confidence": { "w1": 0.92, "o1": 0.6 }
}
```

- Defined once as a Pydantic model (`modules/plans/schemas.py`), exported to `shared/plan-schema/plan.schema.json` by `export_schema.py`, and converted to `frontend/src/types/plan.ts` by `pnpm gen:types`.
- Each edit creates a new row in `plan_versions`. Old versions are kept.
- Sheets store the plan version they were computed from. When the plan moves to a newer version, the sheet is marked stale.

## S3 layout

```
projects/<project_id>/uploads/<file_id>.<ext>      original PDFs and photos
projects/<project_id>/previews/<file_id>.png       plan preview images
projects/<project_id>/reports/<file_id>.pdf        generated reports
```

- The database stores the key, never a URL. URLs are presigned on demand and expire.
- The browser uploads directly to S3 using a presigned URL from the API. Files never stream through FastAPI.

## Migrations

```bash
uv --directory backend run alembic upgrade head     # apply
uv --directory backend run alembic revision --autogenerate -m "describe change"
```

Review autogenerated migrations before applying. Never edit tables by hand.
````

### A.7 `docs/06-workers-and-realtime.md`

````markdown
# 06 Workers and realtime

Slow work never runs inside a request. The API starts a job, a Celery worker runs it, and the browser follows progress over SSE.

## Flow

```
Browser           FastAPI                Redis              Celery worker
  | POST parse --->  create job row                              |
  |                  enqueue task ---------> queue ------------> run
  | <--- 202 + job_id                                            |
  | GET /events/jobs/<id> (SSE)                                  | publish progress
  | <------------ events <---- subscribe <---- pub/sub <--------- |
  |                                                              | save result, mark job done
```

## `app/workers/`

| File | Purpose |
|---|---|
| `celery_app.py` | Celery configuration: Redis broker, queues, retry defaults, task time limits. |
| `tasks/parse_plan.py` | Loads the PDF from S3, runs `parsing.service`, saves a plan version, updates the job. |
| `tasks/build_report.py` | Builds the material report (PDF) or spreadsheet and stores it in S3. |
| `tasks/extract_loan.py` | Placeholder for loan document extraction. |

## Queues

| Queue | Used for | Notes |
|---|---|---|
| `default` | Light jobs | Small, fast tasks. |
| `parsing` | PDF parsing, image processing, model inference | Heavy. Can run on its own machine or GPU later. |
| `reports` | Report and export generation | Independent from parsing so one cannot starve the other. |

The worker image installs the same dependencies as the API. If the segmentation model grows heavy, build a separate image for the `parsing` queue that adds the `ml` extra.

## Job lifecycle

`queued -> running -> done | failed`, with a `progress` number from 0 to 100 and an `error` message on failure. Tasks update the `jobs` row and publish an event at each step.

## Events

| File | Purpose |
|---|---|
| `events/pubsub.py` | `publish(job_id, event)` and `subscribe(job_id)` on Redis channels. |
| `events/sse.py` | `GET /events/jobs/{job_id}`: checks the user owns the job, subscribes, and streams events. Sends a heartbeat so proxies keep the connection open. |

Event example:

```json
{ "job_id": "...", "status": "running", "progress": 60, "step": "validating plan" }
```

If the browser reconnects, the endpoint first sends the current job state from the database, so a missed event does not leave the UI stuck.

## Rules

1. Tasks must be idempotent: running one twice must not create duplicate plan versions.
2. Tasks read inputs from S3 and the database, never from request memory.
3. Every task updates its job row, including on failure.
````