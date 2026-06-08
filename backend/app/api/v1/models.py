from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.schemas.common import ErrorResponse
from app.schemas.models import ModelListResponse
from app.services.models_service import ModelsService

router = APIRouter()


@router.get(
    "/models",
    response_model=ModelListResponse,
    responses={503: {"model": ErrorResponse, "description": "Provider is unavailable"}},
)
def list_models(current_user: CurrentUser = Depends(get_current_user)) -> dict:
    service = ModelsService()
    return service.list_models(current_user=current_user)
