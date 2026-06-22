import hashlib
import logging
import re
import secrets
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.input_validation import (
    parse_ascii_digits,
    validate_ascii_digits_string,
    validate_safe_persisted_text,
)
from app.services.crypto_service import CryptoService
from app.services.directory_identity_service import (
    DirectoryIdentityService,
    DirectoryLookupNotFoundError,
    DirectoryLookupNotUniqueError,
    DirectoryLookupUnavailableError,
)
from app.services.login_eligibility_service import LoginEligibilityService
from app.services.persnl_soap_service import PersnlSoapService, PersnlSoapUnavailableError
from app.services.provider_client import ProviderBadRequestError, ProviderClient, ProviderUnavailableError
from db.models.applications import ApiKeyApplication
from db.models.api_keys import ApiKey
from db.models.limit_strategy_config import LimitStrategyConfig
from db.repositories import SQLAlchemyAdminRepository, SQLAlchemyApiKeyRepository, SQLAlchemyWhitelistRepository
from db.repositories.types import (
    ApiKeyAliasUpdateInput,
    ApiKeyCreateInput,
    ApiKeyListFilter,
    ApiKeyUserStatisticsFilter,
    ApplicationCreateInput,
    AuthIdentity,
)

LIMIT_STRATEGY_CONFIG_ID = "global-limit-strategy-config"
MAX_KEY_ALIAS_ATTEMPTS = 20
TAIPEI_TZ = ZoneInfo("Asia/Taipei")
logger = logging.getLogger(__name__)
LIMIT_STRATEGY_DEFAULTS = {
    "budget_max_budget": "1000",
    "budget_duration": "monthly",
    "rate_limit_tpm": 10000,
    "rate_limit_rpm": 500,
    "max_parallel_requests": 0,
}


@dataclass(slots=True)
class Pagination:
    page: int = 1
    page_size: int = 20


@dataclass(slots=True)
class IssuanceConfigValues:
    max_budget: str
    budget_duration: str
    tpm_limit: int
    rpm_limit: int
    max_parallel_requests: int


@dataclass(slots=True)
class UsageCycleAggregate:
    spend: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(slots=True)
class ActiveKeyProviderIdentifier:
    key_hash: str
    key_alias: str


def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _key_prefix_for_env(app_env: str) -> str:
    return "sk-" if app_env.strip().lower() == "prod" else "AS-"


def _mask_key(plaintext: str) -> str:
    return f"{_key_prefix_for_env(get_settings().app_env)}...{plaintext[-4:]}"


ALLOWED_DURATION_DAYS = {30, 180, 360}


def _validate_duration_days(duration_days: int) -> int:
    if duration_days not in ALLOWED_DURATION_DAYS:
        raise ValueError("duration_days must be one of 30, 180, 360")
    return duration_days


def _calc_expiration(issued_at: datetime, duration_days: int) -> datetime:
    return issued_at + timedelta(days=_validate_duration_days(duration_days))


def _default_alias(owner_account: str) -> str:
    return f"for_{owner_account}"


def _versioned_alias(base_alias: str, version: int) -> str:
    if version <= 1:
        return base_alias
    return f"{base_alias}_v{version}"


def _alias_seed(owner_account: str, current_alias: str | None = None) -> tuple[str, int]:
    normalized_alias = (current_alias or "").strip()
    if not normalized_alias:
        return _default_alias(owner_account), 1

    match = re.match(r"^(?P<base>.+)_v(?P<version>\d+)$", normalized_alias)
    if match:
        return match.group("base"), int(match.group("version"))
    return normalized_alias, 1


def _to_provider_budget_duration(duration: str) -> str:
    normalized = duration.strip().lower()
    if normalized == "daily":
        return "1d"
    if normalized == "weekly":
        return "7d"
    if normalized == "monthly":
        return "30d"
    return normalized


def _normalize_provider_budget_duration(duration: object) -> str | None:
    normalized = str(duration or "").strip().lower()
    if normalized in {"daily", "1d"}:
        return "daily"
    if normalized in {"weekly", "7d"}:
        return "weekly"
    if normalized in {"monthly", "30d"}:
        return "monthly"
    return None


def _to_provider_duration(duration_days: int) -> str:
    return f"{_validate_duration_days(duration_days)}d"


def _to_provider_duration_days(duration_days: int) -> str:
    if duration_days <= 0:
        raise ValueError("duration_days must be positive")
    return f"{duration_days}d"


def _to_provider_rate_limit(limit: int) -> int | None:
    return None if limit == 0 else limit


def _to_provider_max_parallel_requests(limit: int) -> int | None:
    return None if limit == 0 else limit


def _effective_status(*, status: str, expires_at: datetime) -> str:
    expires_at_utc = expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=UTC)
    if status == "active" and expires_at_utc < datetime.now(UTC):
        return "expired"
    return status


def _is_extend_eligible(
    *,
    status: str,
    expires_at: datetime,
) -> bool:
    return status == "active"


