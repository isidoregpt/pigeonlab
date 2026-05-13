import asyncio
import io
import json
import logging
import uuid
from enum import Enum
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from database import get_db
from services.ffmpeg_ingest import (
    default_chunk_seconds,
    default_output_dir,
    get_ffmpeg_status,
    ingest_folder,
    probe_duration,
    split_video,
)
from services.frame_extractor import FrameExtractor
from services.sam3 import get_sam3_status
from services.video_processor import VideoProcessor
from utils import get_default_reviewer

router = APIRouter()
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
UPLOADS_DIR = DATA_DIR / "videos" / "uploads"
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}

_processing_jobs: dict[str, asyncio.Task] = {}
_processing_job_results: dict[str, dict] = {}
_processing_cancel_events: dict[int, asyncio.Event] = {}
_processing_video_jobs: dict[int, str] = {}


# --- Schemas ---

class ProcessRequest(BaseModel):
    video_paths: list[str]
    camera_assignments: dict[str, str] = Field(default_factory=dict)
    text_prompt: str = ""
    expected_pigeon_count: int = Field(default=0, ge=0)
    session_id: str = ""


class FolderImportRequest(BaseModel):
    input_dir: str = ""
    output_dir: str = ""
    archive_dir: str = ""
    chunk_seconds: int = Field(default=60, ge=30, le=3600)
    archive_originals: bool = False
    process_now: bool = True
    expected_pigeon_count: int = Field(default=4, ge=0)
    text_prompt: str = "pigeon"
    session_prefix: str = ""
    limit: int | None = Field(default=None, ge=1, le=500)


class ReviewStatus(str, Enum):
    raw = "raw"
    reviewed = "reviewed"
    approved = "approved"
    rejected = "rejected"


class ReviewUpdate(BaseModel):
    review_status: ReviewStatus
    reviewer: str = Field(default_factory=get_default_reviewer)


# --- Helpers ---

def _row_to_dict(row) -> dict:
    return dict(row) if row else {}


def _chunk_group_status_label(status: str, completed: int, failed: int, total: int) -> str:
    if status == "completed":
        return f"Done ({completed}/{total})"
    if status == "failed":
        return f"Failed (0/{total})"
    if status == "partial":
        return f"Partial ({completed}/{total}, {failed} failed)"
    if status == "processing":
        return f"Processing ({completed}/{total})"
    if status == "cancelled":
        return f"Cancelled ({completed}/{total})"
    return f"Queued ({completed}/{total})"


def _chunk_group_status_from_counts(row: dict) -> dict:
    total = int(row.get("chunk_group_total") or 0)
    completed = int(row.get("chunk_group_completed") or 0)
    failed = int(row.get("chunk_group_failed") or 0)
    no_detections = int(row.get("chunk_group_no_detections") or 0)
    cancelled = int(row.get("chunk_group_cancelled") or 0)
    processing = int(row.get("chunk_group_processing") or 0)
    queued = int(row.get("chunk_group_queued") or 0)
    if total <= 0:
        return {}
    if completed == total:
        status = "completed"
    elif failed == total:
        status = "failed"
    elif cancelled == total:
        status = "cancelled"
    elif failed > 0 or completed > 0 or cancelled > 0 or no_detections > 0:
        status = "partial"
    elif processing > 0:
        status = "processing"
    else:
        status = "queued"
    if no_detections and status == "partial":
        label = f"Partial ({completed} done, {failed} failed, {no_detections} no-detections)"
    else:
        label = _chunk_group_status_label(status, completed, failed, total)
    return {
        "chunk_group_total": total,
        "chunk_group_completed": completed,
        "chunk_group_failed": failed,
        "chunk_group_no_detections": no_detections,
        "chunk_group_cancelled": cancelled,
        "chunk_group_processing": processing,
        "chunk_group_queued": queued,
        "chunk_group_status": status,
        "chunk_group_status_label": label,
    }


