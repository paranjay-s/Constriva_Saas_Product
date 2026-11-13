# Constriva SaaS Platform

Transform architectural drawings into interactive 3D walkthroughs with automated Bill of Quantities (BOQ) material sheets.

## Constriva Landing Page
The marketing landing page is built with React 19, TypeScript, and Tailwind CSS v4, porting the Altura Coastal Residences design with precision while showcasing Constriva's core capabilities:
1. **2D floor plan to live 3D walkthrough**
2. **Material-wise BOQ sheets (PDF download & material highlight)**
3. **Prompt to 2D floor plan generation**
4. **Photo to materials AI inspection**

### Running the Landing Page
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` to view the full dusk hero with 9-letter roof-cut wordmark, refractive glass navigation, and the 8-room scroll-scrubbed walkthrough.

### Editing Landing Page Copy
All landing page text, headings, numbers, navigation links, and walkthrough captions are strictly isolated in:
- `frontend/src/content/site.ts`

To update the brand name or any copy, edit `BRAND` or the corresponding field in `siteContent`. The layout dynamically adapts to word length.

---

## 1. Prerequisites (Install Once)

Before running the project locally, ensure you have the following installed on your machine:

| Tool | Minimum Version | Installation / Verification |
|---|---|---|
| **Git** | Any recent version | `git --version` |
| **Node.js** | 20+ | `node -v` ([nodejs.org](https://nodejs.org/)) |
| **pnpm** | 9+ | `npm install -g pnpm` (`pnpm -v`) |
| **Python** | 3.12 or 3.13 | `python --version` ([python.org](https://www.python.org/)) |
| **uv** (Fast Python package manager) | Latest | `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh \| sh` (`uv --version`) |
| **Docker Desktop** | Docker Compose v2 | Ensure Docker Desktop is running (`docker compose version`) |

---

## 2. Directory Reference Quick-Guide

Use this table to know which folder to run each command from:

| What you want to do | Where to run the command |
|---|---|
| Clone repo, `.env`, Docker services | **Repository Root** (`Constriva_Saas_Product/`) |
| Backend API, Celery worker, pytest, alembic | `backend/` *(or root using `--directory backend`)* |
| Frontend dev server, pnpm install, vitest | `frontend/` *(or root using `--dir frontend`)* |
| Schema export (`export_schema`) | `backend/` *(or root using `--directory backend`)* |
| TypeScript type generation (`gen:types`) | `frontend/` *(or root using `--dir frontend`)* |

---

## 3. First-Time Setup

### Step 1: Clone the Repository
> 📍 **Run from:** Anywhere you store projects
```bash
git clone <repository-url>
cd Constriva_Saas_Product
```

### Step 2: Configure Environment Variables
> 📍 **Run from:** `Repository Root` (`Constriva_Saas_Product/`)

Copy the sample environment file to `.env`:

- **Windows (PowerShell)**:
  ```powershell
  Copy-Item .env.example .env
  ```
- **macOS / Linux / Git Bash**:
  ```bash
  cp .env.example .env
  ```

*(The defaults in `.env.example` connect to local Docker services: Redis, MinIO S3, and test PostgreSQL).*

### Step 3: Install Backend Dependencies
> 📍 **Run from:** `backend/` directory *(or from Root using `uv --directory backend`)*

- **From `backend/` folder:**
  ```bash
  cd backend
  uv sync
  cd ..
  ```
- **OR from `Repository Root`:**
  ```bash
  uv --directory backend sync
  ```

### Step 4: Install Frontend Dependencies
> 📍 **Run from:** `frontend/` directory *(or from Root using `pnpm --dir frontend`)*

- **From `frontend/` folder:**
  ```bash
  cd frontend
  pnpm install
  cd ..
  ```
- **OR from `Repository Root`:**
  ```bash
  pnpm --dir frontend install
  ```

### Step 5: Start Local Infrastructure (Docker)
> 📍 **Run from:** `Repository Root` (`Constriva_Saas_Product/`)

Start the background services (Redis, MinIO local S3, bucket initialization, and PostgreSQL):
```bash
docker compose up -d redis minio minio-init test-db
```

> **Note**: This starts:
> - **Redis** on port `6379` (task queue & pub/sub)
> - **MinIO (S3)** on port `9000` (API) and port `9001` (Web Console, user: `minioadmin`, pass: `minioadmin`)
> - **Test PostgreSQL** on port `5433`

---

## 4. Running the Application Locally

Open **3 separate terminal windows**:

### Terminal 1 — Backend API
> 📍 **Directory:** `backend/` *(or Root)*

- **If inside `backend/` folder:**
  ```bash
  uv run uvicorn app.main:app --reload --port 8000
  ```
- **If at `Repository Root`:**
  ```bash
  uv --directory backend run uvicorn app.main:app --reload --port 8000
  ```

**Endpoints:**
- API URL: [http://localhost:8000](http://localhost:8000)
- Interactive Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

---

### Terminal 2 — Background Celery Worker
> 📍 **Directory:** `backend/` *(or Root)*

- **If inside `backend/` folder:**
  ```bash
  uv run celery -A app.workers.celery_app:celery_app worker -Q default,parsing,reports --loglevel=info
  ```
- **If at `Repository Root`:**
  ```bash
  uv --directory backend run celery -A app.workers.celery_app:celery_app worker -Q default,parsing,reports --loglevel=info
  ```

*This worker handles heavy background tasks: PDF parsing, geometry extraction, and report building.*

---

### Terminal 3 — Frontend Web Application
> 📍 **Directory:** `frontend/` *(or Root)*

- **If inside `frontend/` folder:**
  ```bash
  pnpm dev
  ```
- **If at `Repository Root`:**
  ```bash
  pnpm --dir frontend dev
  ```

**Frontend URL:**
- Web App UI: [http://localhost:5173](http://localhost:5173)

---

## 5. Other Useful Commands

### Running Tests

- **Backend tests** (📍 Run in `backend/` or from Root):
  ```bash
  # Inside backend/
  uv run pytest

  # From Root
  uv --directory backend run pytest
  ```

- **Frontend tests** (📍 Run in `frontend/` or from Root):
  ```bash
  # Inside frontend/
  pnpm vitest run

  # From Root
  pnpm --dir frontend vitest run
  ```

---

### Linting & Formatting

- **Backend (Ruff)** (📍 Run in `backend/` or from Root):
  ```bash
  # Inside backend/
  uv run ruff check .

  # From Root
  uv --directory backend run ruff check .
  ```

- **Frontend** (📍 Run in `frontend/` or from Root):
  ```bash
  # Inside frontend/
  pnpm lint

  # From Root
  pnpm --dir frontend lint
  ```

---

### Database Migrations

📍 **Directory:** `backend/` *(or Root)*

```bash
# Inside backend/
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "describe changes"

# From Root
uv --directory backend run alembic upgrade head
uv --directory backend run alembic revision --autogenerate -m "describe changes"
```

---

### Regenerating Plan Schema & Types

When the Pydantic plan model in [`backend/app/modules/plans/schemas.py`](backend/app/modules/plans/schemas.py) is modified:

1. **Export the updated JSON schema** (📍 `backend/` or Root):
   ```bash
   # Inside backend/
   uv run python -m app.modules.plans.export_schema

   # From Root
   uv --directory backend run python -m app.modules.plans.export_schema
   ```

2. **Regenerate frontend TypeScript types in `frontend/src/types/plan.ts`** (📍 `frontend/` or Root):
   ```bash
   # Inside frontend/
   pnpm gen:types

   # From Root
   pnpm --dir frontend gen:types
   ```

---

### Full Docker Setup (Alternative)
> 📍 **Directory:** `Repository Root` (`Constriva_Saas_Product/`)

To run the entire stack (API, worker, Redis, MinIO, and PostgreSQL) in Docker containers:
```bash
docker compose --profile full up --build
```

---

### Stopping the Environment
> 📍 **Directory:** `Repository Root` (`Constriva_Saas_Product/`)

To stop all running Docker infrastructure containers:
```bash
docker compose down
```
