from dataclasses import dataclass

from app.core.config import get_settings
from app.services.persnl_soap_service import PersnlSoapService, PersnlSoapUnavailableError


def _normalize_title_code(value: str) -> str:
    return value.strip().upper()


@dataclass(slots=True)
class ResearchEligibilityResult:
    eligible: bool
    title_code: str | None


class ResearchEligibilityUnavailableError(RuntimeError):
    pass


class ResearchEligibilityService:
    def __init__(self) -> None:
        settings = get_settings()
        self.allowed_title_codes = {
            _normalize_title_code(code)
            for code in settings.login_allowed_title_codes.split(",")
            if code.strip()
        }
        self.persnl = PersnlSoapService()

    def is_configured(self) -> bool:
        return self.persnl.is_configured()

    def check_eligibility(self, *, email: str, sysid: int) -> ResearchEligibilityResult:
        del email  # Current SOAP query path resolves by sysid-based identity and tCode only.
        if not self.persnl.is_configured():
            return ResearchEligibilityResult(eligible=False, title_code=None)

        try:
            matches = self.persnl.search_person_by_sysid(sysid, on_job="1")
            if not matches:
                return ResearchEligibilityResult(eligible=False, title_code=None)
            title_code = str(matches[0].get("tCode", "")).strip()
        except PersnlSoapUnavailableError as exc:
            raise ResearchEligibilityUnavailableError("persnl soap unavailable") from exc

        normalized = _normalize_title_code(title_code) if title_code else None
        # Keep existing baseline rule: all B* titles are eligible; allowed list extends eligibility.
        if normalized and (normalized.startswith("B") or normalized in self.allowed_title_codes):
            return ResearchEligibilityResult(eligible=True, title_code=normalized)
        return ResearchEligibilityResult(eligible=False, title_code=None)
