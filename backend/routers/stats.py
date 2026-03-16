from datetime import date, timedelta

from fastapi import APIRouter, Query

from database import get_connection

router = APIRouter()


@router.get("/today")
async def stats_today():
    conn = get_connection()
    today = date.today().isoformat()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM videos WHERE DATE(processed_at) = ?",
        (today,),
    ).fetchone()
    videos_processed = row["cnt"] if row else 0

    row = conn.execute(
        """SELECT COUNT(DISTINCT pigeon_id) AS cnt
           FROM features f
           JOIN videos v ON f.video_id = v.video_id
           WHERE DATE(v.processed_at) = ?""",
        (today,),
    ).fetchone()
    pigeons_tracked = row["cnt"] if row else 0
    conn.close()

    return {"videos_processed": videos_processed, "pigeons_tracked": pigeons_tracked}


@router.get("/summary")
async def stats_summary(period: str = Query("week")):
    conn = get_connection()

    days = {"day": 1, "week": 7, "month": 30, "year": 365}
    lookback = days.get(period, 7)
    since = (date.today() - timedelta(days=lookback)).isoformat()

    rows = conn.execute(
        """SELECT f.pigeon_id, f.current_zone, COUNT(*) AS frame_count
           FROM features f
           JOIN videos v ON f.video_id = v.video_id
           WHERE DATE(v.processed_at) >= ? AND f.current_zone IS NOT NULL
           GROUP BY f.pigeon_id, f.current_zone""",
        (since,),
    ).fetchall()
    conn.close()

    pigeon_totals: dict[str, int] = {}
    pigeon_zones: dict[str, dict[str, int]] = {}
    for row in rows:
        pid = row["pigeon_id"]
        zone = row["current_zone"]
        count = row["frame_count"]
        pigeon_totals[pid] = pigeon_totals.get(pid, 0) + count
        pigeon_zones.setdefault(pid, {})[zone] = count

    pigeons: dict[str, dict[str, float]] = {}
    for pid, zones in pigeon_zones.items():
        total = pigeon_totals[pid]
        pigeons[pid] = {
            zone: round(count / total * 100, 1) for zone, count in zones.items()
        }

    return {"pigeons": pigeons}


@router.get("/activity")
async def recent_activity(limit: int = Query(10, ge=1, le=100)):
    conn = get_connection()
    items = []

    # Recent video processing events
    rows = conn.execute(
        """SELECT video_name, processing_status, processed_at
           FROM videos WHERE processed_at IS NOT NULL
           ORDER BY processed_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    for row in rows:
        items.append({
            "timestamp": row["processed_at"],
            "description": f"Video '{row['video_name']}' {row['processing_status']}",
            "type": "video",
            "status": row["processing_status"],
        })

    # Recent identity reviews
    rows = conn.execute(
        """SELECT ir.action, ir.old_pigeon_id, ir.new_pigeon_id,
                  ir.reviewer, ir.reviewed_at
           FROM identity_reviews ir
           WHERE ir.reviewed_at IS NOT NULL
           ORDER BY ir.reviewed_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    for row in rows:
        desc = f"Identity {row['action']}: {row['old_pigeon_id']}"
        if row["new_pigeon_id"]:
            desc += f" → {row['new_pigeon_id']}"
        items.append({
            "timestamp": row["reviewed_at"],
            "description": desc,
            "type": "identity_review",
            "status": row["action"],
        })

    # Recent model training events
    rows = conn.execute(
        """SELECT model_name, model_type, version, created_at
           FROM model_registry WHERE created_at IS NOT NULL
           ORDER BY created_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    for row in rows:
        items.append({
            "timestamp": row["created_at"],
            "description": f"Model '{row['model_name']}' v{row['version']} trained ({row['model_type']})",
            "type": "training",
            "status": "completed",
        })

    # Sort all items by timestamp descending
    items.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    conn.close()

    return items[:limit]
