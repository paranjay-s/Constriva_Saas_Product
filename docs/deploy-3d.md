# Deploying the 3D service (PlanTo3D) on a Linux GPU server

The backend's 3D gateway (`backend/app/modules/plan3d`) talks to PlanTo3D over HTTP (`PLAN3D_SERVICE_URL`). PlanTo3D
reads plans, serves the review page and the walkthrough, builds houses in Blender and renders tours. In production it
runs on a machine with an NVIDIA GPU, and only the gateway can reach it.

## Image

`services/planto3d/Dockerfile` (build from the repository root) contains everything a build needs, so a build never
downloads anything:

| Part | Why |
|---|---|
| CUDA 12 runtime (Ubuntu 24.04) | Cycles on the GPU (OptiX or CUDA) for light maps, stills and tours |
| Blender 5.3.0 (official Linux build) | Builds and bakes houses (`blender/gen.py`, `bake.py`), renders tours (`cinema.py`) and builds library pieces |
| poppler-utils | `pdftocairo`, `pdftotext` and `pdfinfo` for page images and text |
| ffmpeg | Recording conversion and tour videos |
| Node | `tools/tour_cinema.mjs` (the tour route) and the three.js files the viewer serves |
| CC0 assets | Textures, models and skies from Poly Haven, listed in `assets/manifest.json` and checked by `tests/test_assets.py` |
| Asset library | Built at image build time by `library/build/build_all.sh` (each piece's .blend, .glb, preview and the index) |

```sh
docker build -t planto3d -f services/planto3d/Dockerfile .
docker run --gpus all --restart unless-stopped -p 127.0.0.1:8080:8080 \
  -v planto3d-jobs:/app/jobs planto3d
```

The host needs the NVIDIA driver and the NVIDIA Container Toolkit (`--gpus all`). Check the GPU is used: the first
build's `jobs/<id>/build.log` says `bake device OPTIX` (or `CUDA`); `CPU` means the container cannot see the GPU.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `BLENDER` | `/opt/blender/blender` | The Blender binary |
| `PLAN3D_TOUR_CHUNK_S` | 480 | Seconds of rendering per tour chunk (a stopped tour resumes from its last chunk) |
| `PLAN3D_TOUR_COOL_S` | 0 in the image (30 on a laptop) | Pause between tour chunks |
| `PLAN3D_SUN_BEARING` | 225 | Compass bearing of the day sun (225: afternoon from the south-west); turned by the drawing's north arrow |
| `PLAN3D_EVENING` | 1 | 0 skips the evening light maps (about 90 s more on a Low build) |
| `PLAN3D_BLENDER_SLOTS` | 1 | Blender processes at once (one per GPU) |
| `PLAN3D_LIBRARY` | 1 | 0 builds with the built-in furniture instead of the library |
| `PLAN3D_QIBLA_BEARING` | 258 | Compass bearing of the qibla for prayer rooms (Dubai); set it for the server's region |

The gateway side (`.env`): `PLAN3D_SERVICE_URL` (for example `http://10.0.0.5:8080`), `PLAN3D_EMBED_SECRET`,
`PLAN3D_AI_VERIFY`, and `EMAIL_SMTP_*` / `EMAIL_FROM` for build emails.

## Queue and lanes

The Blender queue has two lanes. **Fast:** Low builds and the Low step of a High build, so a house can be walked
through within a minute or two. **Heavy:** High bakes and rendered tours. Queued fast work always goes before queued
heavy work (a long tour never holds up someone's Low preview); within a lane it is first come, first served.
`PLAN3D_BLENDER_SLOTS` (default 1) is how many Blender processes run at once. Keep 1 per GPU. On a server with more
than one GPU, you can also run one container per GPU (`--gpus device=N`) behind the gateway, each with its own jobs
volume; the gateway keeps each job on the service that made it.

Each job starts a fresh Blender process (about 3-5 s of start-up, small next to a Low build of about a minute). A warm
Blender kept between jobs was not built: gen.py builds into one scene per process and would need reworking to reset it
safely between jobs.

## Times to expect

Measured on the development Mac (M1 Pro, Metal), not on a server:

- a Low build of a large villa takes about 100 s, and High takes 8 to 10 minutes
- an 8 s, 480p EEVEE tour clip takes about 7 minutes; a full tour is hours
- an NVIDIA RTX-class GPU should be several times faster; measure with `scripts/benchmark_tour.sh` after deploying

## Security

PlanTo3D has no login: bind it to localhost or a private network, and reach it only through the gateway, which checks
the user and signs every embedded page (read-only tokens per job, redacted from logs). Never expose port 8080
publicly.
