import os
import ipaddress
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from database import get_db, init_db, DB_PATH
import seed_data
from services.gemma_reviewer import get_gemma_status, save_gemma_config
from services.sam3 import get_sam3_status

router = APIRouter()


class GemmaSettingsUpdate(BaseModel):
    mode: str = "off"
    model: str = "gemma4:e4b"
    base_url: str = "http://localhost:11434"
    sample_interval_seconds: int = Field(default=15, ge=1, le=300)
    max_frames_per_video: int = Field(default=20, ge=1, le=200)
    confidence_threshold: float = Field(default=0.65, ge=0.0, le=1.0)


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _require_local_request(request: Request) -> None:
    if os.getenv("PIGEONLAB_ALLOW_REMOTE_DANGER", "").lower() in {"1", "true", "yes"}:
        return
    host = request.client.host if request.client else None
    if not _is_loopback(host):
        raise HTTPException(
            status_code=403,
            detail="Database reset is only available from localhost.",
        )


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


@router.get("/sam3")
async def sam3_info(load_model: bool = False):
    return get_sam3_status(load_model=load_model)


@router.get("/gemma")
async def gemma_info():
    return await get_gemma_status()


@router.put("/gemma")
async def update_gemma_settings(body: GemmaSettingsUpdate):
    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    save_gemma_config(payload)
    return await get_gemma_status()


@router.delete("/reset")
async def reset_database(request: Request):
    """Drop the database file and recreate tables. Development use only."""
    _require_local_request(request)

    for path in [DB_PATH, Path(f"{DB_PATH}-wal"), Path(f"{DB_PATH}-shm")]:
        if path.exists():
            os.remove(path)

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
