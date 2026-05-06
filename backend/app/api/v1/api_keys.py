from fastapi import APIRouter

router = APIRouter()


@router.get("/api-keys")
async def list_api_keys() -> dict[str, list]:
    return {"items": []}
