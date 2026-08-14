from dataclasses import dataclass
import base64
import json
import logging
import secrets
import time
from urllib.parse import urlencode

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.core.config import get_settings
from app.core.outbound import build_safe_httpx_client
from app.core.errors import ApiError

logger = logging.getLogger(__name__)


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
    _UPSTREAM_BODY_LOG_LIMIT = 300

    def __init__(self) -> None:
        self.settings = get_settings()

    def _required(self, value: str | None, key: str) -> str:
        if not value:
            raise ApiError("INTERNAL_ERROR", f"missing oauth config: {key}", 500)
        return value

    def build_login_url(self, request=None) -> str:
        auth_uri = "https://accounts.google.com/o/oauth2/v2/auth"
        redirect_uri = self._required(self.settings.oauth_redirect_uri, "OAUTH_REDIRECT_URI")
        state = self._new_token()
        nonce = self._new_token()
        if request is not None:
            request.session["oauth_state"] = state
            request.session["oauth_nonce"] = nonce
        query = urlencode(
            {
                "client_id": self._required(self.settings.google_client_id, "GOOGLE_CLIENT_ID"),
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": self.settings.oauth_scope,
                "state": state,
                "nonce": nonce,
                "access_type": "online",
            }
        )
        return f"{auth_uri}?{query}"

    def exchange_code_for_token(self, code: str) -> str:
        token_uri = "https://oauth2.googleapis.com/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": self._required(self.settings.google_client_id, "GOOGLE_CLIENT_ID"),
            "client_secret": self._required(self.settings.google_client_secret, "GOOGLE_CLIENT_SECRET"),
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
        except Exception as exc:
            raise ApiError("OAUTH_TOKEN_EXCHANGE_FAILED", "oauth token exchange failed: unexpected_error", 401) from exc
        if response.status_code != 200:
            logger.warning(
                "oauth token exchange upstream failure status=%s body_preview=%s",
                response.status_code,
                self._safe_body_preview(response),
            )
            raise ApiError(
                "OAUTH_TOKEN_EXCHANGE_FAILED",
                f"oauth token exchange failed: upstream_status={response.status_code}",
                401,
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise ApiError("OAUTH_TOKEN_EXCHANGE_FAILED", "oauth token exchange failed: invalid_json", 401) from exc
        id_token = body.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise ApiError("OAUTH_TOKEN_EXCHANGE_FAILED", "google id token missing", 401)
        return id_token

    def _safe_body_preview(self, response: httpx.Response) -> str:
        body = response.text or ""
        compact = " ".join(body.split())
        if len(compact) <= self._UPSTREAM_BODY_LOG_LIMIT:
            return compact
        return f"{compact[:self._UPSTREAM_BODY_LOG_LIMIT]}..."

    def fetch_identity(self, access_token: str, expected_nonce: str | None = None) -> OAuthIdentity:
        claims = self._verify_id_token(access_token, expected_nonce=expected_nonce)
        email = self._pick_claim(claims, "email").lower()
        if claims.get("email_verified") is not True:
            raise ApiError("OAUTH_IDENTITY_INVALID", "google email is not verified", 422)
        hosted_domain = self.settings.google_allowed_hosted_domain
        if hosted_domain and (
            claims.get("hd", "").lower() != hosted_domain.lower()
            or email.rsplit("@", 1)[-1] != hosted_domain.lower()
        ):
            raise ApiError("OAUTH_IDENTITY_INVALID", "google workspace domain is not allowed", 422)
        account = email.split("@", 1)[0]
        name = self._pick_claim(claims, "name")
        return OAuthIdentity(
            account=account,
            name=name,
            email=email,
            department="",
            sysid=0,
            tcode="",
            role="user",
        )

    def _verify_id_token(self, token: str, expected_nonce: str | None = None) -> dict:
        try:
            header_raw, payload_raw, signature_raw = token.split(".")
            header = json.loads(self._b64decode(header_raw))
            claims = json.loads(self._b64decode(payload_raw))
            signature = self._b64decode_bytes(signature_raw)
        except (ValueError, json.JSONDecodeError, TypeError) as exc:
            raise ApiError("OAUTH_IDENTITY_INVALID", "invalid google id token", 422) from exc
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise ApiError("OAUTH_IDENTITY_INVALID", "unsupported google id token", 422)
        now = int(time.time())
        if claims.get("iss") not in {"https://accounts.google.com", "accounts.google.com"}:
            raise ApiError("OAUTH_IDENTITY_INVALID", "invalid google issuer", 422)
        if claims.get("aud") != self._required(self.settings.google_client_id, "GOOGLE_CLIENT_ID"):
            raise ApiError("OAUTH_IDENTITY_INVALID", "invalid google audience", 422)
        if expected_nonce is not None and claims.get("nonce") != expected_nonce:
            raise ApiError("OAUTH_IDENTITY_INVALID", "invalid google nonce", 422)
        if not isinstance(claims.get("exp"), int) or claims["exp"] <= now:
            raise ApiError("OAUTH_IDENTITY_INVALID", "expired google id token", 422)
        if not isinstance(claims.get("iat"), int) or claims["iat"] > now + 60:
            raise ApiError("OAUTH_IDENTITY_INVALID", "invalid google id token time", 422)
        key = self._fetch_google_key(header["kid"])
        signing_input = f"{header_raw}.{payload_raw}".encode("ascii")
        try:
            key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
        except Exception as exc:
            raise ApiError("OAUTH_IDENTITY_INVALID", "invalid google id token signature", 422) from exc
        return claims

    def _fetch_google_key(self, kid: str) -> rsa.RSAPublicKey:
        try:
            with build_safe_httpx_client(timeout_seconds=10.0) as client:
                response = client.get("https://www.googleapis.com/oauth2/v3/certs")
        except httpx.TimeoutException as exc:
            raise ApiError("OAUTH_BASIC_FETCH_FAILED", "google signing keys unavailable: timeout", 401) from exc
        except httpx.HTTPError as exc:
            raise ApiError("OAUTH_BASIC_FETCH_FAILED", "google signing keys unavailable: network_error", 401) from exc
        except Exception as exc:
            raise ApiError("OAUTH_BASIC_FETCH_FAILED", "google signing keys unavailable", 401) from exc
        if response.status_code != 200:
            raise ApiError("OAUTH_BASIC_FETCH_FAILED", "google signing keys unavailable", 401)
        try:
            claims = response.json()
        except ValueError as exc:
            raise ApiError("OAUTH_BASIC_FETCH_FAILED", "google signing keys unavailable: invalid_json", 401) from exc
        for item in claims.get("keys", []):
            if item.get("kid") == kid and item.get("kty") == "RSA":
                try:
                    modulus = int.from_bytes(self._b64decode_bytes(item["n"]), "big")
                    exponent = int.from_bytes(self._b64decode_bytes(item["e"]), "big")
                    return rsa.RSAPublicNumbers(exponent, modulus).public_key()
                except (KeyError, ValueError) as exc:
                    break
        raise ApiError("OAUTH_IDENTITY_INVALID", "google signing key not found", 422)

    @staticmethod
    def _new_token() -> str:
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")

    @staticmethod
    def _b64decode_bytes(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    @classmethod
    def _b64decode(cls, value: str) -> str:
        return cls._b64decode_bytes(value).decode("utf-8")

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
