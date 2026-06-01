from app.core.config import get_settings
from db.repositories import SQLAlchemyAdminRepository, SQLAlchemyWhitelistRepository


def _normalize_code(value: str) -> str:
    return value.strip().upper()


class LoginEligibilityService:
    def __init__(
        self,
        whitelist_repo: SQLAlchemyWhitelistRepository,
        admin_repo: SQLAlchemyAdminRepository,
    ) -> None:
        self.whitelist_repo = whitelist_repo
        self.admin_repo = admin_repo
        settings = get_settings()
        self.allowed_title_codes = {
            _normalize_code(code)
            for code in settings.login_allowed_title_codes.split(",")
            if code.strip()
        }

    def is_eligible(self, *, sysid: int, tcode: str) -> bool:
        return self.is_eligible_by_sysid(sysid) or self.is_allowed_by_tcode(tcode)

    def is_eligible_by_sysid(self, sysid: int) -> bool:
        if self.whitelist_repo.find_active_by_sysid(sysid) is not None:
            return True
        return self.admin_repo.get_active_by_id(sysid) is not None

    def is_allowed_by_tcode(self, tcode: str) -> bool:
        return _normalize_code(tcode) in self.allowed_title_codes
