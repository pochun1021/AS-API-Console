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
from app.services.directory_identity_service import (
    DirectoryIdentityService,
    DirectoryLookupNotFoundError,
    DirectoryLookupNotUniqueError,
    DirectoryLookupUnavailableError,
)
from app.services.login_eligibility_service import LoginEligibilityService
from app.services.mail_service import MailService
from app.services.persnl_soap_service import PersnlSoapService, PersnlSoapUnavailableError
from app.services.provider_client import ProviderBadRequestError, ProviderClient, ProviderUnavailableError
from db.models.applications import ApiKeyApplication
from db.models.api_keys import ApiKey
from db.models.limit_strategy_config import LimitStrategyConfig
from db.repositories import SQLAlchemyAdminRepository, SQLAlchemyApiKeyRepository, SQLAlchemyWhitelistRepository
from db.repositories.types import ApiKeyAliasUpdateInput, ApiKeyCreateInput, ApiKeyListFilter, ApplicationCreateInput, AuthIdentity

LIMIT_STRATEGY_CONFIG_ID = "global-limit-strategy-config"
LIMIT_STRATEGY_DEFAULTS = {
    "budget_max_budget": "1000",
    "budget_duration": "monthly",
    "rate_limit_tpm": 10000,
    "rate_limit_rpm": 500,
}


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


def _to_provider_budget_duration(duration: str) -> str:
    normalized = duration.strip().lower()
    if normalized == "daily":
        return "1d"
    if normalized == "weekly":
        return "7d"
    if normalized == "monthly":
        return "30d"
    return normalized


def _effective_status(*, status: str, expires_at: datetime) -> str:
    expires_at_utc = expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=UTC)
    if status == "active" and expires_at_utc < datetime.now(UTC):
        return "expired"
    return status


def _is_extend_eligible(
    *,
    role: str,
    status: str,
    expiration_notice_sent_at: datetime | None,
) -> bool:
    if status not in {"active", "expired"}:
        return False
    if status == "expired":
        return True
    if role == "admin":
        return True
    return expiration_notice_sent_at is not None


