from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"


def create_app() -> FastAPI:
    app = FastAPI(title="AS API Console", version="0.1.0")
    settings = get_settings()
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)
    register_exception_handlers(app)
    app.include_router(auth_router)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    if FRONTEND_ASSETS.exists():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_ASSETS)), name="assets")

    if FRONTEND_DIST.exists():

        @app.get("/")
        async def serve_frontend_index() -> FileResponse:
            return FileResponse(str(FRONTEND_DIST / "index.html"))

        @app.get("/{full_path:path}")
        async def serve_frontend_spa(full_path: str) -> FileResponse:
            if full_path.startswith("api/") or full_path in {"health", "docs", "openapi.json", "redoc"}:
                raise HTTPException(status_code=404)
            target = FRONTEND_DIST / full_path
            if target.is_file():
                return FileResponse(str(target))
            return FileResponse(str(FRONTEND_DIST / "index.html"))

    return app


app = create_app()
