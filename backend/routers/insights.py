from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_insights():
    return {"status": "ok", "route": "insights"}
