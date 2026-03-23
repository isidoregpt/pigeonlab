import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database import get_db

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


# --- Schemas ---

class ProcessRequest(BaseModel):
    video_paths: list[str]
    camera_assignments: dict[str, str] = {}
    text_prompt: str = ""
    expected_pigeon_count: int = 0
    session_id: str = ""


class ReviewUpdate(BaseModel):
    review_status: str
    reviewer: str


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
            f"SELECT * FROM videos ORDER BY {order_col} DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()

    return {
        "videos": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


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


@router.post("/process")
async def process_videos(req: ProcessRequest):
    if not req.video_paths:
        raise HTTPException(status_code=400, detail="video_paths must not be empty.")

    with get_db() as conn:
        job_id = str(uuid.uuid4())
        queued = 0

        for path in req.video_paths:
            name = Path(path).name
            camera = req.camera_assignments.get(path, "")
            conn.execute(
                """INSERT INTO videos (video_name, session_id, camera_type, processing_status)
                   VALUES (?, ?, ?, 'queued')""",
                (name, req.session_id, camera),
            )
            queued += 1

        conn.commit()

    return {"job_id": job_id, "videos_queued": queued, "status": "queued"}


@router.get("/{video_id}/status")
async def video_status(video_id: int):
    with get_db() as conn:
        video = _get_video_or_404(conn, video_id)

    progress_map = {"queued": 0, "processing": 50, "completed": 100, "failed": 0}
    status = video.get("processing_status", "queued")

    return {"status": status, "progress": progress_map.get(status, 0)}


@router.get("/{video_id}/frame/{frame_num}")
async def get_frame(video_id: int, frame_num: int):
    with get_db() as conn:
        _get_video_or_404(conn, video_id)

    frame_path = DATA_DIR / "frames" / str(video_id) / f"{frame_num:06d}.jpg"
    if not frame_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Frame {frame_num} not found for video {video_id}. "
                   f"Expected at {frame_path.relative_to(DATA_DIR)}",
        )

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
