"""FISA authorization-code client. Secrets and access tokens stay on the server."""

from dataclasses import dataclass
import secrets
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.outbound import validate_outbound_url


@dataclass(frozen=True, slots=True)
class OAuthIdentity:
    account: str
    name: str
    email: str
    department: str
    sysid: int
    raw_sysid: str
    tcode: str
    role: str = "user"


class OAuthService:
    def __init__(self, settings: Settings | None = None, *, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    @staticmethod
    def _required(value: str | None, name: str) -> str:
        if not value or not value.strip():
            raise ApiError("INTERNAL_ERROR", f"missing oauth config: {name}", 500)
        return value.strip()

    def _url(self, value: str | None, name: str) -> str:
        try:
            return validate_outbound_url(self._required(value, name), config_name=name)
        except (OSError, ValueError) as exc:
            raise ApiError("INTERNAL_ERROR", f"invalid oauth config: {name}", 500) from exc

    def build_login_url(self, request) -> str:
        auth_uri = self._url(self.settings.oauth_auth_uri, "OAUTH_AUTH_URI")
        client_id = self._required(self.settings.oauth_client_id, "OAUTH_CLIENT_ID")
        request.session["oauth_request_id"] = getattr(request.state, "request_id", None) or secrets.token_urlsafe(32)
        parts = urlsplit(auth_uri)
        query = parse_qsl(parts.query, keep_blank_values=True)
        query.extend((
            ("client_id", client_id),
            ("redirect_uri", self.settings.oauth_redirect_uri),
            ("response_type", "code"),
            ("scope", self.settings.oauth_scope),
        ))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))

    def exchange_code_for_token(self, code: str) -> str:
        token_uri = self._url(self.settings.oauth_token_uri, "OAUTH_TOKEN_URI")
        payload = {
            "grant_type": "authorization_code",
            "client_id": self._required(self.settings.oauth_client_id, "OAUTH_CLIENT_ID"),
            "client_secret": self._required(self.settings.oauth_client_secret, "OAUTH_CLIENT_SECRET"),
            "redirect_uri": self.settings.oauth_redirect_uri,
            "code": code,
        }
        try:
            with httpx.Client(timeout=self.settings.oauth_timeout_seconds, transport=self.transport) as client:
                response = client.post(token_uri, data=payload)
            if response.status_code != 200:
                raise ValueError("token status")
            data = response.json()
            token = data.get("access_token") if isinstance(data, dict) else None
            if not isinstance(token, str) or not token:
                raise ValueError("token shape")
            return token
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiError("OAUTH_TOKEN_EXCHANGE_FAILED", "oauth token exchange failed", 401) from exc

    def fetch_identity(self, access_token: str) -> OAuthIdentity:
        basic_uri = self._url(self.settings.oauth_basic_uri, "OAUTH_BASIC_URI")
        try:
            with httpx.Client(timeout=self.settings.oauth_timeout_seconds, transport=self.transport) as client:
                response = client.post(basic_uri, data={"access_token": access_token})
            if response.status_code != 200:
                raise ValueError("identity status")
            claims = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiError("OAUTH_BASIC_FETCH_FAILED", "oauth identity fetch failed", 401) from exc
        if not isinstance(claims, dict):
            raise ApiError("OAUTH_IDENTITY_INVALID", "invalid FISA identity", 422)

        def claim(key: str) -> str:
            value = claims.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ApiError("OAUTH_IDENTITY_INVALID", f"invalid FISA identity: {key}", 422)
            return value.strip()

        raw_sysid = claim("sysid")
        if not raw_sysid.isascii() or not raw_sysid.isdecimal() or int(raw_sysid) <= 0:
            raise ApiError("OAUTH_IDENTITY_INVALID", "invalid FISA identity: sysid", 422)
        email = claim("email")
        if email.count("@") != 1 or not all(email.split("@")):
            raise ApiError("OAUTH_IDENTITY_INVALID", "invalid FISA identity: email", 422)
        return OAuthIdentity(
            account=claim("cn"), name=claim("chName"), email=email.lower(),
            department=claim("instCode"), sysid=int(raw_sysid), raw_sysid=raw_sysid,
            tcode=claim("tCode"),
        )
