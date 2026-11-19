# PlanTo3D on a Linux GPU server: Blender 5.3 (Cycles on the NVIDIA GPU), poppler, ffmpeg, Node (tours), the
# three.js viewer files, the CC0 materials and the asset library, all baked into the image, so builds never download.
#
#   docker build -t planto3d -f services/planto3d/Dockerfile .         (from the repository root)
#   docker run --gpus all -p 127.0.0.1:8080:8080 -v planto3d-jobs:/app/jobs planto3d
#
# See docs/deploy-3d.md. Not built on the development Mac (no Docker there): treat as untested until it is.
FROM nvidia/cuda:12.6.3-runtime-ubuntu24.04

ARG BLENDER_VERSION=5.3.0
ARG BLENDER_SERIES=5.3
ENV DEBIAN_FRONTEND=noninteractive \
    BLENDER=/opt/blender/blender \
    NODE=/usr/bin/node \
    PYTHONUNBUFFERED=1 \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics

# Blender's runtime libraries, PDF tools, video, Node for the tour route and three.js, curl and xz to fetch Blender
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 poppler-utils ffmpeg nodejs npm curl xz-utils ca-certificates \
        libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libsm6 libgl1 libegl1 libglu1-mesa \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://download.blender.org/release/Blender${BLENDER_SERIES}/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
        | tar -xJ -C /opt && mv /opt/blender-${BLENDER_VERSION}-linux-x64 /opt/blender

WORKDIR /app
COPY services/planto3d/ /app/
# the viewer library, the CC0 textures, models and sky (recorded in assets/manifest.json), then the asset library
RUN npm ci --omit=dev --prefix /app || npm install --omit=dev --prefix /app
RUN python3 fetch_assets.py --tour && python3 tests/test_assets.py
RUN bash library/build/build_all.sh || true

# Blender picks the GPU itself (blender/bake.py tries OptiX, then CUDA). Tours: PLAN3D_TOUR_CHUNK_S and
# PLAN3D_TOUR_COOL_S (0 on a server with proper cooling).
ENV PLAN3D_TOUR_COOL_S=0
EXPOSE 8080
VOLUME ["/app/jobs"]
CMD ["python3", "server.py", "--host", "0.0.0.0", "--port", "8080"]
