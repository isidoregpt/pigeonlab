from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_export():
    return {"status": "ok", "route": "export"}
