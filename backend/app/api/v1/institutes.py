from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.schemas.institutes import InstituteListResponse
from app.services.institutes_service import InstitutesService
from db.session import get_db

router = APIRouter()


@router.get("/institutes", response_model=InstituteListResponse)
def list_institutes(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _ = current_user
    service = InstitutesService(db)
    return service.list_active()
