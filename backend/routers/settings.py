import os

from fastapi import APIRouter

from database import get_connection, DB_PATH

router = APIRouter()


@router.get("/zones")
async def list_zones():
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT current_zone FROM features WHERE current_zone IS NOT NULL ORDER BY current_zone"
    ).fetchall()
    conn.close()
    return {"zones": [row["current_zone"] for row in rows]}


@router.get("/info")
async def system_info():
    db_path = str(DB_PATH)
    try:
        db_size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2)
    except OSError:
        db_size_mb = 0.0

    conn = get_connection()
    counts = {}
    for key, query in [
        ("total_videos", "SELECT COUNT(*) AS cnt FROM videos"),
        ("total_pigeons", "SELECT COUNT(*) AS cnt FROM pigeons"),
        ("total_features", "SELECT COUNT(*) AS cnt FROM features"),
        ("total_behaviors", "SELECT COUNT(*) AS cnt FROM behaviors"),
        ("total_clips", "SELECT COUNT(*) AS cnt FROM clip_library"),
        ("model_count", "SELECT COUNT(*) AS cnt FROM model_registry"),
    ]:
        row = conn.execute(query).fetchone()
        counts[key] = row["cnt"] if row else 0
    conn.close()

    return {
        "database_path": db_path,
        "database_size_mb": db_size_mb,
        **counts,
    }
