"""Fail-closed DataHub access. The list endpoint contract awaits confirmation."""

from enum import StrEnum

import httpx

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.outbound import validate_outbound_url


class DataHubErrorKind(StrEnum):
    CONFIGURATION = "configuration"
    TIMEOUT = "timeout"
    NETWORK = "network"
    AUTHORIZATION = "authorization"
    HTTP = "http"
    SERVICE = "service"
    SCHEMA = "schema"


class DataHubError(RuntimeError):
    def __init__(self, kind: DataHubErrorKind) -> None:
        self.kind = kind
        super().__init__(kind.value)


class DataHubClient:
    """Return only SSO identifiers; never retain or log the response or token."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    def fetch_incomplete_sso(self) -> frozenset[str]:
        settings = self.settings
        token_url = self._url(settings.datahub_token_url, "DATAHUB_TOKEN_URL")
        list_url = self._url(settings.datahub_list_url, "DATAHUB_LIST_URL")
        client_id = self._required(settings.datahub_client_id)
        client_secret = self._required(settings.datahub_client_secret)
        method = (settings.datahub_list_method or "").upper()
        if method not in {"GET", "POST"} or settings.datahub_timeout_seconds <= 0:
            raise DataHubError(DataHubErrorKind.CONFIGURATION)

        form = {
            "systemName": "opendatacenter",
            "user": client_id,
            "action": "GET",
            "object": "/read/notfinish.json",
        }
        with httpx.Client(
            timeout=settings.datahub_timeout_seconds,
            follow_redirects=False,
            transport=self.transport,
        ) as client:
            token_response = self._request(
                client,
                "POST",
                token_url,
                json={"clientId": client_id, "clientSecret": client_secret},
            )
            token_payload = self._json(token_response)
            if isinstance(token_payload, dict) and "errMsg" in token_payload:
                raise DataHubError(DataHubErrorKind.SERVICE)
            if not isinstance(token_payload, dict) or not isinstance(token_payload.get("accessToken"), str):
                raise DataHubError(DataHubErrorKind.SCHEMA)
            token = token_payload["accessToken"]
            if not token.strip():
                raise DataHubError(DataHubErrorKind.SCHEMA)
            list_response = self._request(
                client,
                method,
                list_url,
                headers={"Authorization": f"Bearer {token}"},
                data=form,
            )
            payload = self._json(list_response)

        if isinstance(payload, dict) and "errMsg" in payload:
            raise DataHubError(DataHubErrorKind.SERVICE)
        if not isinstance(payload, list):
            raise DataHubError(DataHubErrorKind.SCHEMA)
        required = ("sso", "name", "phone", "email", "instName")
        identifiers: set[str] = set()
        for item in payload:
            if not isinstance(item, dict) or any(not isinstance(item.get(key), str) for key in required):
                raise DataHubError(DataHubErrorKind.SCHEMA)
            if not item["sso"] or not item["sso"].strip():
                raise DataHubError(DataHubErrorKind.SCHEMA)
            identifiers.add(item["sso"])
        return frozenset(identifiers)

    @staticmethod
    def _required(value: str | None) -> str:
        if not value or not value.strip():
            raise DataHubError(DataHubErrorKind.CONFIGURATION)
        return value

    @staticmethod
    def _url(value: str | None, name: str) -> str:
        try:
            return validate_outbound_url(value, config_name=name)
        except (ApiError, OSError) as exc:
            raise DataHubError(DataHubErrorKind.CONFIGURATION) from exc

    @staticmethod
    def _request(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            response = client.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise DataHubError(DataHubErrorKind.TIMEOUT) from exc
        except httpx.RequestError as exc:
            raise DataHubError(DataHubErrorKind.NETWORK) from exc
        if response.status_code in {401, 403}:
            raise DataHubError(DataHubErrorKind.AUTHORIZATION)
        if not 200 <= response.status_code < 300:
            raise DataHubError(DataHubErrorKind.HTTP)
        return response

    @staticmethod
    def _json(response: httpx.Response) -> object:
        try:
            return response.json()
        except ValueError as exc:
            raise DataHubError(DataHubErrorKind.SCHEMA) from exc