class ApiKeysService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.whitelist_repo = SQLAlchemyWhitelistRepository(session)
        self.key_repo = SQLAlchemyApiKeyRepository(session)
        self.admin_repo = SQLAlchemyAdminRepository(session)
        self.login_eligibility = LoginEligibilityService(
            whitelist_repo=self.whitelist_repo,
            admin_repo=self.admin_repo,
        )
        self.directory_identity = DirectoryIdentityService()
        self.persnl = PersnlSoapService()
        self.provider_client = ProviderClient()
        self.crypto = CryptoService(self.settings.api_key_encryption_secret)
        self.mail_service = MailService()

    def create_application(
        self,
        current_user: CurrentUser,
        application_date: date,
        duration_months: int,
        purpose: str,
        target_identity: dict | None = None,
    ) -> dict:
        if application_date > date.today():
            raise ApiError("INVALID_APPLICATION_DATE", "application_date cannot be in the future", 422)
        if duration_months not in {1, 6, 12}:
            raise ApiError("INVALID_DURATION_MONTHS", "duration_months must be one of 1, 6, 12", 422)
        normalized_purpose = purpose.strip()
        if not normalized_purpose:
            raise ApiError("VALIDATION_ERROR", "purpose is required", 422)

        identity = AuthIdentity(
            account=current_user.account,
            name=current_user.name,
            email=current_user.email,
            department=current_user.department,
            sysid=current_user.sysid,
        )
        is_proxy_submission = False
        if current_user.role == "admin" and target_identity is not None:
            target_account = str(target_identity.get("account", "")).strip()
            if not target_account:
                raise ApiError("VALIDATION_ERROR", "target_identity.account is required for admin proxy submission", 422)
            if not self.directory_identity.is_configured():
                raise ApiError("SOAP_SERVICE_UNAVAILABLE", "soap service unavailable", 503)
            try:
                identity = self.directory_identity.resolve_by_account(target_account)
            except DirectoryLookupNotFoundError as exc:
                raise ApiError("VALIDATION_ERROR", "target account not found", 422) from exc
            except DirectoryLookupNotUniqueError as exc:
                raise ApiError("VALIDATION_ERROR", "target account is not unique", 422) from exc
            except DirectoryLookupUnavailableError as exc:
                raise ApiError("SOAP_SERVICE_UNAVAILABLE", "soap service unavailable", 503) from exc
            is_proxy_submission = True

        if not self.login_eligibility.is_eligible_by_sysid(identity.sysid):
            if self.persnl.is_configured():
                lookup_account = identity.account.strip()
                if not lookup_account:
                    raise ApiError("APPLICANT_NOT_ELIGIBLE", "applicant is not eligible", 403)
                try:
                    matches = self.persnl.search_person_by_account(lookup_account, on_job="1")
                except PersnlSoapUnavailableError as exc:
                    raise ApiError("SOAP_SERVICE_UNAVAILABLE", "soap service timeout", 503) from exc
                tcode = str(matches[0].get("tCode", "")).strip() if matches else ""
            else:
                tcode = ""
            if not self.login_eligibility.is_allowed_by_tcode(tcode):
                raise ApiError("APPLICANT_NOT_ELIGIBLE", "applicant is not eligible", 403)

        operator_identity = AuthIdentity(
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
                user_id=identity.sysid,
                identity=identity,
                operator_identity=operator_identity,
                is_proxy_submission=is_proxy_submission,
                application_date=application_date,
                duration_months=duration_months,
                purpose=normalized_purpose,
                limit_strategy="",
                max_budget=None,
                budget_duration=None,
                tpm_limit=None,
                rpm_limit=None,
                issuance_status="issued",
                pending_issued_at=None,
                issued_at=issued_at,
                expires_at=expires_at,
            )
        )
        try:
            plaintext = self._issue_application(application)
        except ApiError as exc:
            if exc.code == "PROVIDER_UNAVAILABLE":
                self._notify_admins_issuance_failure(
                    operation="application",
                    actor_account=current_user.account,
                    actor_role=current_user.role,
                    target_account=identity.account,
                    error_code=exc.code,
                )
            raise

        self.session.add(application)
        self.session.commit()
        if application.issuance_status == "issued":
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
        }

    def _issue_application(self, application: ApiKeyApplication) -> str | None:
        config = self._get_limit_strategy_config_for_issuance()
        max_budget = (config.budget_max_budget or "").strip()
        budget_duration = (config.budget_duration or "").strip()
        tpm_limit = config.rate_limit_tpm
        rpm_limit = config.rate_limit_rpm
        if not max_budget or not budget_duration:
            raise ApiError("ISSUANCE_CONFIG_INCOMPLETE", "budget config is incomplete", 409)
        if not tpm_limit or not rpm_limit or int(tpm_limit) <= 0 or int(rpm_limit) <= 0:
            raise ApiError("ISSUANCE_CONFIG_INCOMPLETE", "rate limit config is incomplete", 409)
        application.limit_strategy = "budget+rate_limit"
        application.max_budget = max_budget
        application.budget_duration = budget_duration
        application.tpm_limit = tpm_limit
        application.rpm_limit = rpm_limit

        plaintext: str | None = None
        try:
            provider_mode = (self.settings.issuance_provider_mode or "external").strip().lower()
            use_local_issuance = provider_mode == "local"
            if not use_local_issuance and self.provider_client.is_configured():
                provider_budget_duration = _to_provider_budget_duration(budget_duration)
                provider_result = self.provider_client.generate_key(
                    {
                        "max_budget": float(max_budget),
                        "budget_duration": provider_budget_duration,
                        "tpm_limit": tpm_limit,
                        "rpm_limit": rpm_limit,
                        "models": ["gemma-4-31B-it"],
                        "key_alias": _default_alias(application.account),
                        "key_type": "AI API",
                    }
                )
                plaintext = provider_result.key_plaintext
            else:
                plaintext = _generate_api_key()
            key = self.key_repo.create_key(
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
        except ProviderUnavailableError as exc:
            raise ApiError("PROVIDER_UNAVAILABLE", "provider unavailable", 503) from exc
        application.updated_at = datetime.now(UTC)
        self.session.add(application)
        return plaintext

    def _get_limit_strategy_config_for_issuance(self) -> LimitStrategyConfig:
        config = self.session.get(LimitStrategyConfig, LIMIT_STRATEGY_CONFIG_ID)
        if config is not None:
            return config
        now = datetime.now(UTC)
        return LimitStrategyConfig(
            id=LIMIT_STRATEGY_CONFIG_ID,
            budget_max_budget=LIMIT_STRATEGY_DEFAULTS["budget_max_budget"],
            budget_duration=LIMIT_STRATEGY_DEFAULTS["budget_duration"],
            rate_limit_tpm=LIMIT_STRATEGY_DEFAULTS["rate_limit_tpm"],
            rate_limit_rpm=LIMIT_STRATEGY_DEFAULTS["rate_limit_rpm"],
            created_at=now,
            updated_at=now,
        )

    def get_limit_strategy_config(self, current_user: CurrentUser) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)
        config = self.session.get(LimitStrategyConfig, LIMIT_STRATEGY_CONFIG_ID)
        if config is None:
            return dict(LIMIT_STRATEGY_DEFAULTS)
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
        config = self.session.get(LimitStrategyConfig, LIMIT_STRATEGY_CONFIG_ID)
        now = datetime.now(UTC)
        if config is None:
            config = LimitStrategyConfig(
                id=LIMIT_STRATEGY_CONFIG_ID,
                budget_max_budget=LIMIT_STRATEGY_DEFAULTS["budget_max_budget"],
                budget_duration=LIMIT_STRATEGY_DEFAULTS["budget_duration"],
                rate_limit_tpm=LIMIT_STRATEGY_DEFAULTS["rate_limit_tpm"],
                rate_limit_rpm=LIMIT_STRATEGY_DEFAULTS["rate_limit_rpm"],
                created_at=now,
                updated_at=now,
            )
        config.budget_max_budget = budget_max_budget
        config.budget_duration = budget_duration
        config.rate_limit_tpm = rate_limit_tpm
        config.rate_limit_rpm = rate_limit_rpm
        config.updated_at = now
        self.session.add(config)
        self.session.commit()
        return {
            "budget_max_budget": config.budget_max_budget,
            "budget_duration": config.budget_duration,
            "rate_limit_tpm": config.rate_limit_tpm,
            "rate_limit_rpm": config.rate_limit_rpm,
        }

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

        items, total = self.key_repo.list_keys(
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
                    "status": _effective_status(status=item.status, expires_at=item.expires_at),
                    "masked_key": item.masked_key,
                    "key_alias": item.key_alias or _default_alias(item.owner_account),
                    "application_date": item.application_date,
                    "duration_months": item.duration_months,
                    "owner_account": item.owner_account,
                    "owner_name": item.owner_name,
                    "expires_at": item.expires_at,
                    "expiration_notice_sent_at": item.expiration_notice_sent_at,
                    "extend_eligible": _is_extend_eligible(
                        role=current_user.role,
                        status=_effective_status(status=item.status, expires_at=item.expires_at),
                        expiration_notice_sent_at=item.expiration_notice_sent_at,
                    ),
                }
                for item in items
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def get_key_detail(self, current_user: CurrentUser, key_id: str) -> dict:
        detail = self.key_repo.get_key_detail(key_id, "admin", current_user.account)
        if detail is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)

        scoped = self.key_repo.get_key_detail(key_id, current_user.role, current_user.account)
        if scoped is None:
            raise ApiError("KEY_NOT_OWNED_BY_USER", "key is not owned by requester", 403)

        effective_status = _effective_status(status=scoped.status, expires_at=scoped.expires_at)
        return {
            "id": scoped.id,
            "status": effective_status,
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
            "expiration_notice_sent_at": scoped.expiration_notice_sent_at,
            "extend_eligible": _is_extend_eligible(
                role=current_user.role,
                status=effective_status,
                expiration_notice_sent_at=scoped.expiration_notice_sent_at,
            ),
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

    def renew_key(self, current_user: CurrentUser, key_id: str) -> dict:
        exists = self.key_repo.get_key_detail(key_id, "admin", current_user.account)
        if exists is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)

        allowed = self.key_repo.get_key_detail(key_id, current_user.role, current_user.account)
        if allowed is None:
            raise ApiError("KEY_NOT_OWNED_BY_USER", "key is not owned by requester", 403)

        row = (
            self.session.query(ApiKey, ApiKeyApplication)
            .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
            .filter(ApiKey.id == key_id)
            .first()
        )
        if row is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)

        source_key, source_app = row
        source_effective_status = _effective_status(status=source_key.status, expires_at=source_app.expires_at)
        if source_effective_status not in {"revoked", "expired"}:
            raise ApiError("KEY_NOT_RENEWABLE", "only revoked or expired key can be renewed", 409)
        if source_key.renewed_to_key_id:
            raise ApiError("KEY_ALREADY_RENEWED", "key already renewed", 409)

        identity = AuthIdentity(
            account=source_app.account,
            name=source_app.name,
            email=source_app.email,
            department=source_app.department,
            sysid=source_app.sysid,
        )
        operator_identity = AuthIdentity(
            account=current_user.account,
            name=current_user.name,
            email=current_user.email,
            department=current_user.department,
            sysid=current_user.sysid,
        )
        now = datetime.now(UTC)
        application = self.key_repo.create_application(
            ApplicationCreateInput(
                user_id=source_app.user_id,
                identity=identity,
                operator_identity=operator_identity,
                is_proxy_submission=current_user.role == "admin" and current_user.account != source_app.account,
                application_date=date.today(),
                duration_months=source_app.duration_months,
                purpose=source_app.purpose,
                limit_strategy="",
                max_budget=None,
                budget_duration=None,
                tpm_limit=None,
                rpm_limit=None,
                issuance_status="issued",
                pending_issued_at=None,
                issued_at=now,
                expires_at=_calc_expiration(now, source_app.duration_months),
            )
        )
        try:
            plaintext = self._issue_application(application)
        except ApiError as exc:
            if exc.code == "PROVIDER_UNAVAILABLE":
                self._notify_admins_issuance_failure(
                    operation="renew",
                    actor_account=current_user.account,
                    actor_role=current_user.role,
                    target_account=source_app.account,
                    error_code=exc.code,
                )
            raise

        issued_key = self.session.query(ApiKey).filter(ApiKey.application_id == application.id).one_or_none()
        email_warning: str | None = None

        if application.issuance_status == "issued":
            try:
                run_async(
                    self.mail_service.send_key_renewed_notification(
                        to_email=source_app.email,
                        owner_name=source_app.name,
                        app_domain=self.settings.app_domain,
                    )
                )
            except Exception:  # noqa: BLE001
                logging.exception("failed to send key renewed email to applicant")
                email_warning = "key_renewed_email_failed"
        if issued_key is None and application.issuance_status == "issued":
            raise ApiError("INTERNAL_ERROR", "renew issued without key record", 500)

        if issued_key is not None:
            source_key.renewed_to_key_id = issued_key.id
        source_app.updated_at = datetime.now(UTC)
        self.session.add(source_key)
        self.session.add(source_app)
        self.session.commit()
        return {
            "id": issued_key.id if issued_key is not None else source_key.id,
            "status": issued_key.status if issued_key is not None else source_key.status,
            "expires_at": application.expires_at,
            "issuance_status": application.issuance_status,
            "renewed_from_key_id": source_key.id,
            "api_key_plaintext": plaintext,
            "email_warning": email_warning,
        }

    def extend_key(self, current_user: CurrentUser, key_id: str, duration_months: int) -> dict:
        if duration_months not in {1, 6, 12}:
            raise ApiError("VALIDATION_ERROR", "duration_months must be one of 1, 6, 12", 422)

        exists = self.key_repo.get_key_detail(key_id, "admin", current_user.account)
        if exists is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)

        allowed = self.key_repo.get_key_detail(key_id, current_user.role, current_user.account)
        if allowed is None:
            raise ApiError("KEY_NOT_OWNED_BY_USER", "key is not owned by requester", 403)

        row = (
            self.session.query(ApiKey, ApiKeyApplication)
            .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
            .filter(ApiKey.id == key_id)
            .first()
        )
        if row is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)

        source_key, source_app = row
        source_effective_status = _effective_status(status=source_key.status, expires_at=source_app.expires_at)
        if source_effective_status not in {"active", "expired"}:
            raise ApiError("KEY_NOT_EXTENDABLE", "only active or expired key can be extended", 409)
        if (
            current_user.role != "admin"
            and source_effective_status == "active"
            and source_key.expiration_notice_sent_at is None
        ):
            raise ApiError("KEY_EXTENSION_NOTICE_REQUIRED", "extension requires expiration notice", 409)
        base_time = source_app.expires_at
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        if base_time < now:
            base_time = now
        source_app.expires_at = _calc_expiration(base_time, duration_months)
        source_app.duration_months = duration_months
        source_app.status = "active"
        source_key.status = "active"
        source_app.updated_at = now
        self.session.add(source_key)
        self.session.add(source_app)
        self.session.commit()
        return {
            "id": source_key.id,
            "status": source_key.status,
            "expires_at": source_app.expires_at,
        }

    def _notify_admins_issuance_failure(
        self,
        *,
        operation: str,
        actor_account: str,
        actor_role: str,
        target_account: str,
        error_code: str,
    ) -> None:
        recipients = sorted({email.strip().lower() for email in self.admin_repo.list_active_emails() if email and email.strip()})
        if not recipients:
            return
        try:
            run_async(
                self.mail_service.send_provider_issuance_failed_to_admins(
                    to_emails=recipients,
                    operation=operation,
                    actor_account=actor_account,
                    actor_role=actor_role,
                    target_account=target_account,
                    error_code=error_code,
                )
            )
        except Exception:  # noqa: BLE001
            logging.exception("failed to send provider issuance failure email to admins")

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

        allowed_sort_by = {
            "owner_account",
            "owner_name",
            "owner_email",
            "owner_department",
            "total_applications",
            "active_count",
            "revoked_count",
            "expired_count",
            "last_applied_at",
        }
        allowed_scopes = {"all", "active", "revoked", "expired"}
        if scope not in allowed_scopes:
            raise ApiError("VALIDATION_ERROR", "scope must be one of all, active, revoked, expired", 422)

        if sort_by not in allowed_sort_by:
            raise ApiError("VALIDATION_ERROR", "sort_by is invalid", 422)

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
