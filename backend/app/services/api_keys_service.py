import hashlib
import logging
import secrets
from asyncio import run as run_async
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.core.errors import ApiError
from app.services.crypto_service import CryptoService
from app.services.mail_service import MailService
from app.services.provider_client import ProviderBadRequestError, ProviderClient, ProviderUnavailableError
from app.services.research_eligibility_service import ResearchEligibilityService
from db.models.applications import ApiKeyApplication
from db.models.api_keys import ApiKey
from db.models.limit_strategy_config import LimitStrategyConfig
from db.repositories import SQLAlchemyAdminRepository, SQLAlchemyApiKeyRepository, SQLAlchemyWhitelistRepository
from db.repositories.types import ApiKeyAliasUpdateInput, ApiKeyCreateInput, ApiKeyListFilter, ApplicationCreateInput, AuthIdentity


@dataclass(slots=True)
class Pagination:
    page: int = 1
    page_size: int = 20


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


def _default_alias(owner_account: str) -> str:
    return f"for_{owner_account}"


class ApiKeysService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.admin_repo = SQLAlchemyAdminRepository(session)
        self.whitelist_repo = SQLAlchemyWhitelistRepository(session)
        self.key_repo = SQLAlchemyApiKeyRepository(session)
        self.research_eligibility = ResearchEligibilityService()
        self.provider_client = ProviderClient()
        self.crypto = CryptoService(self.settings.api_key_encryption_secret)
        self.mail_service = MailService()

    def create_application(
        self,
        current_user: CurrentUser,
        application_date: date,
        duration_months: int,
        purpose: str,
    ) -> dict:
        if application_date > date.today():
            raise ApiError("INVALID_APPLICATION_DATE", "application_date cannot be in the future", 422)
        if duration_months not in {1, 6, 12}:
            raise ApiError("INVALID_DURATION_MONTHS", "duration_months must be one of 1, 6, 12", 422)
        normalized_purpose = purpose.strip()
        if not normalized_purpose:
            raise ApiError("VALIDATION_ERROR", "purpose is required", 422)

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
        issued_at = datetime.now(UTC)
        expires_at = _calc_expiration(issued_at, duration_months)
        application = self.key_repo.create_application(
            ApplicationCreateInput(
                user_id=current_user.sysid,
                identity=identity,
                application_date=application_date,
                duration_months=duration_months,
                purpose=normalized_purpose,
                limit_strategy="",
                max_budget=None,
                budget_duration=None,
                tpm_limit=None,
                rpm_limit=None,
                issuance_status="pending",
                pending_issued_at=None,
                issued_at=issued_at,
                expires_at=expires_at,
            )
        )
        application.selected_issuance_mode = None
        self.session.add(application)
        self.session.commit()
        self._send_application_received_emails(application)

        return {
            "application": {
                "id": application.id,
                "account": application.account,
                "status": application.status,
                "issued_at": application.issued_at,
                "expires_at": application.expires_at,
            },
            "issuance_status": "pending",
            "api_key_plaintext": None,
            "pending_reason": "awaiting_admin_mode_selection",
        }

    def _send_application_received_emails(self, application: ApiKeyApplication) -> None:
        try:
            active_admin_emails = self.admin_repo.list_active_emails()
            run_async(
                self.mail_service.send_application_received_to_admins(
                    recipients=active_admin_emails,
                    application_id=application.id,
                    applicant_account=application.account,
                    applicant_name=application.name,
                    applicant_email=application.email,
                    applicant_department=application.department,
                    application_date=str(application.application_date),
                    duration_months=application.duration_months,
                    purpose=application.purpose,
                    app_domain=self.settings.app_domain,
                )
            )
        except Exception:  # noqa: BLE001
            logging.exception("failed to send application received email to admins")

        try:
            run_async(
                self.mail_service.send_application_received_to_applicant(
                    to_email=application.email,
                    owner_name=application.name,
                    application_id=application.id,
                    app_domain=self.settings.app_domain,
                )
            )
        except Exception:  # noqa: BLE001
            logging.exception("failed to send application received email to applicant")

    def list_pending_applications(self, current_user: CurrentUser) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)
        stmt = (
            self.session.query(ApiKeyApplication)
            .filter(ApiKeyApplication.issuance_status == "pending")
            .order_by(ApiKeyApplication.created_at.desc())
        )
        items = stmt.all()
        return {
            "items": [
                {
                    "id": app.id,
                    "account": app.account,
                    "name": app.name,
                    "email": app.email,
                    "department": app.department,
                    "purpose": app.purpose,
                    "application_date": app.application_date,
                    "duration_months": app.duration_months,
                    "selected_issuance_mode": app.selected_issuance_mode,
                    "created_at": app.created_at,
                }
                for app in items
            ],
            "total": len(items),
        }

    def update_pending_application_mode(self, current_user: CurrentUser, application_id: str, mode: str) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)
        if mode not in {"budget", "rate_limit"}:
            raise ApiError("ISSUANCE_MODE_INVALID", "mode must be budget or rate_limit", 422)
        application = self.session.get(ApiKeyApplication, application_id)
        if application is None:
            raise ApiError("VALIDATION_ERROR", "application not found", 404)
        if application.issuance_status != "pending":
            raise ApiError("APPLICATION_NOT_PENDING", "application is not pending", 409)
        application.selected_issuance_mode = mode
        application.updated_at = datetime.now(UTC)
        self.session.add(application)
        self.session.commit()
        return {"id": application.id, "selected_issuance_mode": mode, "issuance_status": application.issuance_status}

    def issue_pending_application(self, current_user: CurrentUser, application_id: str) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)
        application = self.session.get(ApiKeyApplication, application_id)
        if application is None:
            raise ApiError("VALIDATION_ERROR", "application not found", 404)
        if application.issuance_status == "issued":
            raise ApiError("APPLICATION_ALREADY_ISSUED", "application already issued", 409)
        if application.issuance_status != "pending":
            raise ApiError("APPLICATION_NOT_PENDING", "application is not pending", 409)
        if application.selected_issuance_mode not in {"budget", "rate_limit"}:
            raise ApiError("ISSUANCE_MODE_REQUIRED", "issuance mode is required", 409)

        plaintext = self._issue_application(application)
        self.session.commit()
        return {
            "application": {
                "id": application.id,
                "account": application.account,
                "status": application.status,
                "issued_at": application.issued_at,
                "expires_at": application.expires_at,
            },
            "issuance_status": application.issuance_status,
            "api_key_plaintext": plaintext,
            "pending_reason": "provider_unavailable" if application.issuance_status == "pending" else None,
        }

    def _issue_application(self, application: ApiKeyApplication) -> str | None:
        mode = application.selected_issuance_mode
        if mode not in {"budget", "rate_limit"}:
            raise ApiError("ISSUANCE_MODE_REQUIRED", "issuance mode is required", 409)
        config = self._get_or_create_limit_strategy_config()
        if mode == "budget":
            max_budget = (config.budget_max_budget or "").strip()
            budget_duration = (config.budget_duration or "").strip()
            tpm_limit = None
            rpm_limit = None
            if not max_budget or not budget_duration:
                raise ApiError("ISSUANCE_CONFIG_INCOMPLETE", "budget config is incomplete", 409)
        else:
            max_budget = None
            budget_duration = None
            tpm_limit = config.rate_limit_tpm
            rpm_limit = config.rate_limit_rpm
            if not tpm_limit or not rpm_limit or int(tpm_limit) <= 0 or int(rpm_limit) <= 0:
                raise ApiError("ISSUANCE_CONFIG_INCOMPLETE", "rate limit config is incomplete", 409)
        application.limit_strategy = mode
        application.max_budget = max_budget
        application.budget_duration = budget_duration
        application.tpm_limit = tpm_limit
        application.rpm_limit = rpm_limit

        plaintext: str | None = None
        try:
            if self.provider_client.is_configured():
                provider_result = self.provider_client.generate_key(
                    {
                        "account": application.account,
                        "application_id": application.id,
                        "duration_months": application.duration_months,
                        "purpose": application.purpose,
                        "limit_strategy": mode,
                        "max_budget": max_budget,
                        "budget_duration": budget_duration,
                        "tpm_limit": tpm_limit,
                        "rpm_limit": rpm_limit,
                    }
                )
                plaintext = provider_result.key_plaintext
            else:
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
            application.issuance_status = "issued"
            application.pending_issued_at = datetime.now(UTC)
        except ProviderBadRequestError as exc:
            raise ApiError("VALIDATION_ERROR", str(exc), 422) from exc
        except ProviderUnavailableError:
            application.issuance_status = "pending"
            plaintext = None
        application.updated_at = datetime.now(UTC)
        self.session.add(application)
        return plaintext

    def get_limit_strategy_config(self, current_user: CurrentUser) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)
        config = self._get_or_create_limit_strategy_config()
        return {
            "budget_max_budget": config.budget_max_budget,
            "budget_duration": config.budget_duration,
            "rate_limit_tpm": config.rate_limit_tpm,
            "rate_limit_rpm": config.rate_limit_rpm,
        }

    def update_limit_strategy_config(self, current_user: CurrentUser, payload: dict) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)
        budget_max_budget = str(payload.get("budget_max_budget") or "").strip()
        budget_duration = str(payload.get("budget_duration") or "").strip()
        rate_limit_tpm = int(payload.get("rate_limit_tpm") or 0)
        rate_limit_rpm = int(payload.get("rate_limit_rpm") or 0)
        if not budget_max_budget or not budget_duration:
            raise ApiError("MISSING_BUDGET_FIELDS", "budget config is required", 422)
        if rate_limit_tpm <= 0 or rate_limit_rpm <= 0:
            raise ApiError("MISSING_RATE_LIMIT_FIELDS", "rate limit config is required", 422)
        config = self._get_or_create_limit_strategy_config()
        config.budget_max_budget = budget_max_budget
        config.budget_duration = budget_duration
        config.rate_limit_tpm = rate_limit_tpm
        config.rate_limit_rpm = rate_limit_rpm
        config.updated_at = datetime.now(UTC)
        self.session.add(config)
        self.session.commit()
        return {
            "budget_max_budget": config.budget_max_budget,
            "budget_duration": config.budget_duration,
            "rate_limit_tpm": config.rate_limit_tpm,
            "rate_limit_rpm": config.rate_limit_rpm,
        }

    def _get_or_create_limit_strategy_config(self) -> LimitStrategyConfig:
        config = self.session.get(LimitStrategyConfig, "global-limit-strategy-config")
        if config is not None:
            return config
        now = datetime.now(UTC)
        config = LimitStrategyConfig(
            id="global-limit-strategy-config",
            budget_max_budget="1000",
            budget_duration="monthly",
            rate_limit_tpm=10000,
            rate_limit_rpm=500,
            created_at=now,
            updated_at=now,
        )
        self.session.add(config)
        self.session.flush()
        return config

    def list_keys(
        self,
        current_user: CurrentUser,
        page: int,
        page_size: int,
        status: str | None = None,
        owner_account: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        offset = (page - 1) * page_size

        normalized_owner_account = owner_account.strip() if owner_account else None
        if current_user.role != "admin":
            normalized_owner_account = None

        items = self.key_repo.list_keys(
            requester_role=current_user.role,
            requester_account=current_user.account,
            filters=ApiKeyListFilter(
                status=status,
                owner_account=normalized_owner_account or None,
                from_date=from_date,
                to_date=to_date,
            ),
            limit=page_size,
            offset=offset,
        )

        return {
            "items": [
                {
                    "id": item.id,
                    "status": item.status,
                    "masked_key": item.masked_key,
                    "key_alias": item.key_alias or _default_alias(item.owner_account),
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
            "key_alias": scoped.key_alias or _default_alias(scoped.owner_account),
            "owner_account": scoped.owner_account,
            "owner_name": scoped.owner_name,
            "purpose": scoped.purpose,
            "department": scoped.department,
            "application_date": scoped.application_date,
            "duration_months": scoped.duration_months,
            "created_at": scoped.created_at,
            "expires_at": scoped.expires_at,
        }

    def update_key_alias(self, current_user: CurrentUser, key_id: str, key_alias: str) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)

        normalized_alias = key_alias.strip()
        if not normalized_alias:
            raise ApiError("VALIDATION_ERROR", "key_alias cannot be empty", 422)

        exists = self.key_repo.get_key_detail(key_id, "admin", current_user.account)
        if exists is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)

        updated = self.key_repo.update_key_alias(
            key_id,
            current_user.role,
            current_user.account,
            ApiKeyAliasUpdateInput(key_alias=normalized_alias),
        )
        if updated is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)

        self.session.commit()
        return {
            "id": updated.id,
            "status": updated.status,
            "masked_key": updated.masked_key,
            "key_alias": updated.key_alias or _default_alias(updated.owner_account),
            "owner_account": updated.owner_account,
            "owner_name": updated.owner_name,
            "purpose": updated.purpose,
            "department": updated.department,
            "application_date": updated.application_date,
            "duration_months": updated.duration_months,
            "created_at": updated.created_at,
            "expires_at": updated.expires_at,
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
def _generate_api_key() -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    suffix = "".join(secrets.choice(alphabet) for _ in range(30))
    return f"AS-{suffix}"
