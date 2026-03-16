from fastapi import APIRouter

from database import get_connection

router = APIRouter()


@router.get("/zones")
async def list_zones():
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT current_zone FROM features WHERE current_zone IS NOT NULL ORDER BY current_zone"
    ).fetchall()
    conn.close()
    return {"zones": [row["current_zone"] for row in rows]}
