import os

from fastapi import APIRouter, HTTPException

from database import get_db, init_db, DB_PATH
import seed_data

router = APIRouter()


@router.get("/zones")
async def list_zones():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT current_zone FROM features WHERE current_zone IS NOT NULL ORDER BY current_zone"
        ).fetchall()
    return {"zones": [row["current_zone"] for row in rows]}


@router.get("/info")
async def system_info():
    db_path = str(DB_PATH)
    try:
        db_size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2)
    except OSError:
        db_size_mb = 0.0

    with get_db() as conn:
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

    return {
        "database_path": db_path,
        "database_size_mb": db_size_mb,
        **counts,
    }


@router.delete("/reset")
async def reset_database():
    """Drop the database file and recreate tables. Development use only."""
    if DB_PATH.exists():
        os.remove(DB_PATH)

    init_db()

    return {"status": "reset"}


@router.post("/seed")
async def seed_database():
    """Load sample data into the database. Fails if data already exists."""
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM pigeons").fetchone()
        if row and row["cnt"] > 0:
            raise HTTPException(
                status_code=409,
                detail="Data already exists. Use --force or reset first.",
            )

    seed_data.seed()
    return {"status": "seeded"}
