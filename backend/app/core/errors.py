from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


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
