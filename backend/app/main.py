"""
=============================================================================
Construtiva SaaS Platform - FastAPI Application Entry Point
=============================================================================
File: app/main.py
Purpose:
  Bootstraps the FastAPI application, configures CORS middleware for the React frontend,
  mounts all business modules (/api/v1/auth, /projects, /files, /parsing, etc.),
  and ensures Supabase Storage buckets ('blueprints', 'rasters', 'site-photos') are provisioned.
=============================================================================
"""

import os
import sys
from pathlib import Path

_backend_root = Path(__file__).resolve().parents[1]
_venv_site_packages = _backend_root / ".venv" / "Lib" / "site-packages"
if _venv_site_packages.exists() and str(_venv_site_packages) not in sys.path:
    sys.path.insert(0, str(_venv_site_packages))

import importlib
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.supabase import ensure_storage_buckets

logger = logging.getLogger("construtiva.app")

MODULES = [
    "auth",
    "projects",
    "files",
    "plans",
    "parsing",
    "sheets",
    "materials",
    "ai",
    "loan",
    "jobs",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager:
    Initializes Supabase Storage buckets on startup.
    """
    logger.info("Initializing Construtiva FastAPI backend...")
    ensure_storage_buckets()
    yield
    logger.info("Construtiva backend shutting down.")


def create_app() -> FastAPI:
    """
    Factory function to construct the FastAPI application instance.
    """
    app = FastAPI(
        title="Construtiva SaaS Platform API",
        version="1.0.0",
        description="Architectural 2D-to-3D Conversion, Material Estimation & Project Management API",
        lifespan=None if os.environ.get("TESTING") == "1" else lifespan,
    )

    # Configure CORS for React frontend origin (ensuring zero CORS errors on port 5173 or any dev port)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.frontend_origin,
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # Dynamically mount all business domain modules
    for name in MODULES:
        try:
            module = importlib.import_module(f"app.modules.{name}.router")
            app.include_router(module.router, prefix=f"/api/v1/{name}", tags=[name.capitalize()])
            logger.info(f"Mounted router: /api/v1/{name}")
        except ModuleNotFoundError as e:
            logger.warning(f"Could not mount module '{name}': {e}")

    @app.get("/health", summary="Health Check")
    async def health() -> dict[str, str]:
        """Simple health check endpoint."""
        return {"status": "ok", "app": "Construtiva SaaS API", "version": "1.0.0"}

    return app


app = create_app()
