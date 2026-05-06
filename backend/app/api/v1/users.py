from fastapi import APIRouter

router = APIRouter()


@router.get("/users")
async def list_users() -> dict[str, list]:
    return {"items": []}
