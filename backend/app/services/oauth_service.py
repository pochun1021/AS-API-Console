from dataclasses import dataclass
import logging
import secrets

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from app.core.config import get_settings
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
    def __init__(self) -> None:
        self.settings = get_settings()

    def _required(self, value: str | None, key: str) -> str:
        if not value:
            raise ApiError("INTERNAL_ERROR", f"missing oauth config: {key}", 500)
        return value

    def _new_flow(self) -> Flow:
        filename = self._required(self.settings.google_client_secrets_file, "GOOGLE_CLIENT_SECRETS_FILE")
        try:
            flow = Flow.from_client_secrets_file(
                filename,
                scopes=self.settings.oauth_scope.split(),
                token_updater=self._discard_token_update,
            )
        except (OSError, ValueError, KeyError) as exc:
            raise ApiError("INTERNAL_ERROR", "invalid Google client secrets configuration", 500) from exc
        flow.redirect_uri = self.settings.oauth_redirect_uri
        return flow

    def build_login_url(self, request=None) -> str:
        flow = self._new_flow()
        state = self._new_token()
        nonce = self._new_token()
        if request is not None:
            request.session["oauth_state"] = state
            request.session["oauth_nonce"] = nonce
        authorization_url, _ = flow.authorization_url(
            access_type="online",
            include_granted_scopes="true",
            state=state,
            nonce=nonce,
        )
        if request is not None and flow.code_verifier:
            request.session["oauth_code_verifier"] = flow.code_verifier
        return authorization_url

    def exchange_code_for_token(self, code: str, code_verifier: str | None = None) -> str:
        if not code_verifier:
            raise ApiError("OAUTH_TOKEN_EXCHANGE_FAILED", "oauth code verifier missing", 401)
        flow = self._new_flow()
        flow.code_verifier = code_verifier
        try:
            flow.fetch_token(code=code)
            token = flow.credentials.id_token
        except Warning as exc:
            warning_token = getattr(exc, "token", None)
            token_keys = sorted(warning_token) if isinstance(warning_token, dict) else []
            token = warning_token.get("id_token") if isinstance(warning_token, dict) else None
            if isinstance(warning_token, dict) and isinstance(token, str) and token:
                flow.oauth2session.token = warning_token
                logger.info(
                    "google oauth token exchange accepted normalized scopes old_scopes=%s new_scopes=%s token_keys=%s",
                    getattr(exc, "old_scope", "unknown"),
                    getattr(exc, "new_scope", "unknown"),
                    token_keys,
                )
            else:
                logger.exception(
                    "google oauth token exchange warning did not contain usable id token token_keys=%s",
                    token_keys,
                )
                raise ApiError("OAUTH_TOKEN_EXCHANGE_FAILED", "oauth token exchange failed", 401) from exc
        except Exception as exc:
            provider_error = getattr(exc, "error", None)
            provider_description = getattr(exc, "description", None)
            updated_token = getattr(exc, "token", None)
            updated_token_keys = sorted(updated_token) if isinstance(updated_token, dict) else []
            logger.exception(
                "google oauth token exchange failed exception_type=%s provider_error=%s provider_description=%s token_keys=%s",
                type(exc).__name__,
                provider_error if isinstance(provider_error, str) else "unknown",
                provider_description if isinstance(provider_description, str) else "unknown",
                updated_token_keys,
            )
            raise ApiError("OAUTH_TOKEN_EXCHANGE_FAILED", "oauth token exchange failed", 401) from exc
        if not isinstance(token, str) or not token:
            raise ApiError("OAUTH_TOKEN_EXCHANGE_FAILED", "google id token missing", 401)
        return token

    @staticmethod
    def _discard_token_update(token: dict) -> None:
        """Prevent requests-oauthlib TokenUpdated warnings without persisting tokens."""
        logger.debug("google oauth token update received keys=%s", sorted(token))

    def fetch_identity(self, id_token_value: str, expected_nonce: str | None = None) -> OAuthIdentity:
        client_id = self._client_id()
        try:
            claims = id_token.verify_oauth2_token(
                id_token_value,
                GoogleRequest(),
                audience=client_id,
            )
        except Exception as exc:
            raise ApiError("OAUTH_IDENTITY_INVALID", "invalid Google ID token", 422) from exc
        if not isinstance(claims, dict):
            raise ApiError("OAUTH_IDENTITY_INVALID", "invalid Google ID token", 422)

        if expected_nonce is not None and claims.get("nonce") != expected_nonce:
            raise ApiError("OAUTH_IDENTITY_INVALID", "invalid google nonce", 422)
        email = self._pick_claim(claims, "email").lower()
        if claims.get("email_verified") is not True:
            raise ApiError("OAUTH_IDENTITY_INVALID", "google email is not verified", 422)
        hosted_domain = self.settings.google_allowed_hosted_domain
        if hosted_domain and (
            claims.get("hd", "").lower() != hosted_domain.lower()
            or email.rsplit("@", 1)[-1] != hosted_domain.lower()
        ):
            raise ApiError("OAUTH_IDENTITY_INVALID", "google workspace domain is not allowed", 422)
        return OAuthIdentity(
            account=email.split("@", 1)[0],
            name=self._pick_claim(claims, "name"),
            email=email,
            department="",
            sysid=0,
            tcode="",
            role="user",
        )

    def _client_id(self) -> str:
        client_id = self._new_flow().client_config.get("client_id")
        return self._required(client_id, "GOOGLE_CLIENT_ID")

    @staticmethod
    def _new_token() -> str:
        return secrets.token_urlsafe(32)

    def _pick_claim(self, claims: dict, *keys: str) -> str:
        for key in keys:
            value = claims.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise ApiError("OAUTH_IDENTITY_INVALID", f"missing required oauth claim: {'|'.join(keys)}", 422)
