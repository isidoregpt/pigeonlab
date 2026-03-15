from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_pigeons():
    return {"status": "ok", "route": "pigeons"}