def _chunk_group_statuses(conn, group_ids: list[str]) -> dict[str, dict]:
    if not group_ids:
        return {}
    placeholders = ",".join("?" for _ in group_ids)
    rows = conn.execute(
        f"""SELECT chunk_group_id,
                   COUNT(*) AS chunk_group_total,
                   SUM(CASE WHEN processing_status = 'completed' THEN 1 ELSE 0 END) AS chunk_group_completed,
                   SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) AS chunk_group_failed,
                   SUM(CASE WHEN processing_status = 'completed_no_detections' THEN 1 ELSE 0 END)
                       AS chunk_group_no_detections,
                   SUM(CASE WHEN processing_status = 'cancelled' THEN 1 ELSE 0 END) AS chunk_group_cancelled,
                   SUM(CASE WHEN processing_status = 'processing' THEN 1 ELSE 0 END) AS chunk_group_processing,
                   SUM(CASE WHEN processing_status = 'queued' THEN 1 ELSE 0 END) AS chunk_group_queued
            FROM videos
            WHERE chunk_group_id IN ({placeholders})
            GROUP BY chunk_group_id""",
        group_ids,
    ).fetchall()
    return {
        row["chunk_group_id"]: _chunk_group_status_from_counts(dict(row))
        for row in rows
    }


def _attach_chunk_group_status(conn, videos: list[dict]) -> list[dict]:
    group_ids = sorted({
        str(video.get("chunk_group_id"))
        for video in videos
        if video.get("chunk_group_id")
    })
    statuses = _chunk_group_statuses(conn, group_ids)
    for video in videos:
        group_id = video.get("chunk_group_id")
        if group_id and group_id in statuses:
            video.update(statuses[group_id])
    return videos


def _video_insert_payload(entry: dict, session_id: str, camera_type: str) -> tuple:
    chunk_index = int(entry.get("chunk_index") or 1)
    chunk_count = int(entry.get("chunk_count") or 1)
    logical_name = (
        entry.get("logical_video_name")
        or entry.get("source_video_name")
        or entry.get("video_name")
    )
    original_source_path = (
        entry.get("original_source_path")
        or entry.get("source_path")
        or entry.get("video_path")
    )
    return (
        entry["video_name"],
        entry["video_path"],
        logical_name,
        original_source_path,
        entry.get("chunk_group_id"),
        chunk_index,
        chunk_count,
        entry.get("chunk_seconds"),
        session_id,
        camera_type,
    )


def _insert_video(conn, entry: dict, session_id: str, camera_type: str):
    return conn.execute(
        """INSERT INTO videos
           (video_name, source_path, logical_video_name, original_source_path,
            chunk_group_id, chunk_index, chunk_count, chunk_seconds,
            session_id, camera_type, processing_status, processing_error)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', NULL)""",
        _video_insert_payload(entry, session_id, camera_type),
    )


def _get_video_or_404(conn, video_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM videos WHERE video_id = ?", (video_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    return _row_to_dict(row)


def _require_sam3_ready() -> None:
    sam3_status = get_sam3_status(load_model=False)
    if not sam3_status["ready"]:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "SAM3 is not ready for video processing.",
                "errors": sam3_status["errors"],
                "warnings": sam3_status["warnings"],
            },
        )


def _import_session_id(prefix: str, source_stem: str) -> str:
    clean_prefix = prefix.strip().strip("_-")
    clean_stem = source_stem.strip() or "imported_video"
    return f"{clean_prefix}_{clean_stem}" if clean_prefix else clean_stem


def _form_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _form_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    import os

    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _auto_chunk_entries(entries: list[dict]) -> list[dict]:
    if not _env_bool("PIGEONLAB_VIDEO_AUTO_CHUNK_UPLOADS", True):
        return entries

    chunk_seconds = default_chunk_seconds()
    output_dir = default_output_dir()
    expanded: list[dict] = []

    for entry in entries:
        path = Path(entry["video_path"])
        duration = probe_duration(path)
        if duration is None or duration <= chunk_seconds:
            entry.setdefault("logical_video_name", entry.get("source_video_name", entry["video_name"]))
            entry.setdefault("original_source_path", entry.get("source_path", entry["video_path"]))
            entry.setdefault("chunk_index", 1)
            entry.setdefault("chunk_count", 1)
            entry.setdefault("chunk_seconds", None)
            expanded.append(entry)
            continue

        split_result = split_video(path, output_dir, chunk_seconds)
        chunks = split_result.get("chunks", [])
        group_id = uuid.uuid4().hex
        logger.info(
            "Auto-chunking %s: %d chunks of %ss each",
            entry["video_name"],
            len(chunks),
            split_result.get("chunk_seconds", chunk_seconds),
        )
        for idx, chunk_path in enumerate(chunks, start=1):
            chunk = Path(chunk_path)
            expanded.append(
                {
                    **entry,
                    "video_path": str(chunk.resolve()),
                    "video_name": chunk.name,
                    "logical_video_name": entry.get("source_video_name", entry["video_name"]),
                    "source_video_name": entry.get("source_video_name", entry["video_name"]),
                    "source_path": str(chunk.resolve()),
                    "original_source_path": entry.get("source_path", entry["video_path"]),
                    "chunk_group_id": group_id,
                    "chunk_index": idx,
                    "chunk_count": len(chunks),
                    "chunk_seconds": split_result.get("chunk_seconds", chunk_seconds),
                }
            )
    return expanded


