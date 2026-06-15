import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette import status


DEFAULT_INTERNAL_ERROR_MESSAGE = "unexpected internal error"
logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: str | None = None,
        *,
        extra: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        self.extra = extra or {}
        self.headers = headers or {}
        super().__init__(message)


def _derive_error_details(request: Request, explicit_details: str | None = None) -> str | None:
    if explicit_details:
        return explicit_details
    endpoint = request.scope.get("endpoint")
    if not callable(endpoint):
        return None
    module = getattr(endpoint, "__module__", "")
    name = getattr(endpoint, "__name__", "")
    if not module or not name:
        return None
    return f"{module}:{name}"


def get_request_id(request: Request) -> str | None:
    request_id = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) and request_id else None


def _build_error_content(
    request: Request,
    *,
    code: str,
    message: str,
    details: str | None = None,
    extra: dict | None = None,
) -> dict:
    error = {"code": code, "message": message}
    resolved_details = _derive_error_details(request, details)
    if resolved_details:
        error["details"] = resolved_details
    content = {"error": error}
    request_id = get_request_id(request)
    if request_id:
        content["request_id"] = request_id
    if extra:
        content.update(extra)
    return content


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_content(
                request,
                code=exc.code,
                message=exc.message,
                details=exc.details,
                extra=exc.extra,
            ),
            headers=exc.headers,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        code = "VALIDATION_ERROR" if exc.status_code == 422 else "INTERNAL_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_content(request, code=code, message=str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception request_id=%s path=%s", get_request_id(request), request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_build_error_content(
                request,
                code="INTERNAL_ERROR",
                message=DEFAULT_INTERNAL_ERROR_MESSAGE,
                extra={"route": request.url.path, "reason": "unexpected_internal_error"},
            ),
        )
