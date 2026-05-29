from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.outbound import build_safe_httpx_client
from app.core.errors import ApiError


@dataclass(slots=True)
class OAuthIdentity:
    account: str
    name: str
    email: str
    department: str
    sysid: int
    tcode: str
    role: str = "user"


class OAuthService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _required(self, value: str | None, key: str) -> str:
        if not value:
            raise ApiError("INTERNAL_ERROR", f"missing oauth config: {key}", 500)
        return value

    def build_login_url(self) -> str:
        auth_uri = self._required(self.settings.oauth_auth_uri, "OAUTH_AUTH_URI")
        query = urlencode(
            {
                "client_id": self._required(self.settings.oauth_client_id, "OAUTH_CLIENT_ID"),
                "redirect_uri": self._required(self.settings.oauth_redirect_uri, "OAUTH_REDIRECT_URI"),
                "response_type": "code",
                "scope": self.settings.oauth_scope,
            }
        )
        return f"{auth_uri}?{query}"

    def exchange_code_for_token(self, code: str) -> str:
        token_uri = self._required(self.settings.oauth_token_uri, "OAUTH_TOKEN_URI")
        payload = {
            "grant_type": "authorization_code",
            "client_id": self._required(self.settings.oauth_client_id, "OAUTH_CLIENT_ID"),
            "client_secret": self._required(self.settings.oauth_client_secret, "OAUTH_CLIENT_SECRET"),
            "redirect_uri": self._required(self.settings.oauth_redirect_uri, "OAUTH_REDIRECT_URI"),
            "code": code,
        }
        try:
            with build_safe_httpx_client(timeout_seconds=10.0) as client:
                response = client.post(token_uri, data=payload)
        except httpx.TimeoutException as exc:
            raise ApiError("OAUTH_TOKEN_EXCHANGE_FAILED", "oauth token exchange failed: timeout", 401) from exc
        except httpx.HTTPError as exc:
            raise ApiError("OAUTH_TOKEN_EXCHANGE_FAILED", "oauth token exchange failed: network_error", 401) from exc
        if response.status_code != 200:
            raise ApiError(
                "OAUTH_TOKEN_EXCHANGE_FAILED",
                f"oauth token exchange failed: upstream_status={response.status_code}",
                401,
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise ApiError("OAUTH_TOKEN_EXCHANGE_FAILED", "oauth token exchange failed: invalid_json", 401) from exc
        token = body.get("access_token")
        if not token or not isinstance(token, str):
            raise ApiError("OAUTH_TOKEN_EXCHANGE_FAILED", "oauth access token missing", 401)
        return token

    def fetch_identity(self, access_token: str) -> OAuthIdentity:
        basic_uri = self._required(self.settings.oauth_basic_uri, "OAUTH_BASIC_URI")
        try:
            with build_safe_httpx_client(timeout_seconds=10.0) as client:
                response = client.post(basic_uri, data={"access_token": access_token})
        except httpx.TimeoutException as exc:
            raise ApiError("OAUTH_BASIC_FETCH_FAILED", "oauth basic profile fetch failed: timeout", 401) from exc
        except httpx.HTTPError as exc:
            raise ApiError("OAUTH_BASIC_FETCH_FAILED", "oauth basic profile fetch failed: network_error", 401) from exc
        if response.status_code != 200:
            raise ApiError(
                "OAUTH_BASIC_FETCH_FAILED",
                f"oauth basic profile fetch failed: upstream_status={response.status_code}",
                401,
            )
        try:
            claims = response.json()
        except ValueError as exc:
            raise ApiError("OAUTH_BASIC_FETCH_FAILED", "oauth basic profile fetch failed: invalid_json", 401) from exc
        identity = OAuthIdentity(
            account=self._pick_claim(claims, "cn"),
            name=self._pick_claim(claims, "chName"),
            email=self._pick_claim(claims, "email"),
            department=self._pick_claim(claims, "instCode"),
            sysid=self._pick_numeric_claim(claims, "sysId"),
            tcode=self._pick_claim(claims, "tCode"),
            role="user",
        )
        return identity

    def _pick_claim(self, claims: dict, *keys: str) -> str:
        for key in keys:
            value = claims.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise ApiError("OAUTH_IDENTITY_INVALID", f"missing required oauth claim: {'|'.join(keys)}", 422)

    def _pick_numeric_claim(self, claims: dict, *keys: str) -> int:
        value = self._pick_claim(claims, *keys)
        if not value.isdigit():
            raise ApiError("OAUTH_IDENTITY_INVALID", f"oauth claim must be numeric: {'|'.join(keys)}", 422)
        numeric_value = int(value)
        if numeric_value <= 0:
            raise ApiError("OAUTH_IDENTITY_INVALID", f"oauth claim must be positive integer: {'|'.join(keys)}", 422)
        return numeric_value
