"""Reusable pre-session login gate; not wired into the current OAuth callback."""

from collections.abc import MutableMapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from app.services.datahub_client import DataHubError
from app.services.training_eligibility_service import TrainingEligibilityService


TRAINING_INCOMPLETE_MESSAGE = "未完成時數訓練，請確認完成後方可登入系統"
TRAINING_UNAVAILABLE_MESSAGE = "暫時無法驗證未完訓資格，請稍後再試"


class GateStatus(StrEnum):
    ALLOWED = "allowed"
    TRAINING_INCOMPLETE = "training_incomplete"
    LOGIN_NOT_ELIGIBLE = "login_not_eligible"
    SERVICE_UNAVAILABLE = "service_unavailable"


@dataclass(frozen=True, slots=True)
class GateResult:
    status: GateStatus
    message: str | None = None


class ExistingEligibility(Protocol):
    def is_eligible(self, *, sysid: int, tcode: str) -> bool: ...


class AuthAuditSink(Protocol):
    def log(
        self,
        *,
        provider: str,
        request_id: str,
        result: str,
        error_code: str,
        detail: str | None = None,
    ) -> None: ...


class LoginQualificationGate:
    def __init__(
        self,
        *,
        training: TrainingEligibilityService,
        existing: ExistingEligibility,
        audit: AuthAuditSink,
    ) -> None:
        self.training = training
        self.existing = existing
        self.audit = audit

    def evaluate(
        self,
        *,
        trusted_sso: str,
        sysid: int,
        tcode: str,
        session: MutableMapping[str, Any],
        provider: str,
        request_id: str,
    ) -> GateResult:
        # A prior login must never survive a rejected fresh login attempt.
        session.pop("auth_context", None)
        session.pop("csrf_token", None)
        try:
            incomplete = self.training.is_incomplete(trusted_sso=trusted_sso)
        except ValueError:
            return self._reject(provider, request_id, "TRAINING_IDENTITY_UNAVAILABLE", "identity")
        except DataHubError as exc:
            return self._reject(provider, request_id, "TRAINING_SERVICE_UNAVAILABLE", exc.kind.value)
        except Exception:
            return self._reject(provider, request_id, "TRAINING_SERVICE_UNAVAILABLE", "unexpected")

        if incomplete:
            return self._reject(provider, request_id, "TRAINING_INCOMPLETE", None)

        try:
            eligible = self.existing.is_eligible(sysid=sysid, tcode=tcode)
        except Exception:
            return self._reject(provider, request_id, "LOGIN_ELIGIBILITY_UNAVAILABLE", "eligibility")
        if not eligible:
            return self._reject(provider, request_id, "LOGIN_NOT_ELIGIBLE", None)
        return GateResult(GateStatus.ALLOWED)

    def _reject(
        self,
        provider: str,
        request_id: str,
        error_code: str,
        detail: str | None,
    ) -> GateResult:
        try:
            self.audit.log(
                provider=provider,
                request_id=request_id,
                result="failure",
                error_code=error_code,
                detail=detail,
            )
        except Exception:
            return GateResult(GateStatus.SERVICE_UNAVAILABLE, TRAINING_UNAVAILABLE_MESSAGE)
        if error_code == "TRAINING_INCOMPLETE":
            return GateResult(GateStatus.TRAINING_INCOMPLETE, TRAINING_INCOMPLETE_MESSAGE)
        if error_code == "LOGIN_NOT_ELIGIBLE":
            return GateResult(GateStatus.LOGIN_NOT_ELIGIBLE)
        return GateResult(GateStatus.SERVICE_UNAVAILABLE, TRAINING_UNAVAILABLE_MESSAGE)
