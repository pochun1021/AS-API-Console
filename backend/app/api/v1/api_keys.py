from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi import Response
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import csrf_protected, enforce_rate_limit, validate_date_window, validate_search_keyword
from app.schemas.common import ErrorResponse
from app.schemas.api_keys import (
    ApiKeyDetailResponse,
    ApiKeyAliasUpdateRequest,
    ApiKeyListResponse,
    ApiKeyRevealResponse,
    ApiKeyUserStatisticsResponse,
    LimitStrategyConfigResponse,
    LimitStrategyConfigUpdateRequest,
    ApplicationCreateRequest,
    ApplicationCreateResponse,
    ExtendRequest,
    ExtendResponse,
    RenewResponse,
    RevokeResponse,
)
from app.services.api_keys_service import ApiKeysService
from app.services.operation_audit_service import (
    OperationAuditService,
    extract_request_audit_context,
    summarize_operation_audit_error,
)
from db.session import get_db

router = APIRouter()
settings = get_settings()


@router.post(
    "/api-keys/applications",
    response_model=ApplicationCreateResponse,
    status_code=201,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("api-key-application", settings.application_rate_limit)],
)
def create_application(
    payload: ApplicationCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    event_type = "api_key_application"
    action = "create"
    target_type = "api_key_application"
    service = ApiKeysService(db)
    try:
        result = service.create_application(
            current_user=current_user,
            application_date=payload.application_date,
            duration_days=payload.duration_days,
            purpose=payload.purpose,
            target_identity=payload.target_identity.model_dump() if payload.target_identity else None,
        )
    except ApiError as exc:
        db.rollback()
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type=target_type,
            context=context,
            metadata={
                "duration_days": payload.duration_days,
                "is_proxy_submission": payload.target_identity is not None,
            },
        )
        raise
    except Exception as exc:
        db.rollback()
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="INTERNAL_ERROR",
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type=target_type,
            context=context,
            metadata={
                "duration_days": payload.duration_days,
                "is_proxy_submission": payload.target_identity is not None,
            },
        )
        raise
    audit.log(
        event_type=event_type,
        action=action,
        result="success",
        actor=current_user,
        target_type=target_type,
        target_id=result["application"]["id"],
        context=context,
        metadata={
            "application_id": result["application"]["id"],
            "duration_days": payload.duration_days,
            "is_proxy_submission": payload.target_identity is not None,
            "provider_request_id": result.get("provider_request_id"),
            "provider_operation_id": result.get("provider_operation_id"),
        },
    )
    return result


@router.get("/api-keys", response_model=ApiKeyListResponse)
def list_api_keys(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    owner_account: str | None = Query(default=None),
    owner_name: str | None = Query(default=None),
    key_alias: str | None = Query(default=None),
    application_date_from: date | None = Query(default=None),
    application_date_to: date | None = Query(default=None),
    from_date_legacy: date | None = Query(default=None, alias="from"),
    to_date_legacy: date | None = Query(default=None, alias="to"),
    expires_from: datetime | None = Query(default=None),
    expires_to: datetime | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    resolved_application_date_from = application_date_from or from_date_legacy
    resolved_application_date_to = application_date_to or to_date_legacy
    validate_date_window(resolved_application_date_from, resolved_application_date_to)
    validate_search_keyword(owner_account)
    validate_search_keyword(owner_name)
    validate_search_keyword(key_alias)
    return service.list_keys(
        current_user=current_user,
        page=page,
        page_size=page_size,
        status=status,
        owner_account=owner_account,
        owner_name=owner_name,
        key_alias=key_alias,
        application_date_from=resolved_application_date_from,
        application_date_to=resolved_application_date_to,
        expires_from=expires_from,
        expires_to=expires_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/api-keys/statistics/users", response_model=ApiKeyUserStatisticsResponse)
def list_api_key_user_statistics(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None),
    scope: str = Query(default="all"),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    owner_account: str | None = Query(default=None),
    owner_name: str | None = Query(default=None),
    owner_email: str | None = Query(default=None),
    owner_department: str | None = Query(default=None),
    sort_by: str = Query(default="total_applications"),
    sort_dir: str = Query(default="desc"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    validate_date_window(from_date, to_date)
    validate_search_keyword(q)
    validate_search_keyword(owner_account)
    validate_search_keyword(owner_name)
    validate_search_keyword(owner_email)
    validate_search_keyword(owner_department)
    return service.list_user_statistics(
        current_user=current_user,
        page=page,
        page_size=page_size,
        q=q,
        scope=scope,
        from_date=from_date,
        to_date=to_date,
        owner_account=owner_account,
        owner_name=owner_name,
        owner_email=owner_email,
        owner_department=owner_department,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get(
    "/api-keys/{key_id}",
    response_model=ApiKeyDetailResponse,
    responses={
        403: {"model": ErrorResponse, "description": "User is not allowed to access this key"},
        404: {"model": ErrorResponse, "description": "API key was not found"},
    },
)
def get_api_key_detail(
    key_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    return service.get_key_detail(current_user=current_user, key_id=key_id)


@router.post(
    "/api-keys/{key_id}/revoke",
    response_model=RevokeResponse,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("api-key-revoke", settings.application_rate_limit)],
)
def revoke_api_key(
    key_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    event_type = "api_key"
    action = "revoke"
    target_type = "api_key"
    service = ApiKeysService(db)
    try:
        result = service.revoke_key(current_user=current_user, key_id=key_id)
    except ApiError as exc:
        db.rollback()
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type=target_type,
            target_id=key_id,
            context=context,
            metadata={"key_id": key_id},
        )
        raise
    except Exception as exc:
        db.rollback()
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="INTERNAL_ERROR",
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type=target_type,
            target_id=key_id,
            context=context,
            metadata={"key_id": key_id},
        )
        raise
    audit.log(
        event_type=event_type,
        action=action,
        result="success",
        actor=current_user,
        target_type=target_type,
        target_id=result["id"],
        context=context,
        metadata={
            "key_id": result["id"],
            "status": result["status"],
            "provider_request_id": result.get("provider_request_id"),
            "provider_operation_id": result.get("provider_operation_id"),
        },
    )
    return result


@router.post(
    "/api-keys/{key_id}/renew",
    response_model=RenewResponse,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("api-key-renew", settings.application_rate_limit)],
)
def renew_api_key(
    key_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    event_type = "api_key"
    action = "renew"
    target_type = "api_key"
    service = ApiKeysService(db)
    try:
        result = service.renew_key(current_user=current_user, key_id=key_id)
    except ApiError as exc:
        db.rollback()
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type=target_type,
            target_id=key_id,
            context=context,
            metadata={"key_id": key_id},
        )
        raise
    except Exception as exc:
        db.rollback()
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="INTERNAL_ERROR",
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type=target_type,
            target_id=key_id,
            context=context,
            metadata={"key_id": key_id},
        )
        raise
    audit.log(
        event_type=event_type,
        action=action,
        result="success",
        actor=current_user,
        target_type=target_type,
        target_id=result["id"],
        context=context,
        metadata={
            "key_id": result["id"],
            "status": result["status"],
            "provider_request_id": result.get("provider_request_id"),
            "provider_operation_id": result.get("provider_operation_id"),
        },
    )
    return result


@router.post(
    "/api-keys/{key_id}/extend",
    response_model=ExtendResponse,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("api-key-extend", settings.application_rate_limit)],
)
def extend_api_key(
    key_id: str,
    request: Request,
    payload: ExtendRequest | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    event_type = "api_key"
    action = "extend"
    target_type = "api_key"
    service = ApiKeysService(db)
    try:
        result = service.extend_key(current_user=current_user, key_id=key_id)
    except ApiError as exc:
        db.rollback()
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type=target_type,
            target_id=key_id,
            context=context,
            metadata={"key_id": key_id},
        )
        raise
    except Exception as exc:
        db.rollback()
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="INTERNAL_ERROR",
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type=target_type,
            target_id=key_id,
            context=context,
            metadata={"key_id": key_id},
        )
        raise
    audit.log(
        event_type=event_type,
        action=action,
        result="success",
        actor=current_user,
        target_type=target_type,
        target_id=result["id"],
        context=context,
        metadata={
            "key_id": result["id"],
            "status": result["status"],
            "provider_request_id": result.get("provider_request_id"),
            "provider_operation_id": result.get("provider_operation_id"),
        },
    )
    return result


