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

