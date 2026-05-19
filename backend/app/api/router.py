from fastapi import APIRouter

from app.api.v1 import api_keys, notifications, operation_audit_logs, users, whitelists

api_router = APIRouter()
api_router.include_router(api_keys.router, tags=["api-keys"])
api_router.include_router(notifications.router, tags=["notifications"])
api_router.include_router(operation_audit_logs.router, tags=["operation-audit-logs"])
api_router.include_router(whitelists.router, tags=["whitelists"])
api_router.include_router(users.router, tags=["users"])
