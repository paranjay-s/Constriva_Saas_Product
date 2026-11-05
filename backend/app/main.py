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

