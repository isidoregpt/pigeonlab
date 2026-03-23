import re
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import get_connection

router = APIRouter()


# --- Schemas ---

class PigeonCreate(BaseModel):
    pigeon_id: str
    physical_markers: str = ""
    notes: str = ""


class PigeonUpdate(BaseModel):
    physical_markers: str | None = None
    preferred_zones: str | None = None
    notes: str | None = None


# --- Helpers ---

def _get_pigeon_or_404(conn, pigeon_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM pigeons WHERE pigeon_id = ?", (pigeon_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Pigeon '{pigeon_id}' not found")
    return dict(row)


def _session_count(conn, pigeon_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(DISTINCT video_id) AS cnt FROM video_assignments WHERE pigeon_id = ?",
        (pigeon_id,),
    ).fetchone()
    return row["cnt"] if row else 0


def _top_zone(conn, pigeon_id: str) -> str | None:
    row = conn.execute(
        """SELECT current_zone, COUNT(*) AS cnt FROM features
           WHERE pigeon_id = ? AND current_zone IS NOT NULL
           GROUP BY current_zone ORDER BY cnt DESC LIMIT 1""",
        (pigeon_id,),
    ).fetchone()
    return row["current_zone"] if row else None


def _period_since(period: str) -> str:
    days = {"day": 1, "week": 7, "month": 30, "year": 365}.get(period, 7)
    return (date.today() - timedelta(days=days)).isoformat()


# --- Endpoints ---

@router.get("/")
async def list_pigeons():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM pigeons ORDER BY pigeon_id").fetchall()

    pigeons = []
    for row in rows:
        p = dict(row)
        pid = p["pigeon_id"]
        p["session_count"] = _session_count(conn, pid)
        p["top_zone"] = _top_zone(conn, pid)
        pigeons.append(p)

    conn.close()
    return pigeons


@router.get("/{pigeon_id}")
async def get_pigeon(pigeon_id: str):
    conn = get_connection()
    p = _get_pigeon_or_404(conn, pigeon_id)

    p["session_count"] = _session_count(conn, pigeon_id)
    p["top_zone"] = _top_zone(conn, pigeon_id)

    row = conn.execute(
        "SELECT AVG(velocity_mm_s) AS avg_vel FROM features WHERE pigeon_id = ? AND velocity_mm_s IS NOT NULL",
        (pigeon_id,),
    ).fetchone()
    p["avg_velocity_mm_s"] = round(row["avg_vel"], 2) if row and row["avg_vel"] is not None else 0.0

    rows = conn.execute(
        """SELECT behavior, SUM(duration_seconds) AS total
           FROM behaviors
           WHERE pigeon_id = ? AND review_status = 'approved' AND duration_seconds IS NOT NULL
           GROUP BY behavior""",
        (pigeon_id,),
    ).fetchall()
    p["behavior_summary"] = {row["behavior"]: round(row["total"], 2) for row in rows}

    conn.close()
    return p


@router.get("/{pigeon_id}/heatmap")
async def pigeon_heatmap(pigeon_id: str, period: str = Query("week")):
    conn = get_connection()
    _get_pigeon_or_404(conn, pigeon_id)

    since = _period_since(period)
    rows = conn.execute(
        """SELECT f.centroid_x, f.centroid_y
           FROM features f
           JOIN videos v ON f.video_id = v.video_id
           WHERE f.pigeon_id = ? AND DATE(v.processed_at) >= ?
             AND f.centroid_x IS NOT NULL AND f.centroid_y IS NOT NULL""",
        (pigeon_id, since),
    ).fetchall()
    conn.close()

    grid_w, grid_h = 50, 50
    grid = [[0.0] * grid_w for _ in range(grid_h)]

    if rows:
        xs = [r["centroid_x"] for r in rows]
        ys = [r["centroid_y"] for r in rows]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        range_x = max_x - min_x if max_x != min_x else 1.0
        range_y = max_y - min_y if max_y != min_y else 1.0

        for r in rows:
            gx = min(int((r["centroid_x"] - min_x) / range_x * (grid_w - 1)), grid_w - 1)
            gy = min(int((r["centroid_y"] - min_y) / range_y * (grid_h - 1)), grid_h - 1)
            grid[gy][gx] += 1.0

        max_val = max(grid[gy][gx] for gy in range(grid_h) for gx in range(grid_w))
        if max_val > 0:
            grid = [[cell / max_val for cell in row] for row in grid]

    return {"grid": grid, "width": grid_w, "height": grid_h, "pigeon_id": pigeon_id}


