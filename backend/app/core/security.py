from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import uuid4

from fastapi import Depends, Request
from starlette.datastructures import MutableHeaders

from app.core.config import get_settings
from app.core.errors import ApiError


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if isinstance(token, str) and token:
        return token
    token = uuid4().hex
    request.session["csrf_token"] = token
    return token


def verify_csrf(request: Request) -> None:
    settings = get_settings()
    if request.method.upper() in SAFE_METHODS:
        return
    if settings.header_auth_enabled and "auth_context" not in request.session and request.headers.get("x-account"):
        return
    session_token = request.session.get("csrf_token")
    header_name = settings.csrf_header_name.lower()
    provided_token = request.headers.get(header_name)
    if not session_token or not provided_token or session_token != provided_token:
        raise ApiError("FORBIDDEN", "csrf token invalid", 403)


def csrf_protected(request: Request) -> None:
    verify_csrf(request)


def apply_security_headers(request: Request, headers: MutableHeaders) -> None:
    headers["X-Content-Type-Options"] = "nosniff"
    headers["X-Frame-Options"] = "DENY"
    headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/"):
        headers["Cache-Control"] = "no-store"


def validate_date_window(from_date, to_date, *, max_days: int = 31) -> None:
    if from_date and to_date and from_date > to_date:
        raise ApiError("VALIDATION_ERROR", "from must be <= to", 422)
    if from_date and to_date and (to_date - from_date).days > max_days:
        raise ApiError("VALIDATION_ERROR", f"date range must be <= {max_days} days", 422)


def validate_search_keyword(keyword: str | None, *, max_length: int = 100) -> None:
    if keyword is None:
        return
    if len(keyword.strip()) > max_length:
        raise ApiError("VALIDATION_ERROR", f"query length must be <= {max_length}", 422)


@dataclass(slots=True)
class RatePolicy:
    limit: int
    window_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], list[datetime]] = {}
        self._lock = Lock()

    def check(self, scope: str, subject: str, policy: RatePolicy) -> None:
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=policy.window_seconds)
        key = (scope, subject)
        with self._lock:
            recent = [ts for ts in self._events.get(key, []) if ts > cutoff]
            if len(recent) >= policy.limit:
                raise ApiError("RATE_LIMITED", "rate limit exceeded", 429)
            recent.append(now)
            self._events[key] = recent

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


rate_limiter = InMemoryRateLimiter()


def parse_rate_policy(raw: str) -> RatePolicy:
    try:
        limit_text, window_text = raw.strip().split("/", 1)
        limit = int(limit_text)
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"invalid rate limit policy: {raw!r}") from exc
    window_key = window_text.strip().lower()
    windows = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
        "day": 86400,
    }
    seconds = windows.get(window_key)
    if limit <= 0 or seconds is None:
        raise ValueError(f"invalid rate limit policy: {raw!r}")
    return RatePolicy(limit=limit, window_seconds=seconds)


def _client_subject(request: Request) -> str:
    auth_context = request.session.get("auth_context")
    if isinstance(auth_context, dict):
        sysid = auth_context.get("sysid")
        if sysid:
            return f"sysid:{sysid}"
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    client_host = forwarded_for or (request.client.host if request.client else "unknown")
    return f"ip:{client_host}"


def enforce_rate_limit(scope: str, config_value: str):
    policy = parse_rate_policy(config_value)

    def dependency(request: Request) -> None:
        subject = _client_subject(request)
        rate_limiter.check(scope, subject, policy)

    return Depends(dependency)