def _cleanup_video_data(conn, video_id: int, keep_video_row: bool = False) -> dict:
    deleted: dict[str, int] = {}
    # Delete dependent rows by joining through their parent tables.
    deleted["identity_reviews"] = conn.execute(
        "DELETE FROM identity_reviews WHERE assignment_id IN "
        "(SELECT id FROM video_assignments WHERE video_id = ?)",
        (video_id,),
    ).rowcount
    deleted["behavior_labels"] = conn.execute(
        "DELETE FROM behavior_labels WHERE clip_id IN "
        "(SELECT id FROM clip_library WHERE video_id = ?)",
        (video_id,),
    ).rowcount
    deleted["droppings_reviews"] = conn.execute(
        "DELETE FROM droppings_reviews WHERE dropping_id IN "
        "(SELECT id FROM droppings WHERE video_id = ?)",
        (video_id,),
    ).rowcount
    for table in [
        "features",
        "pairwise",
        "behaviors",
        "clip_library",
        "droppings",
        "qc_flags",
        "review_tasks",
        "ai_observations",
        "video_assignments",
        "track_edits",
    ]:
        deleted[table] = conn.execute(
            f"DELETE FROM {table} WHERE video_id = ?",
            (video_id,),
        ).rowcount
    if not keep_video_row:
        deleted["videos"] = conn.execute(
            "DELETE FROM videos WHERE video_id = ?",
            (video_id,),
        ).rowcount
    deleted["frames"] = FrameExtractor().cleanup_frames(video_id)
    return deleted


def _mark_video_cancelled(conn, video_id: int, reason: str = "Cancelled by user") -> None:
    _cleanup_video_data(conn, video_id, keep_video_row=True)
    conn.execute(
        """UPDATE videos
           SET processing_status = 'cancelled',
               processing_error = ?,
               total_frames = NULL,
               fps = NULL,
               processed_at = NULL,
               model_version = NULL,
               review_status = 'raw'
           WHERE video_id = ?""",
        (reason, video_id),
    )


# --- Endpoints ---

@router.get("/sessions")
async def list_sessions():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT session_id FROM videos WHERE session_id IS NOT NULL ORDER BY session_id"
        ).fetchall()
    return [r["session_id"] for r in rows]


