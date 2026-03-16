from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import uuid
import json
import aiosqlite
from database import get_db_path
from datetime import datetime

router = APIRouter()

MIN_CLIPS_PER_CLASS = 20


# --- Clips ---


@router.get("/clips")
async def get_clips(
    labeled: Optional[str] = Query(None, description="true/false/null for all"),
    pigeon: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Query clip_library joined with behavior_labels, return paginated results."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row

        where_clauses = ["1=1"]
        params: list = []

        if pigeon and pigeon != "all":
            where_clauses.append("c.pigeon_id = ?")
            params.append(pigeon)

        if labeled == "true" or labeled == "labeled":
            where_clauses.append("bl.id IS NOT NULL")
        elif labeled == "false" or labeled == "unlabeled":
            where_clauses.append("bl.id IS NULL")

        where_sql = " AND ".join(where_clauses)

        # Count total
        count_query = f"""
            SELECT COUNT(*) as total
            FROM clip_library c
            LEFT JOIN behavior_labels bl ON bl.clip_id = c.id
            WHERE {where_sql}
        """
        cursor = await db.execute(count_query, params)
        total_row = await cursor.fetchone()
        total = total_row["total"] if total_row else 0

        # Paginated results
        offset = (page - 1) * per_page
        data_query = f"""
            SELECT c.*,
                   bl.id AS label_id,
                   bl.behavior_class AS label,
                   bl.labeler,
                   bl.labeled_at,
                   bl.split
            FROM clip_library c
            LEFT JOIN behavior_labels bl ON bl.clip_id = c.id
            WHERE {where_sql}
            ORDER BY c.created_at DESC
            LIMIT ? OFFSET ?
        """
        cursor = await db.execute(data_query, [*params, per_page, offset])
        rows = await cursor.fetchall()

        return {
            "clips": [dict(row) for row in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        }


# --- Label ---


class LabelPayload(BaseModel):
    clip_id: int
    behavior_class: str
    labeler: str = "lab_user"
    split: str = "train"
    notes: Optional[str] = None


@router.post("/label")
async def label_clip(payload: LabelPayload):
    """Insert into behavior_labels, return created label."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row

        # Verify clip exists
        cursor = await db.execute(
            "SELECT id FROM clip_library WHERE id = ?", (payload.clip_id,)
        )
        clip = await cursor.fetchone()
        if not clip:
            raise HTTPException(status_code=404, detail=f"Clip {payload.clip_id} not found")

        now = datetime.utcnow().isoformat()
        cursor = await db.execute(
            """INSERT INTO behavior_labels (clip_id, behavior_class, labeler, labeled_at, split, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                payload.clip_id,
                payload.behavior_class,
                payload.labeler,
                now,
                payload.split,
                payload.notes,
            ),
        )
        await db.commit()
        label_id = cursor.lastrowid

        return {
            "id": label_id,
            "clip_id": payload.clip_id,
            "behavior_class": payload.behavior_class,
            "labeler": payload.labeler,
            "labeled_at": now,
            "split": payload.split,
        }


# --- Readiness ---


@router.get("/readiness")
async def get_readiness():
    """Query behavior_labels grouped by behavior_class, compare to minimum threshold."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """SELECT behavior_class, COUNT(*) as count
               FROM behavior_labels
               GROUP BY behavior_class
               ORDER BY behavior_class"""
        )
        rows = await cursor.fetchall()

        classes = {}
        total_clips = 0
        all_ready = True

        for row in rows:
            cls = row["behavior_class"]
            count = row["count"]
            total_clips += count
            ready = count >= MIN_CLIPS_PER_CLASS
            if not ready:
                all_ready = False
            classes[cls] = {
                "count": count,
                "minimum": MIN_CLIPS_PER_CLASS,
                "ready": ready,
                "needed": max(0, MIN_CLIPS_PER_CLASS - count),
            }

        return {
            "classes": classes,
            "total_labeled_clips": total_clips,
            "min_per_class": MIN_CLIPS_PER_CLASS,
            "all_ready": all_ready and len(classes) > 0,
            "num_classes": len(classes),
        }


# --- Class counts (kept for backward compat with frontend) ---


@router.get("/class-counts")
async def get_class_counts():
    """Return per-class clip counts."""
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
    """Validate readiness, insert into model_registry, return job stub.

    Does not implement actual PyTorch training — that is a future phase.
    """
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row

        # Validate readiness: check each requested class has enough clips
        if payload.behavior_classes:
            placeholders = ",".join("?" for _ in payload.behavior_classes)
            cursor = await db.execute(
                f"""SELECT behavior_class, COUNT(*) as count
                    FROM behavior_labels
                    WHERE behavior_class IN ({placeholders})
                    GROUP BY behavior_class""",
                payload.behavior_classes,
            )
            rows = await cursor.fetchall()
            counts = {row["behavior_class"]: row["count"] for row in rows}

            insufficient = []
            for cls in payload.behavior_classes:
                count = counts.get(cls, 0)
                if count < MIN_CLIPS_PER_CLASS:
                    insufficient.append(
                        f"{cls}: {count}/{MIN_CLIPS_PER_CLASS}"
                    )

            if insufficient:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient labeled clips for: {', '.join(insufficient)}",
                )

        # Generate version string
        now = datetime.utcnow()
        version = f"v{now.strftime('%Y%m%d_%H%M%S')}"
        job_id = f"train_{uuid.uuid4().hex[:8]}"

        # Count total training clips
        if payload.behavior_classes:
            placeholders = ",".join("?" for _ in payload.behavior_classes)
            cursor = await db.execute(
                f"SELECT COUNT(*) as cnt FROM behavior_labels WHERE behavior_class IN ({placeholders})",
                payload.behavior_classes,
            )
        else:
            cursor = await db.execute("SELECT COUNT(*) as cnt FROM behavior_labels")
        row = await cursor.fetchone()
        training_clips = row["cnt"] if row else 0

        # Build config JSON
        config = payload.model_dump()
        config["job_id"] = job_id

        # Insert into model_registry with is_active=0
        cursor = await db.execute(
            """INSERT INTO model_registry
               (model_name, model_type, version, training_config, training_clips, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, 0, ?)""",
            (
                f"behavior_{payload.backbone}",
                "behavior_classifier",
                version,
                json.dumps(config),
                training_clips,
                now.isoformat(),
            ),
        )
        await db.commit()
        model_id = cursor.lastrowid

        return {
            "job_id": job_id,
            "model_id": model_id,
            "version": version,
            "status": "started",
            "estimated_duration_minutes": None,
            "training_clips": training_clips,
            "config": config,
        }


# --- Training status ---


@router.get("/status/{job_id}")
async def training_status(job_id: str):
    """Return placeholder training status.

    Actual training progress tracking is a future phase.
    """
    return {
        "job_id": job_id,
        "epoch": 0,
        "total_epochs": 0,
        "loss": None,
        "val_acc": None,
        "status": "queued",
        "progress": 0.0,
    }


# --- Model registry ---


@router.get("/models")
async def get_models():
    """Return all rows from model_registry ordered by created_at desc."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM model_registry ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


@router.post("/models/{model_id}/activate")
async def activate_model(model_id: int):
    """Set is_active=1 for this model, 0 for all others of same model_type."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row

        # Get the model to find its type
        cursor = await db.execute(
            "SELECT id, model_type FROM model_registry WHERE id = ?", (model_id,)
        )
        model = await cursor.fetchone()
        if not model:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

        model_type = model["model_type"]

        # Deactivate all models of the same type
        await db.execute(
            "UPDATE model_registry SET is_active = 0 WHERE model_type = ?",
            (model_type,),
        )
        # Activate the requested model
        await db.execute(
            "UPDATE model_registry SET is_active = 1 WHERE id = ?", (model_id,)
        )
        await db.commit()

        return {
            "model_id": model_id,
            "model_type": model_type,
            "is_active": True,
        }


# --- Reinfer ---


class ReinferPayload(BaseModel):
    model_version: Optional[str] = None
    scope: str = "all"
    skip_already_inferred: bool = False
    only_approved_videos: bool = False


@router.post("/reinfer")
async def reinfer_videos(payload: ReinferPayload):
    """Count eligible videos and return a job stub.

    Does not run actual inference — that is a future phase.
    """
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row

        # Resolve model version
        if payload.model_version:
            cursor = await db.execute(
                "SELECT version FROM model_registry WHERE version = ?",
                (payload.model_version,),
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Model version '{payload.model_version}' not found",
                )
            model_version = payload.model_version
        else:
            # Use active model
            cursor = await db.execute(
                "SELECT version FROM model_registry WHERE is_active = 1 LIMIT 1"
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(
                    status_code=400,
                    detail="No active model found. Activate a model first.",
                )
            model_version = row["version"]

        # Count eligible videos
        where_clauses = ["processing_status = 'completed'"]
        params: list = []

        if payload.only_approved_videos:
            where_clauses.append("review_status = 'approved'")

        if payload.skip_already_inferred:
            where_clauses.append("(model_version IS NULL OR model_version != ?)")
            params.append(model_version)

        where_sql = " AND ".join(where_clauses)

        cursor = await db.execute(
            f"SELECT COUNT(*) as cnt FROM videos WHERE {where_sql}", params
        )
        eligible_row = await cursor.fetchone()
        eligible = eligible_row["cnt"] if eligible_row else 0

        # Count skipped
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM videos WHERE processing_status = 'completed'"
        )
        total_row = await cursor.fetchone()
        total_completed = total_row["cnt"] if total_row else 0
        skipped = total_completed - eligible

        job_id = f"reinfer_{uuid.uuid4().hex[:8]}"

        return {
            "job_id": job_id,
            "model_version": model_version,
            "videos_eligible": eligible,
            "videos_skipped": skipped,
            "status": "started",
        }


# --- Legacy route ---


@router.get("/")
async def get_training():
    return {"status": "ok", "route": "training"}
