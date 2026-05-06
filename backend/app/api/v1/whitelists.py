from fastapi import APIRouter

router = APIRouter()


@router.get("/whitelists")
async def list_whitelists() -> dict[str, list]:
    return {"items": []}
