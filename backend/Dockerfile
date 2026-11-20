# The FastAPI backend. New in the pro run (docs/deploy-3d.md, "Backend image"): ifcopenshell (IFC export),
# RapidOCR + onnxruntime (scan reader), all from uv.lock; and, optionally, the ODA File Converter for DWG export
# (build with --build-arg ODA_DEB_URL=<the .deb from opendesign.com>; without it DWG answers 503 and DXF remains).
FROM python:3.12-slim
ARG ODA_DEB_URL=""
# libGL/libglib for OpenCV and RapidOCR; the Qt libraries the ODA converter needs, offscreen (QT_QPA_PLATFORM)
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 curl ca-certificates \
    && if [ -n "$ODA_DEB_URL" ]; then \
         curl -fsSL "$ODA_DEB_URL" -o /tmp/oda.deb && apt-get install -y --no-install-recommends /tmp/oda.deb \
         libxkbcommon0 libdbus-1-3 libfontconfig1 && rm /tmp/oda.deb; fi \
    && rm -rf /var/lib/apt/lists/*
ENV QT_QPA_PLATFORM=offscreen
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

