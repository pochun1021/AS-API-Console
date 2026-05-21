from __future__ import annotations

from ipaddress import ip_address
from socket import getaddrinfo
from urllib.parse import urlsplit

import httpx

from app.core.config import get_settings
from app.core.errors import ApiError


def validate_outbound_url(raw_url: str | None, *, config_name: str) -> str:
    normalized = (raw_url or "").strip()
    if not normalized:
        raise ApiError("INTERNAL_ERROR", f"missing config: {config_name}", 500)
    settings = get_settings()
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ApiError("INTERNAL_ERROR", f"invalid config URL: {config_name}", 500)
    if settings.require_https_outbound and settings.app_env.lower() not in {"dev", "test"} and parsed.scheme != "https":
        raise ApiError("INTERNAL_ERROR", f"{config_name} must use https", 500)
    if settings.app_env.lower() not in {"dev", "test"} and not settings.allow_private_outbound_hosts:
        for family, _, _, _, sockaddr in getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)):
            host = sockaddr[0]
            addr = ip_address(host)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast:
                raise ApiError("INTERNAL_ERROR", f"{config_name} resolves to disallowed address", 500)
    return normalized


def build_safe_httpx_client(*, timeout_seconds: float) -> httpx.Client:
    return httpx.Client(timeout=timeout_seconds, follow_redirects=False)
