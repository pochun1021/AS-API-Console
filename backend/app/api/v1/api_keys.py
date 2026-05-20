from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.errors import ApiError
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
    RenewResponse,
    RevokeResponse,
)
from app.services.api_keys_service import ApiKeysService
from app.services.operation_audit_service import OperationAuditService, extract_request_audit_context
from db.session import get_db

router = APIRouter()


@router.post("/api-keys/applications", response_model=ApplicationCreateResponse, status_code=201)
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
            duration_months=payload.duration_months,
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
            actor=current_user,
            target_type=target_type,
            context=context,
            metadata={
                "duration_months": payload.duration_months,
                "is_proxy_submission": payload.target_identity is not None,
            },
        )
        raise
    except Exception:
        db.rollback()
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="INTERNAL_ERROR",
            actor=current_user,
            target_type=target_type,
            context=context,
            metadata={
                "duration_months": payload.duration_months,
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
            "duration_months": payload.duration_months,
            "is_proxy_submission": payload.target_identity is not None,
        },
    )
    return result


@router.get("/api-keys", response_model=ApiKeyListResponse)
def list_api_keys(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    owner_account: str | None = Query(default=None),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    return service.list_keys(
        current_user=current_user,
        page=page,
        page_size=page_size,
        status=status,
        owner_account=owner_account,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/api-keys/statistics/users", response_model=ApiKeyUserStatisticsResponse)
def list_api_key_user_statistics(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None),
    scope: str = Query(default="all"),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    sort_by: str = Query(default="total_applications"),
    sort_dir: str = Query(default="desc"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    return service.list_user_statistics(
        current_user=current_user,
        page=page,
        page_size=page_size,
        q=q,
        scope=scope,
        from_date=from_date,
        to_date=to_date,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/api-keys/{key_id}", response_model=ApiKeyDetailResponse)
def get_api_key_detail(
    key_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    return service.get_key_detail(current_user=current_user, key_id=key_id)


@router.post("/api-keys/{key_id}/revoke", response_model=RevokeResponse)
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
            actor=current_user,
            target_type=target_type,
            target_id=key_id,
            context=context,
            metadata={"key_id": key_id},
        )
        raise
    except Exception:
        db.rollback()
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="INTERNAL_ERROR",
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
        metadata={"key_id": result["id"], "status": result["status"]},
    )
    return result


@router.post("/api-keys/{key_id}/renew", response_model=RenewResponse)
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
            actor=current_user,
            target_type=target_type,
            target_id=key_id,
            context=context,
            metadata={"key_id": key_id},
        )
        raise
    except Exception:
        db.rollback()
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="INTERNAL_ERROR",
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
        metadata={"key_id": result["id"], "status": result["status"]},
    )
    return result


@router.post("/api-keys/{key_id}/reveal", response_model=ApiKeyRevealResponse)
def reveal_api_key(
    key_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    service = ApiKeysService(db)
    return service.reveal_key_plaintext(current_user=current_user, key_id=key_id)


@router.patch("/api-keys/{key_id}", response_model=ApiKeyDetailResponse)
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


@router.patch("/limit-strategy-config", response_model=LimitStrategyConfigResponse)
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
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={
                "budget_duration": payload.budget_duration,
                "rate_limit_tpm": payload.rate_limit_tpm,
                "rate_limit_rpm": payload.rate_limit_rpm,
            },
        )
        raise
    except Exception:
        db.rollback()
        audit.log(
            event_type=event_type,
            action=action,
            result="failure",
            error_code="INTERNAL_ERROR",
            actor=current_user,
            target_type=target_type,
            target_id=target_id,
            context=context,
            metadata={
                "budget_duration": payload.budget_duration,
                "rate_limit_tpm": payload.rate_limit_tpm,
                "rate_limit_rpm": payload.rate_limit_rpm,
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
        },
    )
    return result
