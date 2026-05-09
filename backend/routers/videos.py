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
from services.ffmpeg_ingest import get_ffmpeg_status, ingest_folder
from services.sam3 import get_sam3_status
from services.video_processor import VideoProcessor
from utils import get_default_reviewer

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
UPLOADS_DIR = DATA_DIR / "videos" / "uploads"
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}

_processing_jobs: dict[str, asyncio.Task] = {}
_processing_job_results: dict[str, dict] = {}


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
    chunk_seconds: int = Field(default=300, ge=30, le=3600)
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
            f"""SELECT v.*, COUNT(DISTINCT va.pigeon_id) AS pigeon_count
                FROM videos v
                LEFT JOIN video_assignments va ON va.video_id = v.video_id
                GROUP BY v.video_id
                ORDER BY {order_col} DESC
                LIMIT ? OFFSET ?""",
            (per_page, offset),
        ).fetchall()

    return {
        "videos": [dict(r) for r in rows],
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

    job_id: str | None = None
    queued = 0
    if process_now:
        with get_db() as conn:
            job_id = str(uuid.uuid4())
            for entry in uploaded_entries:
                camera_type = camera_assignments.get(entry["video_name"], default_camera_type)
                cursor = conn.execute(
                    """INSERT INTO videos
                       (video_name, session_id, camera_type, processing_status, processing_error)
                       VALUES (?, ?, ?, 'queued', NULL)""",
                    (entry["video_name"], session_id, camera_type),
                )
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
        for chunk_path in source["chunks"]:
            chunk_entries.append(
                {
                    "video_path": chunk_path,
                    "session_id": session_id,
                    "source_path": source["source_path"],
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
                name = Path(entry["video_path"]).name
                cursor = conn.execute(
                    """INSERT INTO videos
                       (video_name, session_id, camera_type, processing_status, processing_error)
                       VALUES (?, ?, ?, 'queued', NULL)""",
                    (name, entry["session_id"], "FFmpeg chunk"),
                )
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
    errors = []
    for entry in video_entries:
        try:
            await processor.process_video(
                video_id=entry["video_id"],
                video_path=entry["video_path"],
                text_prompt=entry.get("text_prompt", "pigeon"),
                expected_pigeon_count=entry.get("expected_pigeon_count", 4),
            )
            completed += 1
        except Exception as exc:
            failed += 1
            errors.append({"video_id": entry["video_id"], "error": str(exc)})
            logging.exception(
                "Processing failed for video_id=%s", entry["video_id"],
            )
    _processing_job_results[job_id] = {
        "job_id": job_id,
        "status": "failed" if failed and not completed else "completed",
        "videos_completed": completed,
        "videos_failed": failed,
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

    with get_db() as conn:
        job_id = str(uuid.uuid4())
        queued = 0
        new_video_ids: list[int] = []

        for raw_path, path in video_path_entries:
            name = Path(path).name
            camera = req.camera_assignments.get(raw_path, req.camera_assignments.get(path, ""))
            cursor = conn.execute(
                """INSERT INTO videos
                   (video_name, session_id, camera_type, processing_status, processing_error)
                   VALUES (?, ?, ?, 'queued', NULL)""",
                (name, req.session_id, camera),
            )
            new_video_ids.append(cursor.lastrowid)
            queued += 1

        conn.commit()

    video_entries = [
        {
            "video_id": vid_id,
            "video_path": path,
            "text_prompt": req.text_prompt.strip() or "pigeon",
            "expected_pigeon_count": req.expected_pigeon_count,
        }
        for vid_id, (_, path) in zip(new_video_ids, video_path_entries)
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


@router.get("/{video_id}")
async def get_video(video_id: int):
    with get_db() as conn:
        video = _get_video_or_404(conn, video_id)

        row = conn.execute(
            "SELECT COUNT(DISTINCT pigeon_id) AS cnt FROM video_assignments WHERE video_id = ?",
            (video_id,),
        ).fetchone()
        video["pigeon_count"] = row["cnt"] if row else 0

    return video


@router.get("/{video_id}/status")
async def video_status(video_id: int):
    with get_db() as conn:
        video = _get_video_or_404(conn, video_id)

    progress_map = {"queued": 0, "processing": 50, "completed": 100, "failed": 0}
    status = video.get("processing_status", "queued")

    return {
        "status": status,
        "progress": progress_map.get(status, 0),
        "error": video.get("processing_error"),
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