@router.post(
    "/api-keys/{key_id}/reveal",
    response_model=ApiKeyRevealResponse,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("api-key-reveal", settings.reveal_rate_limit)],
)
def reveal_api_key(
    key_id: str,
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    service = ApiKeysService(db)
    return service.reveal_key_plaintext(current_user=current_user, key_id=key_id)


@router.patch("/api-keys/{key_id}", response_model=ApiKeyDetailResponse, dependencies=[Depends(csrf_protected)])
def update_api_key_alias(
    key_id: str,
    payload: ApiKeyAliasUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    try:
        return service.update_key_alias(current_user=current_user, key_id=key_id, key_alias=payload.key_alias)
    except Exception:
        db.rollback()
        raise


@router.get("/limit-strategy-config", response_model=LimitStrategyConfigResponse)
def get_limit_strategy_config(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    return service.get_limit_strategy_config(current_user=current_user)


@router.patch(
    "/limit-strategy-config",
    response_model=LimitStrategyConfigResponse,
    dependencies=[Depends(csrf_protected), enforce_rate_limit("limit-strategy-update", settings.admin_mutation_rate_limit)],
    responses={
        403: {"model": ErrorResponse, "description": "CSRF token is invalid or admin role is required"},
        422: {"model": ErrorResponse, "description": "Limit strategy payload is invalid"},
    },
)
def update_limit_strategy_config(
    payload: LimitStrategyConfigUpdateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    audit = OperationAuditService(db)
    context = extract_request_audit_context(request)
    event_type = "limit_strategy_config"
    action = "update"
    target_type = "limit_strategy_config"
    target_id = "global-limit-strategy-config"
    service = ApiKeysService(db)
    try:
        result = service.update_limit_strategy_config(current_user=current_user, payload=payload.model_dump())
    except ApiError as exc:
        db.rollback()
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code=exc.code,
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={
                "budget_duration": payload.budget_duration,
                "rate_limit_tpm": payload.rate_limit_tpm,
                "rate_limit_rpm": payload.rate_limit_rpm,
                "max_parallel_requests": payload.max_parallel_requests,
            },
        )
        raise
    except Exception as exc:
        db.rollback()
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="INTERNAL_ERROR",
            error_detail=summarize_operation_audit_error(exc),
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={
                "budget_duration": payload.budget_duration,
                "rate_limit_tpm": payload.rate_limit_tpm,
                "rate_limit_rpm": payload.rate_limit_rpm,
                "max_parallel_requests": payload.max_parallel_requests,
            },
        )
        raise
    audit.log(
        event_type=event_type,
        action=action,
        result="success",
        actor=current_user,
        target_type=target_type,
        target_id=target_id,
        context=context,
        metadata={
            "budget_duration": result["budget_duration"],
            "rate_limit_tpm": result["rate_limit_tpm"],
            "rate_limit_rpm": result["rate_limit_rpm"],
            "max_parallel_requests": result["max_parallel_requests"],
        },
    )
    return result
