import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.core.errors import ApiError
from app.services.crypto_service import CryptoService
from app.services.research_eligibility_service import ResearchEligibilityService
from db.repositories.types import ApiKeyCreateInput, ApplicationCreateInput, AuthIdentity
from db.repositories import SQLAlchemyApiKeyRepository, SQLAlchemyUserRepository, SQLAlchemyWhitelistRepository


@dataclass(slots=True)
class Pagination:
    page: int = 1
    page_size: int = 20


def _generate_api_key() -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    suffix = "".join(secrets.choice(alphabet) for _ in range(30))
    return f"AS-{suffix}"


def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _mask_key(plaintext: str) -> str:
    return f"AS-...{plaintext[-4:]}"


def _calc_expiration(issued_at: datetime, duration_months: int) -> datetime:
    # MVP constraint guarantees 1/6/12 only; keep simple month offset without external libs
    month = issued_at.month - 1 + duration_months
    year = issued_at.year + month // 12
    month = month % 12 + 1
    day = min(issued_at.day, 28)
    return issued_at.replace(year=year, month=month, day=day)


class ApiKeysService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.user_repo = SQLAlchemyUserRepository(session)
        self.whitelist_repo = SQLAlchemyWhitelistRepository(session)
        self.key_repo = SQLAlchemyApiKeyRepository(session)
        self.research_eligibility = ResearchEligibilityService()
        self.crypto = CryptoService(self.settings.api_key_encryption_secret)

    def create_application(self, current_user: CurrentUser, application_date: date, duration_months: int, purpose: str) -> dict:
        if application_date > date.today():
            raise ApiError("INVALID_APPLICATION_DATE", "application_date cannot be in the future", 422)
        if duration_months not in {1, 6, 12}:
            raise ApiError("INVALID_DURATION_MONTHS", "duration_months must be one of 1, 6, 12", 422)

        research_eligible = False
        if self.research_eligibility.is_configured():
            try:
                result = self.research_eligibility.check_eligibility(
                    email=current_user.email,
                    sysid=current_user.sysid,
                )
                research_eligible = result.eligible
            except RuntimeError as exc:
                raise ApiError(
                    "RESEARCH_LIST_SERVICE_UNAVAILABLE",
                    "research list service unavailable",
                    503,
                ) from exc

        whitelist_eligible = self.whitelist_repo.find_active_by_email(current_user.email) is not None
        if not research_eligible and not whitelist_eligible:
            raise ApiError("APPLICANT_NOT_ELIGIBLE", "applicant is not eligible", 403)

        identity = AuthIdentity(
            account=current_user.account,
            name=current_user.name,
            email=current_user.email,
            department=current_user.department,
            sysid=current_user.sysid,
        )
        user = self.user_repo.upsert_from_auth(identity)

        issued_at = datetime.now(UTC)
        expires_at = _calc_expiration(issued_at, duration_months)
        application = self.key_repo.create_application(
            ApplicationCreateInput(
                user_id=user.id,
                identity=identity,
                application_date=application_date,
                duration_months=duration_months,
                purpose=purpose,
                issued_at=issued_at,
                expires_at=expires_at,
            )
        )

        plaintext = _generate_api_key()
        self.key_repo.create_key(
            ApiKeyCreateInput(
                application_id=application.id,
                key_hash=_hash_key(plaintext),
                masked_key=_mask_key(plaintext),
                key_ciphertext=self.crypto.encrypt(plaintext),
                key_kek_version=self.settings.api_key_kek_version,
            )
        )
        self.session.commit()

        return {
            "application": {
                "id": application.id,
                "account": application.account,
                "status": application.status,
                "issued_at": application.issued_at,
                "expires_at": application.expires_at,
            },
            "api_key_plaintext": plaintext,
        }

    def list_keys(self, current_user: CurrentUser, page: int, page_size: int, status: str | None = None) -> dict:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        offset = (page - 1) * page_size

        items = self.key_repo.list_keys(
            requester_role=current_user.role,
            requester_account=current_user.account,
            status=status,
            limit=page_size,
            offset=offset,
        )

        return {
            "items": [
                {
                    "id": item.id,
                    "status": item.status,
                    "masked_key": item.masked_key,
                    "application_date": item.application_date,
                    "duration_months": item.duration_months,
                    "owner_account": item.owner_account,
                    "owner_name": item.owner_name,
                    "expires_at": item.expires_at,
                }
                for item in items
            ],
            "page": page,
            "page_size": page_size,
            "total": len(items),
        }

    def get_key_detail(self, current_user: CurrentUser, key_id: str) -> dict:
        detail = self.key_repo.get_key_detail(key_id, "admin", current_user.account)
        if detail is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)

        scoped = self.key_repo.get_key_detail(key_id, current_user.role, current_user.account)
        if scoped is None:
            raise ApiError("KEY_NOT_OWNED_BY_USER", "key is not owned by requester", 403)

        return {
            "id": scoped.id,
            "status": scoped.status,
            "masked_key": scoped.masked_key,
            "owner_account": scoped.owner_account,
            "owner_name": scoped.owner_name,
            "purpose": scoped.purpose,
            "department": scoped.department,
            "application_date": scoped.application_date,
            "duration_months": scoped.duration_months,
            "created_at": scoped.created_at,
            "expires_at": scoped.expires_at,
        }

    def revoke_key(self, current_user: CurrentUser, key_id: str) -> dict:
        exists = self.key_repo.get_key_detail(key_id, "admin", current_user.account)
        if exists is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)

        allowed = self.key_repo.get_key_detail(key_id, current_user.role, current_user.account)
        if allowed is None:
            raise ApiError("KEY_NOT_OWNED_BY_USER", "key is not owned by requester", 403)

        key = self.key_repo.revoke_key(key_id, current_user.role, current_user.account)
        if key is None:
            raise ApiError("KEY_NOT_ACTIVE", "key is not active", 409)

        self.session.commit()
        return {"id": key.id, "status": key.status}

    def reveal_key_plaintext(self, current_user: CurrentUser, key_id: str) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)

        material = self.key_repo.get_key_secret_material(key_id, current_user.role, current_user.account)
        if material is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)
        if not material.key_ciphertext or not material.key_kek_version:
            raise ApiError("KEY_NOT_REVEALABLE", "key plaintext is not available", 409)

        plaintext = self.crypto.decrypt(material.key_ciphertext)
        return {
            "id": material.id,
            "api_key_plaintext": plaintext,
            "key_kek_version": material.key_kek_version,
        }

    def list_user_statistics(
        self,
        *,
        current_user: CurrentUser,
        page: int,
        page_size: int,
        q: str | None = None,
        scope: str = "all",
        from_date: date | None = None,
        to_date: date | None = None,
        sort_by: str = "total_applications",
        sort_dir: str = "desc",
    ) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)

        allowed_scopes = {"all", "active", "revoked", "expired"}
        if scope not in allowed_scopes:
            raise ApiError("VALIDATION_ERROR", "scope must be one of all, active, revoked, expired", 422)

        if sort_dir not in {"asc", "desc"}:
            raise ApiError("VALIDATION_ERROR", "sort_dir must be asc or desc", 422)

        if from_date is not None and to_date is not None and from_date > to_date:
            raise ApiError("VALIDATION_ERROR", "from cannot be greater than to", 422)

        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        offset = (page - 1) * page_size

        items, total = self.key_repo.list_user_statistics(
            scope=scope,
            q=q.strip() if q else None,
            from_date=from_date,
            to_date=to_date,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=page_size,
            offset=offset,
        )

        return {
            "items": [
                {
                    "owner_account": item.owner_account,
                    "owner_name": item.owner_name,
                    "owner_email": item.owner_email,
                    "owner_department": item.owner_department,
                    "total_applications": item.total_applications,
                    "active_count": item.active_count,
                    "revoked_count": item.revoked_count,
                    "expired_count": item.expired_count,
                    "last_applied_at": item.last_applied_at,
                }
                for item in items
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