@router.get("/{pigeon_id}/behaviors")
async def pigeon_behaviors(pigeon_id: str, period: str = Query("week")):
    conn = get_connection()
    _get_pigeon_or_404(conn, pigeon_id)

    since = _period_since(period)
    rows = conn.execute(
        """SELECT b.behavior, SUM(b.duration_seconds) AS total_dur, COUNT(*) AS cnt
           FROM behaviors b
           JOIN videos v ON b.video_id = v.video_id
           WHERE b.pigeon_id = ? AND DATE(v.processed_at) >= ?
           GROUP BY b.behavior""",
        (pigeon_id, since),
    ).fetchall()
    conn.close()

    behaviors = {}
    for row in rows:
        behaviors[row["behavior"]] = {
            "duration_seconds": round(row["total_dur"], 2) if row["total_dur"] else 0.0,
            "event_count": row["cnt"],
        }

    return {"behaviors": behaviors}


@router.get("/{pigeon_id}/identity-status")
async def identity_status(pigeon_id: str):
    conn = get_connection()
    _get_pigeon_or_404(conn, pigeon_id)

    row = conn.execute(
        "SELECT COUNT(DISTINCT video_id) AS cnt FROM video_assignments WHERE pigeon_id = ?",
        (pigeon_id,),
    ).fetchone()
    total = row["cnt"] if row else 0

    row = conn.execute(
        """SELECT COUNT(DISTINCT video_id) AS cnt FROM video_assignments
           WHERE pigeon_id = ? AND review_status IN ('approved', 'reviewed')""",
        (pigeon_id,),
    ).fetchone()
    confirmed = row["cnt"] if row else 0

    conn.close()
    return {
        "confirmed_sessions": confirmed,
        "unconfirmed_sessions": total - confirmed,
        "total_sessions": total,
    }


PIGEON_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


@router.post("/")
async def create_pigeon(body: PigeonCreate):
    if not PIGEON_ID_RE.match(body.pigeon_id):
        raise HTTPException(
            status_code=400,
            detail="pigeon_id may only contain letters, numbers, hyphens, and underscores.",
        )

    conn = get_connection()

    existing = conn.execute(
        "SELECT pigeon_id FROM pigeons WHERE pigeon_id = ?", (body.pigeon_id,)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail=f"Pigeon '{body.pigeon_id}' already exists")

    conn.execute(
        """INSERT INTO pigeons (pigeon_id, physical_markers, notes, first_seen)
           VALUES (?, ?, ?, datetime('now'))""",
        (body.pigeon_id, body.physical_markers, body.notes),
    )
    conn.commit()
    conn.close()

    return {"pigeon_id": body.pigeon_id, "status": "created"}


@router.put("/{pigeon_id}")
async def update_pigeon(pigeon_id: str, body: PigeonUpdate):
    conn = get_connection()
    _get_pigeon_or_404(conn, pigeon_id)

    updates = []
    params = []
    for field in ("physical_markers", "preferred_zones", "notes"):
        val = getattr(body, field)
        if val is not None:
            updates.append(f"{field} = ?")
            params.append(val)

    if not updates:
        conn.close()
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(pigeon_id)
    conn.execute(
        f"UPDATE pigeons SET {', '.join(updates)} WHERE pigeon_id = ?",
        params,
    )
    conn.commit()
    conn.close()

    return {"pigeon_id": pigeon_id, "status": "updated"}
