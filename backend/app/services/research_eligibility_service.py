from dataclasses import dataclass

import httpx

from app.core.config import get_settings


def _normalize_title_code(value: str) -> str:
    return value.strip().upper()


@dataclass(slots=True)
class ResearchEligibilityResult:
    eligible: bool
    title_code: str | None


class ResearchEligibilityService:
    def __init__(self) -> None:
        settings = get_settings()
        self.api_url = settings.research_list_api_url
        self.timeout_seconds = settings.research_list_timeout_seconds
        self.allowed_title_codes = {
            _normalize_title_code(code)
            for code in settings.research_list_allowed_title_codes.split(",")
            if code.strip()
        }

    def is_configured(self) -> bool:
        return bool(self.api_url)

    def check_eligibility(self, *, email: str, sysid: str) -> ResearchEligibilityResult:
        if not self.api_url:
            return ResearchEligibilityResult(eligible=False, title_code=None)

        try:
            response = httpx.get(
                self.api_url,
                params={"email": email, "sysid": sysid},
                timeout=self.timeout_seconds,
            )
        except httpx.RequestError as exc:
            raise RuntimeError("research list service request failed") from exc

        if response.status_code >= 500:
            raise RuntimeError("research list service unavailable")

        if response.status_code == 404:
            return ResearchEligibilityResult(eligible=False, title_code=None)

        if response.status_code >= 400:
            raise RuntimeError("research list service unavailable")

        payload = response.json()
        if bool(payload.get("eligible")):
            return ResearchEligibilityResult(eligible=True, title_code=None)

        title_code = payload.get("title_code")
        if isinstance(title_code, str):
            normalized = _normalize_title_code(title_code)
            return ResearchEligibilityResult(
                eligible=normalized in self.allowed_title_codes,
                title_code=normalized,
            )

        return ResearchEligibilityResult(eligible=False, title_code=None)
