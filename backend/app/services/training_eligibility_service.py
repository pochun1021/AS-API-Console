"""Training qualification uses a trusted SSO string without normalization."""

from typing import Protocol

from app.services.datahub_client import DataHubClient


class IncompleteSsoSource(Protocol):
    def fetch_incomplete_sso(self) -> frozenset[str]: ...


class TrainingEligibilityService:
    def __init__(self, client: IncompleteSsoSource | None = None) -> None:
        self.client = client or DataHubClient()

    def is_incomplete(self, *, trusted_sso: str) -> bool:
        if not isinstance(trusted_sso, str) or not trusted_sso or not trusted_sso.strip():
            raise ValueError("trusted sso string required")
        return trusted_sso in self.client.fetch_incomplete_sso()