@router.get("/")
async def list_videos(
    sort: str = Query("date"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    with get_db() as conn:
        order_col = {
            "date": "processed_at",
            "name": "video_name",
            "status": "processing_status",
            "frames": "total_frames",
        }.get(sort, "processed_at")

        total_row = conn.execute("SELECT COUNT(*) AS cnt FROM videos").fetchone()
        total = total_row["cnt"] if total_row else 0

        offset = (page - 1) * per_page
        rows = conn.execute(
            f"""SELECT v.*,
                       COUNT(DISTINCT va.video_obj_id) AS track_count,
                       COUNT(DISTINCT CASE
                           WHEN va.review_status = 'approved'
                            AND va.pigeon_id NOT LIKE 'unknown_%'
                           THEN va.pigeon_id
                       END) AS confirmed_pigeon_count,
                       COUNT(DISTINCT va.pigeon_id) AS pigeon_count
                FROM videos v
                LEFT JOIN video_assignments va ON va.video_id = v.video_id
                GROUP BY v.video_id
                ORDER BY {order_col} DESC
                LIMIT ? OFFSET ?""",
            (per_page, offset),
        ).fetchall()
        videos = _attach_chunk_group_status(conn, [dict(r) for r in rows])

    return {
        "videos": videos,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/ffmpeg/status")
async def ffmpeg_status():
    return get_ffmpeg_status()


@router.post("/upload")
async def upload_videos(request: Request):
    form = await request.form()
    uploads = [
        value
        for _key, value in form.multi_items()
        if hasattr(value, "filename") and hasattr(value, "read")
    ]
    if not uploads:
        raise HTTPException(status_code=400, detail="No video files were uploaded.")

    process_now = _form_bool(form.get("process_now"), True)
    if process_now:
        _require_sam3_ready()

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    uploaded_entries: list[dict] = []
    invalid_names: list[str] = []

    for upload in uploads:
        original_name = Path(upload.filename or "video.mp4").name
        suffix = Path(original_name).suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            invalid_names.append(original_name)
            continue

        safe_name = f"{uuid.uuid4().hex[:8]}_{original_name}"
        destination = UPLOADS_DIR / safe_name
        with destination.open("wb") as out_file:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                out_file.write(chunk)
        uploaded_entries.append(
            {
                "video_path": str(destination.resolve()),
                "video_name": original_name,
                "source_path": str(destination.resolve()),
                "source_video_name": original_name,
            }
        )

    if invalid_names:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format(s): {', '.join(invalid_names)}",
        )
    if not uploaded_entries:
        raise HTTPException(status_code=400, detail="No supported video files were uploaded.")

    text_prompt = str(form.get("text_prompt") or "pigeon").strip() or "pigeon"
    expected_pigeon_count = max(0, _form_int(form.get("expected_pigeon_count"), 4))
    camera_assignments: dict[str, str] = {}
    raw_assignments = form.get("camera_assignments")
    if raw_assignments:
        try:
            parsed_assignments = json.loads(str(raw_assignments))
            if isinstance(parsed_assignments, dict):
                camera_assignments = {
                    str(key): str(value) for key, value in parsed_assignments.items()
                }
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="camera_assignments must be valid JSON.")
    default_camera_type = str(form.get("camera_type") or form.get("camera") or "Uploaded video")
    session_id = str(form.get("session_id") or "").strip()
    try:
        uploaded_entries = _auto_chunk_entries(uploaded_entries)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Video chunking failed: {exc}") from exc

    job_id: str | None = None
    queued = 0
    if process_now:
        with get_db() as conn:
            job_id = str(uuid.uuid4())
            for entry in uploaded_entries:
                camera_type = camera_assignments.get(
                    entry["video_name"],
                    camera_assignments.get(entry.get("source_video_name", ""), default_camera_type),
                )
                cursor = _insert_video(conn, entry, session_id, camera_type)
                entry["video_id"] = cursor.lastrowid
                queued += 1
            conn.commit()

        video_entries = [
            {
                "video_id": entry["video_id"],
                "video_path": entry["video_path"],
                "text_prompt": text_prompt,
                "expected_pigeon_count": expected_pigeon_count,
            }
            for entry in uploaded_entries
        ]
        task = asyncio.create_task(_run_processing_job(job_id, video_entries))
        _processing_jobs[job_id] = task

    return {
        "job_id": job_id,
        "status": "queued" if process_now else "uploaded",
        "videos_uploaded": len(uploaded_entries),
        "videos_queued": queued,
        "uploaded_files": uploaded_entries,
    }


@router.post("/import-folder")
async def import_video_folder(req: FolderImportRequest):
    if req.process_now:
        _require_sam3_ready()

    try:
        import_result = ingest_folder(
            input_dir=req.input_dir or None,
            output_dir=req.output_dir or None,
            archive_dir=req.archive_dir or None,
            chunk_seconds=req.chunk_seconds,
            archive_originals=req.archive_originals,
            limit=req.limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    chunk_entries: list[dict] = []
    for source in import_result["videos"]:
        session_id = _import_session_id(req.session_prefix, source["source_stem"])
        chunks = list(source["chunks"])
        group_id = uuid.uuid4().hex if len(chunks) > 1 else None
        if len(chunks) > 1:
            logger.info(
                "Auto-chunking %s: %d chunks of %ss each",
                source["source_name"],
                len(chunks),
                source["chunk_seconds"],
            )
        for idx, chunk_path in enumerate(chunks, start=1):
            chunk = Path(chunk_path)
            chunk_entries.append(
                {
                    "video_path": chunk_path,
                    "video_name": chunk.name,
                    "session_id": session_id,
                    "source_video_name": source["source_name"],
                    "logical_video_name": source["source_name"],
                    "source_path": chunk_path,
                    "original_source_path": source["source_path"],
                    "chunk_group_id": group_id,
                    "chunk_index": idx,
                    "chunk_count": len(chunks),
                    "chunk_seconds": source["chunk_seconds"],
                    "text_prompt": req.text_prompt.strip() or "pigeon",
                    "expected_pigeon_count": req.expected_pigeon_count,
                }
            )

    if not chunk_entries:
        if import_result["errors"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "No chunks were created from the input folder.",
                    "errors": import_result["errors"],
                },
            )
        return {
            **import_result,
            "job_id": None,
            "videos_queued": 0,
            "status": "no_videos_found",
        }

    job_id: str | None = None
    queued = 0
    if req.process_now:
        with get_db() as conn:
            job_id = str(uuid.uuid4())
            new_video_ids: list[int] = []
            for entry in chunk_entries:
                cursor = _insert_video(conn, entry, entry["session_id"], "FFmpeg chunk")
                new_video_ids.append(cursor.lastrowid)
                queued += 1
            conn.commit()

        video_entries = [
            {
                "video_id": vid_id,
                "video_path": entry["video_path"],
                "text_prompt": entry["text_prompt"],
                "expected_pigeon_count": entry["expected_pigeon_count"],
            }
            for vid_id, entry in zip(new_video_ids, chunk_entries)
        ]
        task = asyncio.create_task(_run_processing_job(job_id, video_entries))
        _processing_jobs[job_id] = task

    return {
        **import_result,
        "job_id": job_id,
        "videos_queued": queued,
        "status": "queued" if req.process_now else "chunked",
    }


async def _run_processing_job(
    job_id: str,
    video_entries: list[dict],
) -> None:
    """Background task that processes queued videos sequentially."""
    processor = VideoProcessor()
    completed = 0
    failed = 0
    cancelled = 0
    no_detections = 0
    errors = []
    for entry in video_entries:
        video_id = entry["video_id"]
        try:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT processing_status FROM videos WHERE video_id = ?",
                    (video_id,),
                ).fetchone()
                if row and row["processing_status"] == "cancelled":
                    cancelled += 1
                    continue

            cancel_event = asyncio.Event()
            _processing_cancel_events[video_id] = cancel_event
            _processing_video_jobs[video_id] = job_id
            result = await processor.process_video(
                video_id=video_id,
                video_path=entry["video_path"],
                text_prompt=entry.get("text_prompt", "pigeon"),
                expected_pigeon_count=entry.get("expected_pigeon_count", 4),
                cancel_check=cancel_event.is_set,
            )
            with get_db() as conn:
                row = conn.execute(
                    "SELECT processing_status FROM videos WHERE video_id = ?",
                    (video_id,),
                ).fetchone()
                if row and row["processing_status"] == "cancelled":
                    cancelled += 1
                elif row and row["processing_status"] == "completed_no_detections":
                    no_detections += 1
                elif result.get("status") == "completed_no_detections":
                    no_detections += 1
                else:
                    completed += 1
        except Exception as exc:
            failed += 1
            errors.append({"video_id": video_id, "error": str(exc)})
            logging.exception(
                "Processing failed for video_id=%s", video_id,
            )
        finally:
            _processing_cancel_events.pop(video_id, None)
            _processing_video_jobs.pop(video_id, None)
    if failed and not completed and not cancelled and not no_detections:
        status = "failed"
    elif cancelled and not completed and not failed and not no_detections:
        status = "cancelled"
    elif failed or cancelled or no_detections:
        status = "partial"
    else:
        status = "completed"
    _processing_job_results[job_id] = {
        "job_id": job_id,
        "status": status,
        "videos_completed": completed,
        "videos_failed": failed,
        "videos_cancelled": cancelled,
        "videos_no_detections": no_detections,
        "errors": errors,
    }
    _processing_jobs.pop(job_id, None)