def _normalized_utc_datetime(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _base_expires_at(
    *,
    application_date: date,
    original_duration_days: int,
    issued_at: datetime,
) -> datetime:
    issued_at_utc = _normalized_utc_datetime(issued_at)
    base_date = application_date + timedelta(days=_validate_duration_days(original_duration_days))
    return datetime.combine(base_date, issued_at_utc.timetz())


def _provider_total_days_for_expiration(*, application_date: date, expires_at: datetime) -> int:
    expires_at_utc = _normalized_utc_datetime(expires_at)
    total_days = (expires_at_utc.date() - application_date).days
    return max(total_days, 1)


def _extended_terms(
    *,
    issued_at: datetime,
    original_duration_days: int,
    now: datetime,
) -> tuple[date, datetime]:
    next_application_date = now.date()
    return next_application_date, _base_expires_at(
        application_date=next_application_date,
        original_duration_days=original_duration_days,
        issued_at=issued_at,
    )


def _parse_optional_budget(value: str | None) -> float | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return float(Decimal(normalized))
    except (InvalidOperation, ValueError):
        return None


def _round_money(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01")))


def _budget_duration_days(duration: str | None) -> int | None:
    normalized = str(duration or "").strip().lower()
    if normalized == "daily":
        return 1
    if normalized == "weekly":
        return 7
    if normalized == "monthly":
        return 30
    return None


def _resolve_current_cycle_window(
    *,
    budget_duration: str | None,
    budget_reset_at: datetime | None,
) -> tuple[datetime, datetime] | None:
    duration_days = _budget_duration_days(budget_duration)
    if duration_days is None or budget_reset_at is None:
        return None
    cycle_end = _normalized_utc_datetime(budget_reset_at)
    cycle_start = cycle_end - timedelta(days=duration_days)
    return cycle_start, cycle_end


def _bucket_overlaps_cycle(
    *,
    bucket_start_utc: datetime,
    bucket_end_utc: datetime,
    cycle_start_utc: datetime,
    cycle_end_utc: datetime,
) -> bool:
    normalized_bucket_start = _normalized_utc_datetime(bucket_start_utc)
    normalized_bucket_end = _normalized_utc_datetime(bucket_end_utc)
    return normalized_bucket_end > cycle_start_utc and normalized_bucket_start < cycle_end_utc


def _aggregate_cycle_usage(buckets, *, cycle_start_utc: datetime, cycle_end_utc: datetime) -> UsageCycleAggregate:
    spend_total = Decimal("0")
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    for bucket in buckets:
        if not _bucket_overlaps_cycle(
            bucket_start_utc=bucket.bucket_start_utc,
            bucket_end_utc=bucket.bucket_end_utc,
            cycle_start_utc=cycle_start_utc,
            cycle_end_utc=cycle_end_utc,
        ):
            continue
        if bucket.spend is not None:
            spend_total += Decimal(str(bucket.spend))
        prompt_tokens += bucket.prompt_tokens
        completion_tokens += bucket.completion_tokens
        total_tokens += bucket.total_tokens
    return UsageCycleAggregate(
        spend=_round_money(float(spend_total)),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _build_usage_summary(
    *,
    max_budget_raw: str | None,
    budget_duration: str | None,
    key_created_at: datetime,
    config_updated_at: datetime | None,
    tpm_limit: int | None,
    rpm_limit: int | None,
    max_parallel_requests: int | None,
    spend: float | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    budget_reset_at: datetime | None,
    synced_at: datetime | None,
) -> dict:
    max_budget = _parse_optional_budget(max_budget_raw)
    remaining_budget: float | None = None
    if max_budget is not None and spend is not None:
        remaining_budget = 0.0 if max_budget == 0 else _round_money(max(max_budget - spend, 0.0))

    return {
        "spend": _round_money(spend) if spend is not None else None,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "max_budget": max_budget,
        "remaining_budget": remaining_budget,
        "tpm_limit": tpm_limit,
        "rpm_limit": rpm_limit,
        "max_parallel_requests": max_parallel_requests,
        "budget_reset_at": budget_reset_at,
        "synced_at": synced_at,
    }


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

    def create_application(
        self,
        current_user: CurrentUser,
        application_date: date,
        duration_days: int,
        purpose: str,
        target_identity: dict | None = None,
    ) -> dict:
        self._ensure_application_is_live_for_user(current_user)
        if application_date > date.today():
            raise ApiError("INVALID_APPLICATION_DATE", "application_date cannot be in the future", 422)
        if duration_days not in ALLOWED_DURATION_DAYS:
            raise ApiError("INVALID_DURATION_DAYS", "duration_days must be one of 30, 180, 360", 422)
        normalized_purpose = validate_safe_persisted_text(field_name="purpose", value=purpose, required=True)

        identity = AuthIdentity(
            account=current_user.account,
            name=current_user.name,
            email=current_user.email,
            department=current_user.department,
            sysid=current_user.sysid,
        )
        is_proxy_submission = False
        if current_user.role == "admin" and target_identity is not None:
            target_account = validate_safe_persisted_text(
                field_name="target_identity.account",
                value=target_identity.get("account", ""),
                required=True,
            )
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

        issued_at = datetime.now(UTC)
        expires_at = _calc_expiration(issued_at, duration_days)
        config = self._get_limit_strategy_values()
        plaintext, provider_metadata, key_alias = self._generate_key_for_application(
            owner_account=identity.account,
            duration_days=duration_days,
            config=config,
        )

        application = self.key_repo.create_application(
            ApplicationCreateInput(
                identity=identity,
                is_proxy_submission=is_proxy_submission,
                proxy_operator_account=current_user.account if is_proxy_submission else None,
                application_date=application_date,
                duration_days=duration_days,
                original_duration_days=duration_days,
                purpose=normalized_purpose,
                max_budget=config.max_budget,
                budget_duration=config.budget_duration,
                tpm_limit=config.tpm_limit,
                rpm_limit=config.rpm_limit,
                max_parallel_requests=config.max_parallel_requests,
                issued_at=issued_at,
                expires_at=expires_at,
            )
        )
        self._create_key_record(application_id=application.id, plaintext=plaintext, key_alias=key_alias)
        application_id = application.id
        application_account = application.account
        application_status = application.status
        application_issued_at = application.issued_at
        application_expires_at = application.expires_at
        self.session.add(application)
        self.session.commit()

        limit_config = self._get_limit_strategy_config_for_issuance()

        return {
            "application": {
                "id": application_id,
                "account": application_account,
                "status": application_status,
                "issued_at": application_issued_at,
                "expires_at": application_expires_at,
            },
            "api_key_plaintext": plaintext,
            "provider_request_id": provider_metadata.get("provider_request_id"),
            "provider_operation_id": provider_metadata.get("provider_operation_id"),
        }

    def _resolve_api_key_application_go_live_at(self) -> datetime:
        go_live_at = self.settings.api_key_application_go_live_at
        if go_live_at.tzinfo is None:
            return go_live_at.replace(tzinfo=TAIPEI_TZ)
        return go_live_at.astimezone(TAIPEI_TZ)

    def _ensure_application_is_live_for_user(self, current_user: CurrentUser) -> None:
        if current_user.role == "admin":
            return
        go_live_at = self._resolve_api_key_application_go_live_at()
        if datetime.now(TAIPEI_TZ) < go_live_at:
            raise ApiError(
                "APPLICATION_NOT_LIVE",
                "application is not live yet",
                403,
                extra={"go_live_at": go_live_at.isoformat()},
            )

    def _get_limit_strategy_values(self) -> IssuanceConfigValues:
        config = self._get_limit_strategy_config_for_issuance()
        max_budget = (config.budget_max_budget or "").strip()
        budget_duration = (config.budget_duration or "").strip()
        tpm_limit = config.rate_limit_tpm
        rpm_limit = config.rate_limit_rpm
        max_parallel_requests = config.max_parallel_requests
        if not max_budget or not budget_duration:
            raise ApiError("ISSUANCE_CONFIG_INCOMPLETE", "budget config is incomplete", 409)
        if tpm_limit is None or rpm_limit is None or max_parallel_requests is None:
            raise ApiError("ISSUANCE_CONFIG_INCOMPLETE", "rate limit config is incomplete", 409)
        if int(tpm_limit) < 0 or int(rpm_limit) < 0 or int(max_parallel_requests) < 0:
            raise ApiError("ISSUANCE_CONFIG_INCOMPLETE", "rate limit config is incomplete", 409)
        return IssuanceConfigValues(
            max_budget=max_budget,
            budget_duration=budget_duration,
            tpm_limit=int(tpm_limit),
            rpm_limit=int(rpm_limit),
            max_parallel_requests=int(max_parallel_requests),
        )

    def _build_provider_payload(
        self,
        *,
        duration_days: int,
        config: IssuanceConfigValues,
        key_alias: str,
    ) -> dict:
        return {
            "max_budget": float(config.max_budget),
            "budget_duration": _to_provider_budget_duration(config.budget_duration),
            "duration": _to_provider_duration(duration_days),
            "tpm_limit": _to_provider_rate_limit(config.tpm_limit),
            "rpm_limit": _to_provider_rate_limit(config.rpm_limit),
            "max_parallel_requests": _to_provider_max_parallel_requests(config.max_parallel_requests),
            "team_id": self._require_provider_team_id(),
            "key_alias": key_alias,
            "key_type": "llm_api",
        }

    def _build_provider_update_payload(
        self,
        *,
        plaintext: str,
        duration_days: int | None = None,
        config: IssuanceConfigValues,
        key_alias: str | None = None,
    ) -> dict:
        if duration_days is None:
            raise ValueError("duration_days is required")
        payload = {
            "key": plaintext,
            "max_budget": float(config.max_budget),
            "budget_duration": _to_provider_budget_duration(config.budget_duration),
            "duration": _to_provider_duration_days(duration_days),
            "tpm_limit": _to_provider_rate_limit(config.tpm_limit),
            "rpm_limit": _to_provider_rate_limit(config.rpm_limit),
            "max_parallel_requests": _to_provider_max_parallel_requests(config.max_parallel_requests),
            "team_id": self._require_provider_team_id(),
            "key_type": "llm_api",
        }
        if key_alias is not None:
            payload["key_alias"] = key_alias
        return payload

    def _require_provider_team_id(self) -> str:
        team_id = (self.settings.provider_team_id or "").strip()
        if not team_id:
            raise ApiError("PROVIDER_TEAM_ID_REQUIRED", "provider team id is required", 503)
        return team_id

    def _provider_operates_remotely(self) -> bool:
        provider_mode = (self.settings.issuance_provider_mode or "external").strip().lower()
        return provider_mode != "local" and self.provider_client.is_configured()

    def _generate_key_for_application(
        self,
        *,
        owner_account: str,
        duration_days: int,
        config: IssuanceConfigValues,
    ) -> tuple[str, dict, str]:
        try:
            if self._provider_operates_remotely():
                provider_result, key_alias = self._retry_provider_alias_operation(
                    owner_account=owner_account,
                    duration_days=duration_days,
                    config=config,
                    current_alias=None,
                    operation=lambda payload: self.provider_client.generate_key(payload),
                )
                return provider_result.key_plaintext, {
                    "provider_request_id": provider_result.request_id,
                    "provider_operation_id": provider_result.operation_id,
                }, key_alias
            return _generate_api_key(), {}, _default_alias(owner_account)
        except ProviderBadRequestError as exc:
            raise ApiError("VALIDATION_ERROR", str(exc), 422) from exc
        except ProviderUnavailableError as exc:
            raise ApiError("PROVIDER_UNAVAILABLE", "provider unavailable", 503) from exc

    def _retry_provider_alias_operation(
        self,
        *,
        owner_account: str,
        duration_days: int,
        config: IssuanceConfigValues,
        current_alias: str | None,
        operation,
    ):
        base_alias, start_version = _alias_seed(owner_account, current_alias)
        last_error: ProviderBadRequestError | None = None
        for attempt in range(MAX_KEY_ALIAS_ATTEMPTS):
            candidate_alias = _versioned_alias(base_alias, start_version + attempt)
            try:
                return (
                    operation(
                        self._build_provider_payload(
                            duration_days=duration_days,
                            config=config,
                            key_alias=candidate_alias,
                        )
                    ),
                    candidate_alias,
                )
            except ProviderBadRequestError as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    def _create_key_record(self, *, application_id: str, plaintext: str, key_alias: str | None) -> ApiKey:
        key_prefix = _key_prefix_for_env(self.settings.app_env)
        return self.key_repo.create_key(
            ApiKeyCreateInput(
                application_id=application_id,
                key_hash=_hash_key(plaintext),
                key_prefix=key_prefix,
                masked_key=_mask_key(plaintext),
                key_alias=key_alias,
                key_ciphertext=self.crypto.encrypt(plaintext),
                key_kek_version=self.settings.api_key_kek_version,
            )
        )

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
            max_parallel_requests=LIMIT_STRATEGY_DEFAULTS["max_parallel_requests"],
            created_at=now,
            updated_at=now,
        )

    def _list_active_key_provider_identifiers(self) -> list[ActiveKeyProviderIdentifier]:
        rows = (
            self.session.query(ApiKey.key_hash, ApiKey.key_alias, ApiKeyApplication.account)
            .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
            .filter(ApiKey.status == "active")
            .all()
        )
        return [
            ActiveKeyProviderIdentifier(
                key_hash=str(key_hash),
                key_alias=(str(key_alias).strip() if key_alias else _default_alias(str(account))),
            )
            for key_hash, key_alias, account in rows
        ]

    def _verify_provider_limit_strategy_sync(self, *, expected_budget_duration: str) -> None:
        active_keys = self._list_active_key_provider_identifiers()
        if not active_keys:
            return

        try:
            payload = self.provider_client.list_spend_keys()
        except ProviderBadRequestError as exc:
            raise ApiError("PROVIDER_UNAVAILABLE", "provider spend summaries unavailable", 503) from exc
        except ProviderUnavailableError as exc:
            raise ApiError("PROVIDER_UNAVAILABLE", "provider spend summaries unavailable", 503) from exc

        if isinstance(payload, dict):
            records = payload.get("data")
        else:
            records = payload
        if not isinstance(records, list):
            raise ApiError("PROVIDER_SYNC_MISMATCH", "provider spend summaries are invalid", 503)

        matched_durations: dict[str, str | None] = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            normalized_duration = _normalize_provider_budget_duration(record.get("budget_duration"))
            token = str(record.get("token") or "").strip()
            key_alias = str(record.get("key_alias") or "").strip()
            if token:
                matched_durations[f"token:{token}"] = normalized_duration
            if key_alias:
                matched_durations[f"alias:{key_alias}"] = normalized_duration

        mismatched_keys: list[str] = []
        missing_keys: list[str] = []
        for key in active_keys:
            matched_duration = matched_durations.get(f"token:{key.key_hash}")
            if matched_duration is None:
                matched_duration = matched_durations.get(f"alias:{key.key_alias}")
            if matched_duration is None:
                missing_keys.append(key.key_alias)
                continue
            if matched_duration != expected_budget_duration:
                mismatched_keys.append(key.key_alias)

        if missing_keys or mismatched_keys:
            logger.error(
                "provider limit strategy sync mismatch detected",
                extra={
                    "expected_budget_duration": expected_budget_duration,
                    "missing_key_aliases": missing_keys,
                    "mismatched_key_aliases": mismatched_keys,
                },
            )
            raise ApiError("PROVIDER_SYNC_MISMATCH", "provider key limit sync verification failed", 503)

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
            "max_parallel_requests": config.max_parallel_requests,
        }

    def update_limit_strategy_config(self, current_user: CurrentUser, payload: dict) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)
        budget_max_budget = validate_ascii_digits_string(
            field_name="budget_max_budget",
            value=payload.get("budget_max_budget"),
        )
        budget_duration = str(payload.get("budget_duration") or "").strip()
        rate_limit_tpm = parse_ascii_digits(field_name="rate_limit_tpm", value=payload.get("rate_limit_tpm"))
        rate_limit_rpm = parse_ascii_digits(field_name="rate_limit_rpm", value=payload.get("rate_limit_rpm"))
        max_parallel_requests = parse_ascii_digits(
            field_name="max_parallel_requests",
            value=payload.get("max_parallel_requests"),
        )
        if not budget_max_budget or not budget_duration:
            raise ApiError("VALIDATION_ERROR", "budget config is required", 422)
        if rate_limit_tpm < 0 or rate_limit_rpm < 0 or max_parallel_requests < 0:
            raise ApiError("VALIDATION_ERROR", "rate limit config is required", 422)
        config = self.session.get(LimitStrategyConfig, LIMIT_STRATEGY_CONFIG_ID)
        now = datetime.now(UTC)
        if config is None:
            config = LimitStrategyConfig(
                id=LIMIT_STRATEGY_CONFIG_ID,
                budget_max_budget=LIMIT_STRATEGY_DEFAULTS["budget_max_budget"],
                budget_duration=LIMIT_STRATEGY_DEFAULTS["budget_duration"],
                rate_limit_tpm=LIMIT_STRATEGY_DEFAULTS["rate_limit_tpm"],
                rate_limit_rpm=LIMIT_STRATEGY_DEFAULTS["rate_limit_rpm"],
                max_parallel_requests=LIMIT_STRATEGY_DEFAULTS["max_parallel_requests"],
                created_at=now,
                updated_at=now,
            )
        config.budget_max_budget = budget_max_budget
        config.budget_duration = budget_duration
        config.rate_limit_tpm = rate_limit_tpm
        config.rate_limit_rpm = rate_limit_rpm
        config.max_parallel_requests = max_parallel_requests
        config.updated_at = now
        if self._provider_operates_remotely():
            try:
                self.provider_client.update_team_limits(
                    {
                        "team_id": self._require_provider_team_id(),
                        "all_keys_in_team": True,
                        "update_fields": {
                            "max_budget": float(config.budget_max_budget),
                            "budget_duration": _to_provider_budget_duration(config.budget_duration),
                            "tpm_limit": _to_provider_rate_limit(config.rate_limit_tpm),
                            "rpm_limit": _to_provider_rate_limit(config.rate_limit_rpm),
                            "max_parallel_requests": _to_provider_max_parallel_requests(config.max_parallel_requests),
                        },
                    }
                )
                self._verify_provider_limit_strategy_sync(
                    expected_budget_duration=config.budget_duration,
                )
            except ProviderBadRequestError as exc:
                raise ApiError("VALIDATION_ERROR", str(exc), 422) from exc
            except ProviderUnavailableError as exc:
                raise ApiError("PROVIDER_UNAVAILABLE", "provider unavailable", 503) from exc
        self.session.add(config)
        self.session.commit()
        return {
            "budget_max_budget": config.budget_max_budget,
            "budget_duration": config.budget_duration,
            "rate_limit_tpm": config.rate_limit_tpm,
            "rate_limit_rpm": config.rate_limit_rpm,
            "max_parallel_requests": config.max_parallel_requests,
        }

    def list_keys(
        self,
        current_user: CurrentUser,
        page: int,
        page_size: int,
        status: str | None = None,
        owner_account: str | None = None,
        owner_name: str | None = None,
        key_alias: str | None = None,
        application_date_from: date | None = None,
        application_date_to: date | None = None,
        expires_from: datetime | None = None,
        expires_to: datetime | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> dict:
        allowed_statuses = {"active", "revoked", "expired"}
        allowed_sort_by = {
            "application_date",
            "duration_days",
            "status",
            "expires_at",
            "masked_key",
            "key_alias",
            "owner_account",
            "owner_name",
            "created_at",
        }
        if status is not None and status not in allowed_statuses:
            raise ApiError("VALIDATION_ERROR", "status must be one of active, revoked, expired", 422)
        if sort_by not in allowed_sort_by:
            raise ApiError("VALIDATION_ERROR", "sort_by is invalid", 422)
        if sort_dir not in {"asc", "desc"}:
            raise ApiError("VALIDATION_ERROR", "sort_dir must be asc or desc", 422)
        if expires_from is not None and expires_to is not None and expires_from > expires_to:
            raise ApiError("VALIDATION_ERROR", "expires_from cannot be greater than expires_to", 422)

        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        offset = (page - 1) * page_size

        normalized_owner_account = owner_account.strip() if owner_account else None
        normalized_owner_name = owner_name.strip() if owner_name else None
        normalized_key_alias = key_alias.strip() if key_alias else None
        if current_user.role != "admin":
            normalized_owner_account = None
            normalized_owner_name = None

        items, total = self.key_repo.list_keys(
            requester_role=current_user.role,
            requester_account=current_user.account,
            filters=ApiKeyListFilter(
                status=status,
                owner_account=normalized_owner_account or None,
                owner_name=normalized_owner_name or None,
                key_alias=normalized_key_alias or None,
                application_date_from=application_date_from,
                application_date_to=application_date_to,
                expires_from=expires_from,
                expires_to=expires_to,
                sort_by=sort_by,
                sort_dir=sort_dir,
            ),
            limit=page_size,
            offset=offset,
        )
        limit_config = self._get_limit_strategy_config_for_issuance()
        usage_windows_by_key: dict[str, tuple[datetime, datetime]] = {}
        for item in items:
            window = _resolve_current_cycle_window(
                budget_duration=limit_config.budget_duration,
                budget_reset_at=item.usage_budget_reset_at,
            )
            if window is not None:
                usage_windows_by_key[item.id] = window

        usage_buckets_by_key: dict[str, list] = defaultdict(list)
        if usage_windows_by_key:
            usage_buckets = self.key_repo.list_usage_buckets_for_keys(
                key_ids=list(usage_windows_by_key.keys()),
                granularity="day",
                bucket_start_from=min(window[0] for window in usage_windows_by_key.values()),
                bucket_start_to=max(window[1] for window in usage_windows_by_key.values()),
            )
            for bucket in usage_buckets:
                usage_buckets_by_key[bucket.api_key_id].append(bucket)

        response_items = []
        for item in items:
            effective_status = _effective_status(status=item.status, expires_at=item.expires_at)
            cycle_window = usage_windows_by_key.get(item.id)
            cycle_usage = None
            if cycle_window is not None:
                cycle_usage = _aggregate_cycle_usage(
                    usage_buckets_by_key.get(item.id, []),
                    cycle_start_utc=cycle_window[0],
                    cycle_end_utc=cycle_window[1],
                )
            usage_summary = _build_usage_summary(
                max_budget_raw=limit_config.budget_max_budget,
                budget_duration=limit_config.budget_duration,
                key_created_at=item.created_at,
                config_updated_at=limit_config.updated_at,
                tpm_limit=limit_config.rate_limit_tpm,
                rpm_limit=limit_config.rate_limit_rpm,
                max_parallel_requests=limit_config.max_parallel_requests,
                spend=cycle_usage.spend if cycle_usage is not None else None,
                prompt_tokens=cycle_usage.prompt_tokens if cycle_usage is not None else None,
                completion_tokens=cycle_usage.completion_tokens if cycle_usage is not None else None,
                total_tokens=cycle_usage.total_tokens if cycle_usage is not None else None,
                budget_reset_at=item.usage_budget_reset_at,
                synced_at=item.usage_synced_at,
            )
            response_items.append(
                {
                    "id": item.id,
                    "status": effective_status,
                    "masked_key": item.masked_key,
                    "key_alias": item.key_alias or _default_alias(item.owner_account),
                    "application_date": item.application_date,
                    "duration_days": item.duration_days,
                    "original_duration_days": item.original_duration_days,
                    "owner_account": item.owner_account,
                    "owner_name": item.owner_name,
                    "expires_at": item.expires_at,
                    "usage_summary": usage_summary,
                    "expiration_notice_sent_at": item.expiration_notice_sent_at,
                    "extend_eligible": _is_extend_eligible(
                        status=effective_status,
                        expires_at=item.expires_at,
                    ),
                }
            )
        return {
            "items": response_items,
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def list_usage_series(
        self,
        *,
        current_user: CurrentUser,
        key_id: str,
        granularity: str,
        from_date: date,
        to_date: date,
    ) -> dict:
        if granularity != "day":
            raise ApiError("VALIDATION_ERROR", "granularity must be day", 422)
        if from_date > to_date:
            raise ApiError("VALIDATION_ERROR", "from cannot be greater than to", 422)

        detail = self.key_repo.get_key_detail(key_id, "admin", current_user.account)
        if detail is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)
        scoped = self.key_repo.get_key_detail(key_id, current_user.role, current_user.account)
        if scoped is None:
            raise ApiError("KEY_NOT_OWNED_BY_USER", "key is not owned by requester", 403)

        bucket_start_from = datetime.combine(from_date, datetime.min.time(), tzinfo=TAIPEI_TZ).astimezone(UTC)
        bucket_start_to = datetime.combine(to_date + timedelta(days=1), datetime.min.time(), tzinfo=TAIPEI_TZ).astimezone(UTC)
        items = self.key_repo.list_usage_series(
            key_id=key_id,
            granularity=granularity,
            bucket_start_from=bucket_start_from,
            bucket_start_to=bucket_start_to,
        )
        return {
            "key_id": key_id,
            "granularity": granularity,
            "from": from_date,
            "to": to_date,
            "items": [
                {
                    "bucket_start": _normalized_utc_datetime(item.bucket_start_utc).astimezone(TAIPEI_TZ),
                    "bucket_label": _normalized_utc_datetime(item.bucket_start_utc).astimezone(TAIPEI_TZ).date().isoformat(),
                    "prompt_tokens": item.prompt_tokens,
                    "completion_tokens": item.completion_tokens,
                    "total_tokens": item.total_tokens,
                    "spend": _round_money(item.spend) if item.spend is not None else None,
                }
                for item in items
            ],
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
            "duration_days": scoped.duration_days,
            "original_duration_days": scoped.original_duration_days,
            "created_at": scoped.created_at,
            "expires_at": scoped.expires_at,
            "expiration_notice_sent_at": scoped.expiration_notice_sent_at,
            "extend_eligible": _is_extend_eligible(
                status=effective_status,
                expires_at=scoped.expires_at,
            ),
        }

    def update_key_alias(self, current_user: CurrentUser, key_id: str, key_alias: str) -> dict:
        if current_user.role != "admin":
            raise ApiError("FORBIDDEN", "admin role required", 403)

        normalized_alias = validate_safe_persisted_text(
            field_name="key_alias",
            value=key_alias,
            required=True,
            restrict_special_chars=True,
            allow_spaces=False,
        )
        if self.key_repo.alias_exists(normalized_alias, exclude_key_id=key_id):
            raise ApiError("KEY_ALIAS_DUPLICATE", "key_alias already exists", 409)

        exists = self.key_repo.get_key_detail(key_id, "admin", current_user.account)
        if exists is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)

        key, application = self._load_key_with_application(key_id)
        if self._provider_operates_remotely():
            plaintext = self._decrypt_key_for_provider(key)
            config = self._get_provider_update_config_for_application(application)
            try:
                self.provider_client.update_key(
                    self._build_provider_update_payload(
                        plaintext=plaintext,
                        duration_days=application.original_duration_days,
                        config=config,
                        key_alias=normalized_alias,
                    )
                )
            except ProviderBadRequestError as exc:
                raise ApiError("VALIDATION_ERROR", str(exc), 422) from exc
            except ProviderUnavailableError as exc:
                raise ApiError("PROVIDER_UNAVAILABLE", "provider unavailable", 503) from exc

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
            "duration_days": updated.duration_days,
            "original_duration_days": updated.original_duration_days,
            "created_at": updated.created_at,
            "expires_at": updated.expires_at,
        }

    def _load_key_with_application(self, key_id: str) -> tuple[ApiKey, ApiKeyApplication]:
        row = (
            self.session.query(ApiKey, ApiKeyApplication)
            .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
            .filter(ApiKey.id == key_id)
            .first()
        )
        if row is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)
        return row

    def _decrypt_key_for_provider(self, key: ApiKey) -> str:
        if not key.key_ciphertext or not key.key_kek_version:
            raise ApiError("KEY_NOT_REVEALABLE", "key plaintext is not available", 409)
        try:
            return self.crypto.decrypt(key.key_ciphertext)
        except Exception as exc:  # noqa: BLE001
            raise ApiError("KEY_NOT_REVEALABLE", "key plaintext is not available", 409) from exc

    def _provider_metadata(self, *, request_id: str | None, operation_id: str | None) -> dict:
        return {
            "provider_request_id": request_id,
            "provider_operation_id": operation_id,
        }

    def _get_provider_update_config_for_application(self, application: ApiKeyApplication) -> IssuanceConfigValues:
        if (
            application.max_budget is not None
            and application.budget_duration is not None
            and application.tpm_limit is not None
            and application.rpm_limit is not None
            and application.max_parallel_requests is not None
        ):
            return IssuanceConfigValues(
                max_budget=str(application.max_budget),
                budget_duration=str(application.budget_duration),
                tpm_limit=int(application.tpm_limit),
                rpm_limit=int(application.rpm_limit),
                max_parallel_requests=int(application.max_parallel_requests),
            )
        return self._get_limit_strategy_values()

    def revoke_key(self, current_user: CurrentUser, key_id: str) -> dict:
        exists = self.key_repo.get_key_detail(key_id, "admin", current_user.account)
        if exists is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)

        allowed = self.key_repo.get_key_detail(key_id, current_user.role, current_user.account)
        if allowed is None:
            raise ApiError("KEY_NOT_OWNED_BY_USER", "key is not owned by requester", 403)

        key, application = self._load_key_with_application(key_id)
        if key.status != "active":
            raise ApiError("KEY_NOT_ACTIVE", "key is not active", 409)

        provider_metadata: dict = {}
        try:
            plaintext = self._decrypt_key_for_provider(key)
            if self._provider_operates_remotely():
                provider_result = self.provider_client.delete_key({"keys": [plaintext]})
                provider_metadata = self._provider_metadata(
                    request_id=provider_result.request_id,
                    operation_id=provider_result.operation_id,
                )
        except ProviderBadRequestError as exc:
            raise ApiError("VALIDATION_ERROR", str(exc), 422) from exc
        except ProviderUnavailableError as exc:
            raise ApiError("PROVIDER_UNAVAILABLE", "provider unavailable", 503) from exc

        key.status = "revoked"
        application.status = "revoked"
        application.revoked_at = datetime.now(UTC)
        application.updated_at = datetime.now(UTC)
        self.session.add(key)
        self.session.add(application)
        self.session.commit()
        return {"id": key.id, "status": key.status, **provider_metadata}

    def renew_key(self, current_user: CurrentUser, key_id: str) -> dict:
        exists = self.key_repo.get_key_detail(key_id, "admin", current_user.account)
        if exists is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)

        allowed = self.key_repo.get_key_detail(key_id, current_user.role, current_user.account)
        if allowed is None:
            raise ApiError("KEY_NOT_OWNED_BY_USER", "key is not owned by requester", 403)

        source_key, source_app = self._load_key_with_application(key_id)
        source_effective_status = _effective_status(status=source_key.status, expires_at=source_app.expires_at)
        if source_effective_status not in {"revoked", "expired"}:
            raise ApiError("KEY_NOT_RENEWABLE", "only revoked or expired key can be renewed", 409)
        if source_key.renewed_to_key_id:
            raise ApiError("KEY_ALREADY_RENEWED", "key already renewed", 409)

        config = self._get_limit_strategy_values()
        try:
            if self._provider_operates_remotely():
                provider_result, key_alias = self._retry_provider_alias_operation(
                    owner_account=source_app.account,
                    duration_days=source_app.duration_days,
                    config=config,
                    current_alias=source_key.key_alias,
                    operation=lambda payload: self.provider_client.generate_key(payload),
                )
                plaintext = provider_result.key_plaintext
                provider_metadata = self._provider_metadata(
                    request_id=provider_result.request_id,
                    operation_id=provider_result.operation_id,
                )
            else:
                plaintext = _generate_api_key()
                provider_metadata = {}
                key_alias = source_key.key_alias or _default_alias(source_app.account)
        except ProviderBadRequestError as exc:
            raise ApiError("VALIDATION_ERROR", str(exc), 422) from exc
        except ProviderUnavailableError as exc:
            raise ApiError("PROVIDER_UNAVAILABLE", "provider unavailable", 503) from exc

        identity = AuthIdentity(
            account=source_app.account,
            name=source_app.name,
            email=source_app.email,
            department=source_app.department,
            sysid=source_app.sysid,
        )
        now = datetime.now(UTC)
        is_proxy_submission = current_user.role == "admin" and current_user.account != source_app.account
        application = self.key_repo.create_application(
            ApplicationCreateInput(
                identity=identity,
                is_proxy_submission=is_proxy_submission,
                proxy_operator_account=current_user.account if is_proxy_submission else None,
                application_date=date.today(),
                duration_days=source_app.duration_days,
                original_duration_days=source_app.duration_days,
                purpose=source_app.purpose,
                max_budget=config.max_budget,
                budget_duration=config.budget_duration,
                tpm_limit=config.tpm_limit,
                rpm_limit=config.rpm_limit,
                max_parallel_requests=config.max_parallel_requests,
                issued_at=now,
                expires_at=_calc_expiration(now, source_app.duration_days),
            )
        )
        issued_key = self._create_key_record(application_id=application.id, plaintext=plaintext, key_alias=key_alias)

        source_key.renewed_to_key_id = issued_key.id
        source_app.updated_at = datetime.now(UTC)
        self.session.add(source_key)
        self.session.add(source_app)
        self.session.commit()
        return {
            "id": issued_key.id,
            "status": issued_key.status,
            "expires_at": application.expires_at,
            "renewed_from_key_id": source_key.id,
            "api_key_plaintext": plaintext,
            "email_warning": None,
            **provider_metadata,
        }

    def extend_key(self, current_user: CurrentUser, key_id: str) -> dict:
        exists = self.key_repo.get_key_detail(key_id, "admin", current_user.account)
        if exists is None:
            raise ApiError("VALIDATION_ERROR", "key not found", 404)

        allowed = self.key_repo.get_key_detail(key_id, current_user.role, current_user.account)
        if allowed is None:
            raise ApiError("KEY_NOT_OWNED_BY_USER", "key is not owned by requester", 403)

        source_key, source_app = self._load_key_with_application(key_id)
        source_effective_status = _effective_status(status=source_key.status, expires_at=source_app.expires_at)
        if source_effective_status != "active":
            raise ApiError("KEY_NOT_EXTENDABLE", "only active key can be extended", 409)
        now = datetime.now(UTC)
        next_duration_days = source_app.original_duration_days
        next_application_date, next_expires_at = _extended_terms(
            issued_at=source_app.issued_at,
            original_duration_days=source_app.original_duration_days,
            now=now,
        )

        provider_metadata: dict = {}
        config = self._get_limit_strategy_values()
        try:
            plaintext = self._decrypt_key_for_provider(source_key)
            if self._provider_operates_remotely():
                provider_result = self.provider_client.update_key(
                    self._build_provider_update_payload(
                        plaintext=plaintext,
                        duration_days=source_app.original_duration_days,
                        config=config,
                        key_alias=source_key.key_alias or _default_alias(source_app.account),
                    )
                )
                provider_metadata = self._provider_metadata(
                    request_id=provider_result.request_id,
                    operation_id=provider_result.operation_id,
                )
        except ProviderBadRequestError as exc:
            raise ApiError("VALIDATION_ERROR", str(exc), 422) from exc
        except ProviderUnavailableError as exc:
            raise ApiError("PROVIDER_UNAVAILABLE", "provider unavailable", 503) from exc

        source_app.application_date = next_application_date
        source_app.duration_days = next_duration_days
        source_app.expires_at = next_expires_at
        source_app.status = "active"
        source_key.status = "active"
        source_key.expiration_notice_sent_at = None
        source_app.updated_at = now
        self.session.add(source_key)
        self.session.add(source_app)
        self.session.commit()
        return {
            "id": source_key.id,
            "status": source_key.status,
            "expires_at": source_app.expires_at,
            **provider_metadata,
        }

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
        owner_account: str | None = None,
        owner_name: str | None = None,
        owner_email: str | None = None,
        owner_department: str | None = None,
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
            filters=ApiKeyUserStatisticsFilter(
                q=q.strip() if q else None,
                owner_account=owner_account.strip() if owner_account else None,
                owner_name=owner_name.strip() if owner_name else None,
                owner_email=owner_email.strip() if owner_email else None,
                owner_department=owner_department.strip() if owner_department else None,
                from_date=from_date,
                to_date=to_date,
            ),
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
    return f"{_key_prefix_for_env(get_settings().app_env)}{suffix}"
