from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.auth import router as auth_router
from app.api.test_auth import router as test_auth_router
from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.security import apply_security_headers
from app.services.persnl_soap_service import PersnlSoapService


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"
PATH_BASE = "/main"


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.persnl_soap_service.initialize()
        yield

    app = FastAPI(
        title="AS API Console",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=f"{PATH_BASE}/docs",
        redoc_url=f"{PATH_BASE}/redoc",
        openapi_url=f"{PATH_BASE}/openapi.json",
    )
    settings = get_settings()
    allowed_hosts = [host.strip() for host in settings.allowed_hosts.split(",") if host.strip()]
    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        session_cookie=settings.session_cookie_name,
        max_age=settings.session_max_age_seconds,
        same_site="lax",
        https_only=settings.session_https_only,
    )
    register_exception_handlers(app)
    app.state.persnl_soap_service = PersnlSoapService()

    app.include_router(auth_router, prefix=PATH_BASE)
    if settings.app_env.lower() == "test":
        app.include_router(test_auth_router, prefix=PATH_BASE)
    app.include_router(api_router, prefix=f"{PATH_BASE}/api/v1")

    @app.middleware("http")
    async def security_headers_middleware(request, call_next):
        response = await call_next(request)
        apply_security_headers(request, response.headers)
        return response

    @app.get(f"{PATH_BASE}/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    if FRONTEND_ASSETS.exists():
        app.mount(f"{PATH_BASE}/assets", StaticFiles(directory=str(FRONTEND_ASSETS)), name="assets")

    if FRONTEND_DIST.exists():

        @app.get(PATH_BASE)
        @app.get(f"{PATH_BASE}/")
        async def serve_frontend_index() -> FileResponse:
            return FileResponse(str(FRONTEND_DIST / "index.html"))

        @app.get(f"{PATH_BASE}" + "/{full_path:path}")
        async def serve_frontend_spa(full_path: str) -> FileResponse:
            if full_path.startswith("api/") or full_path in {"health", "docs", "openapi.json", "redoc", "login", "auth/callback", "logout"}:
                raise HTTPException(status_code=404)
            target = FRONTEND_DIST / full_path
            if target.is_file():
                return FileResponse(str(target))
            return FileResponse(str(FRONTEND_DIST / "index.html"))

    return app


app = create_app()