@router.post("/process")
async def process_videos(req: ProcessRequest):
    if not req.video_paths:
        raise HTTPException(status_code=400, detail="video_paths must not be empty.")

    _require_sam3_ready()

    video_path_entries: list[tuple[str, str]] = []
    missing_paths: list[str] = []
    invalid_ext: list[str] = []
    for raw_path in req.video_paths:
        path = Path(raw_path).expanduser()
        if not path.is_file():
            missing_paths.append(raw_path)
            continue
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            invalid_ext.append(raw_path)
            continue
        video_path_entries.append((raw_path, str(path.resolve())))

    if missing_paths or invalid_ext:
        details = []
        if missing_paths:
            details.append(f"Missing video file(s): {', '.join(missing_paths)}")
        if invalid_ext:
            details.append(f"Unsupported video format(s): {', '.join(invalid_ext)}")
        raise HTTPException(status_code=400, detail=" ".join(details))

    raw_entries = []
    for raw_path, path in video_path_entries:
        name = Path(path).name
        raw_entries.append(
            {
                "raw_path": raw_path,
                "video_path": path,
                "video_name": name,
                "source_path": path,
                "source_video_name": name,
                "camera_type": req.camera_assignments.get(raw_path, req.camera_assignments.get(path, "")),
            }
        )
    try:
        processing_entries = _auto_chunk_entries(raw_entries)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Video chunking failed: {exc}") from exc

    with get_db() as conn:
        job_id = str(uuid.uuid4())
        queued = 0
        new_video_ids: list[int] = []

        for entry in processing_entries:
            cursor = _insert_video(conn, entry, req.session_id, entry.get("camera_type", ""))
            new_video_ids.append(cursor.lastrowid)
            queued += 1

        conn.commit()

    video_entries = [
        {
            "video_id": vid_id,
            "video_path": entry["video_path"],
            "text_prompt": req.text_prompt.strip() or "pigeon",
            "expected_pigeon_count": req.expected_pigeon_count,
        }
        for vid_id, entry in zip(new_video_ids, processing_entries)
    ]

    task = asyncio.create_task(_run_processing_job(job_id, video_entries))
    _processing_jobs[job_id] = task

    return {"job_id": job_id, "videos_queued": queued, "status": "queued"}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    task = _processing_jobs.get(job_id)
    if task is None:
        if job_id in _processing_job_results:
            return _processing_job_results[job_id]
        return {"job_id": job_id, "status": "not_found"}
    if task.done():
        exc = task.exception()
        if exc:
            return {"job_id": job_id, "status": "failed", "error": str(exc)}
        return {"job_id": job_id, "status": "completed"}
    return {"job_id": job_id, "status": "running"}


