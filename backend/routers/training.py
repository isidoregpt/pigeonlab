from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import aiosqlite
from database import get_db_path
from datetime import datetime

router = APIRouter()


# --- Clips ---


@router.get("/clips")
async def get_clips(pigeon: Optional[str] = None, labeled: Optional[str] = None):
    """Return clip library items with optional filtering."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT c.*,
                   bl.behavior_class AS label,
                   bl.labeler
            FROM clip_library c
            LEFT JOIN behavior_labels bl ON bl.clip_id = c.id
            WHERE 1=1
        """
        params: list = []
        if pigeon and pigeon != "all":
            query += " AND c.pigeon_id = ?"
            params.append(pigeon)
        if labeled == "labeled":
            query += " AND bl.id IS NOT NULL"
        elif labeled == "unlabeled":
            query += " AND bl.id IS NULL"
        query += " ORDER BY c.created_at DESC"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# --- Label ---


class LabelPayload(BaseModel):
    clip_id: int
    behavior_class: str
    labeler: str = "lab_user"


@router.post("/label")
async def label_clip(payload: LabelPayload):
    """Label a clip with a behavior class."""
    async with aiosqlite.connect(get_db_path()) as db:
        now = datetime.utcnow().isoformat()
        await db.execute(
            """INSERT INTO behavior_labels (clip_id, behavior_class, labeler, labeled_at)
               VALUES (?, ?, ?, ?)""",
            (payload.clip_id, payload.behavior_class, payload.labeler, now),
        )
        await db.commit()
        return {
            "clip_id": payload.clip_id,
            "behavior_class": payload.behavior_class,
            "status": "labeled",
        }


# --- Class counts ---


@router.get("/class-counts")
async def get_class_counts():
    """Return per-class clip counts for training readiness."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT behavior_class, COUNT(*) as count
               FROM behavior_labels
               GROUP BY behavior_class"""
        )
        rows = await cursor.fetchall()
        return {row["behavior_class"]: row["count"] for row in rows}


# --- Start training ---


class TrainPayload(BaseModel):
    backbone: str = "r3d_18"
    epochs: int = 50
    batch_size: int = 16
    learning_rate: float = 0.001
    freeze_backbone: bool = False
    behavior_classes: list[str] = []


@router.post("/start")
async def start_training(payload: TrainPayload):
    """Start a training job (stub — returns mock job status)."""
    return {
        "job_id": "train_001",
        "status": "started",
        "config": payload.model_dump(),
    }


# --- Training status ---


@router.get("/status/{job_id}")
async def training_status(job_id: str):
    """Poll training job status (stub)."""
    return {
        "job_id": job_id,
        "status": "running",
        "epoch": 0,
        "total_epochs": 50,
        "progress": 0.0,
    }


# --- Model registry ---


@router.get("/models")
async def get_models():
    """Return all trained models."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM model_registry ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


@router.post("/models/{model_id}/activate")
async def activate_model(model_id: int):
    """Set a model as the active model."""
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute("UPDATE model_registry SET is_active = 0")
        await db.execute(
            "UPDATE model_registry SET is_active = 1 WHERE id = ?", (model_id,)
        )
        await db.commit()
        return {"model_id": model_id, "is_active": True}


# --- Reinfer ---


@router.post("/reinfer")
async def reinfer_all():
    """Rerun inference on all videos with the active model (stub)."""
    return {
        "status": "started",
        "job_id": "reinfer_001",
        "message": "Re-inference started on all videos with the active model.",
    }


# --- Legacy route ---


@router.get("/")
async def get_training():
    return {"status": "ok", "route": "training"}