@router.post("/chunk-groups/{chunk_group_id}/retry-failed")
async def retry_failed_chunk_group(chunk_group_id: str):
    _require_sam3_ready()
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM videos
               WHERE chunk_group_id = ? AND processing_status = 'failed'
               ORDER BY chunk_index, video_id""",
            (chunk_group_id,),
        ).fetchall()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail="No failed chunks found for this chunk group.",
            )

        entries: list[dict] = []
        for row in rows:
            video = dict(row)
            source_path = video.get("source_path")
            if not source_path or not Path(source_path).is_file():
                raise HTTPException(
                    status_code=400,
                    detail=f"Source video file is missing for chunk {video['video_id']}: {source_path}",
                )
            _cleanup_video_data(conn, video["video_id"], keep_video_row=True)
            conn.execute(
                """UPDATE videos
                   SET processing_status = 'queued',
                       processing_error = NULL,
                       total_frames = NULL,
                       fps = NULL,
                       processed_at = NULL,
                       model_version = NULL,
                       review_status = 'raw'
                   WHERE video_id = ?""",
                (video["video_id"],),
            )
            entries.append(
                {
                    "video_id": video["video_id"],
                    "video_path": source_path,
                    "text_prompt": "pigeon",
                    "expected_pigeon_count": 4,
                }
            )
        conn.commit()

    job_id = str(uuid.uuid4())
    task = asyncio.create_task(_run_processing_job(job_id, entries))
    _processing_jobs[job_id] = task
    return {
        "job_id": job_id,
        "chunk_group_id": chunk_group_id,
        "chunks_queued": len(entries),
        "status": "queued",
    }


@router.post("/{video_id}/cancel")
async def cancel_video(video_id: int):
    with get_db() as conn:
        video = _get_video_or_404(conn, video_id)
        status = video.get("processing_status")
        if status not in {"queued", "processing"}:
            return {
                "video_id": video_id,
                "status": status,
                "cancelled": False,
                "message": "Video is not queued or processing.",
            }

        targets = [video]
        group_id = video.get("chunk_group_id")
        if group_id:
            rows = conn.execute(
                """SELECT * FROM videos
                   WHERE chunk_group_id = ?
                     AND chunk_index >= ?
                     AND processing_status IN ('queued', 'processing')
                   ORDER BY chunk_index, video_id""",
                (group_id, int(video.get("chunk_index") or 1)),
            ).fetchall()
            targets = [dict(row) for row in rows]

        cancelled_ids: list[int] = []
        for target in targets:
            target_id = int(target["video_id"])
            event = _processing_cancel_events.get(target_id)
            if event is not None:
                event.set()
                conn.execute(
                    """UPDATE videos
                       SET processing_status = 'cancelled',
                           processing_error = 'Cancelled by user'
                       WHERE video_id = ?""",
                    (target_id,),
                )
            else:
                _mark_video_cancelled(conn, target_id)
            cancelled_ids.append(target_id)
        conn.commit()

    return {
        "video_id": video_id,
        "status": "cancelled",
        "cancelled": True,
        "cancelled_video_ids": cancelled_ids,
    }


@router.post("/{video_id}/retry")
async def retry_video(video_id: int):
    _require_sam3_ready()
    with get_db() as conn:
        video = _get_video_or_404(conn, video_id)
        source_path = video.get("source_path")
        if not source_path:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This video was created before source paths were recorded. "
                    "Re-add the video to process it again."
                ),
            )
        path = Path(source_path)
        if not path.is_file():
            raise HTTPException(status_code=400, detail=f"Source video file is missing: {source_path}")

        _cleanup_video_data(conn, video_id, keep_video_row=True)
        conn.execute(
            """UPDATE videos
               SET processing_status = 'queued',
                   processing_error = NULL,
                   total_frames = NULL,
                   fps = NULL,
                   processed_at = NULL,
                   model_version = NULL,
                   review_status = 'raw'
               WHERE video_id = ?""",
            (video_id,),
        )
        conn.commit()

    job_id = str(uuid.uuid4())
    task = asyncio.create_task(
        _run_processing_job(
            job_id,
            [
                {
                    "video_id": video_id,
                    "video_path": source_path,
                    "text_prompt": "pigeon",
                    "expected_pigeon_count": 4,
                }
            ],
        )
    )
    _processing_jobs[job_id] = task
    return {"job_id": job_id, "video_id": video_id, "status": "queued"}


@router.delete("/{video_id}")
async def delete_video(video_id: int):
    with get_db() as conn:
        _get_video_or_404(conn, video_id)
        deleted = _cleanup_video_data(conn, video_id, keep_video_row=False)
        conn.commit()
    return {"video_id": video_id, "deleted": True, "rows_deleted": deleted}


@router.get("/{video_id}")
async def get_video(video_id: int):
    with get_db() as conn:
        video = _get_video_or_404(conn, video_id)

        row = conn.execute(
            "SELECT COUNT(DISTINCT video_obj_id) AS cnt FROM video_assignments WHERE video_id = ?",
            (video_id,),
        ).fetchone()
        video["track_count"] = row["cnt"] if row else 0
        video["pigeon_count"] = video["track_count"]
        confirmed = conn.execute(
            """SELECT COUNT(DISTINCT pigeon_id) AS cnt
               FROM video_assignments
               WHERE video_id = ?
                 AND review_status = 'approved'
                 AND pigeon_id NOT LIKE 'unknown_%'""",
            (video_id,),
        ).fetchone()
        video["confirmed_pigeon_count"] = confirmed["cnt"] if confirmed else 0
        _attach_chunk_group_status(conn, [video])

    return video


@router.get("/{video_id}/status")
async def video_status(video_id: int):
    with get_db() as conn:
        video = _get_video_or_404(conn, video_id)
        _attach_chunk_group_status(conn, [video])

    progress_map = {
        "queued": 0,
        "processing": 50,
        "completed": 100,
        "completed_no_detections": 100,
        "failed": 0,
        "cancelled": 0,
    }
    status = video.get("processing_status", "queued")

    return {
        "status": status,
        "progress": progress_map.get(status, 0),
        "error": video.get("processing_error"),
        "chunk_group_status": video.get("chunk_group_status"),
        "chunk_group_status_label": video.get("chunk_group_status_label"),
        "chunk_group_total": video.get("chunk_group_total"),
        "chunk_group_completed": video.get("chunk_group_completed"),
        "chunk_group_failed": video.get("chunk_group_failed"),
        "chunk_group_no_detections": video.get("chunk_group_no_detections"),
        "chunk_group_cancelled": video.get("chunk_group_cancelled"),
    }


@router.get("/{video_id}/frame/{frame_num}")
async def get_frame(video_id: int, frame_num: int, overlay: bool = Query(False)):
    with get_db() as conn:
        _get_video_or_404(conn, video_id)

    frame_path = DATA_DIR / "frames" / str(video_id) / f"{frame_num:06d}.jpg"
    if not frame_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Frame {frame_num} not found for video {video_id}. "
                   f"Expected at {frame_path.relative_to(DATA_DIR)}",
        )

    if overlay:
        try:
            import cv2

            frame = cv2.imread(str(frame_path))
            if frame is None:
                raise ValueError("OpenCV could not read frame")
            with get_db() as conn:
                rows = conn.execute(
                    """SELECT pigeon_id, centroid_x, centroid_y, confidence, current_zone
                       FROM features
                       WHERE video_id = ? AND frame_idx = ?
                         AND centroid_x IS NOT NULL AND centroid_y IS NOT NULL""",
                    (video_id, frame_num),
                ).fetchall()

            for row in rows:
                x = int(row["centroid_x"])
                y = int(row["centroid_y"])
                color_seed = abs(hash(row["pigeon_id"]))
                color = (
                    60 + color_seed % 160,
                    60 + (color_seed // 7) % 160,
                    60 + (color_seed // 13) % 160,
                )
                cv2.circle(frame, (x, y), 12, color, 2)
                label = row["pigeon_id"]
                if row["confidence"] is not None:
                    label += f" {row['confidence']:.2f}"
                cv2.putText(
                    frame,
                    label,
                    (x + 14, max(16, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                    cv2.LINE_AA,
                )

            ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            if ok:
                return StreamingResponse(io.BytesIO(buffer.tobytes()), media_type="image/jpeg")
        except Exception:
            logging.exception("Failed to render frame overlay for video_id=%s frame=%s", video_id, frame_num)

    return FileResponse(frame_path, media_type="image/jpeg")


@router.put("/{video_id}/review")
async def update_review(video_id: int, body: ReviewUpdate):
    with get_db() as conn:
        _get_video_or_404(conn, video_id)

        conn.execute(
            "UPDATE videos SET review_status = ? WHERE video_id = ?",
            (body.review_status, video_id),
        )
        conn.commit()

    return {"video_id": video_id, "review_status": body.review_status, "reviewer": body.reviewer}


@router.get("/{video_id}/features")
async def get_video_features(video_id: int, frame_idx: int = Query(...)):
    with get_db() as conn:
        _get_video_or_404(conn, video_id)

        rows = conn.execute(
            "SELECT * FROM features WHERE video_id = ? AND frame_idx = ?",
            (video_id, frame_idx),
        ).fetchall()

    return [dict(r) for r in rows]


@router.get("/{video_id}/ai-observations")
async def get_video_ai_observations(
    video_id: int,
    frame_idx: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    with get_db() as conn:
        _get_video_or_404(conn, video_id)

        if frame_idx is None:
            rows = conn.execute(
                """SELECT * FROM ai_observations
                   WHERE video_id = ?
                   ORDER BY frame_idx ASC, created_at DESC
                   LIMIT ?""",
                (video_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM ai_observations
                   WHERE video_id = ? AND frame_idx = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (video_id, frame_idx, limit),
            ).fetchall()

    return [dict(r) for r in rows]


@router.get("/{video_id}/track-edits")
async def get_video_track_edits(video_id: int):
    with get_db() as conn:
        _get_video_or_404(conn, video_id)

        rows = conn.execute(
            "SELECT id, edit_type, editor, details, edited_at FROM track_edits "
            "WHERE video_id = ? ORDER BY edited_at DESC",
            (video_id,),
        ).fetchall()

    return [
        {
            "edit_id": r["id"],
            "edit_type": r["edit_type"],
            "editor": r["editor"],
            "details": r["details"],
            "created_at": r["edited_at"],
        }
        for r in rows
    ]
