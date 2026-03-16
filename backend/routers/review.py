from fastapi import APIRouter, Query

from database import get_connection

router = APIRouter()


@router.get("/")
async def get_review():
    return {"status": "ok", "route": "review"}


@router.get("/attention/count")
async def attention_count():
    conn = get_connection()

    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM qc_flags WHERE review_status = 'pending'"
    ).fetchone()
    qc = row["cnt"] if row else 0

    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM video_assignments WHERE review_status = 'raw'"
    ).fetchone()
    identity = row["cnt"] if row else 0

    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM droppings WHERE review_status = 'raw'"
    ).fetchone()
    droppings = row["cnt"] if row else 0

    conn.close()
    return {
        "total": qc + identity + droppings,
        "identity": identity,
        "qc": qc,
        "droppings": droppings,
    }


@router.get("/attention")
async def attention_items(limit: int = Query(5, ge=1, le=50)):
    conn = get_connection()
    items = []

    # QC flags needing attention
    rows = conn.execute(
        """SELECT id, video_id, rule_name, severity, reason
           FROM qc_flags WHERE review_status = 'pending'
           ORDER BY
             CASE severity
               WHEN 'critical' THEN 0
               WHEN 'high' THEN 1
               WHEN 'medium' THEN 2
               WHEN 'low' THEN 3
               ELSE 4
             END
           LIMIT ?""",
        (limit,),
    ).fetchall()
    for row in rows:
        items.append({
            "id": row["id"],
            "type": "qc",
            "description": f"QC: {row['rule_name']} — {row['reason'] or 'No details'}",
            "severity": row["severity"] or "medium",
            "video_id": row["video_id"],
            "link": f"/videos/{row['video_id']}",
        })

    # Unreviewed identity assignments
    rows = conn.execute(
        """SELECT va.id, va.video_id, va.pigeon_id, va.confidence, va.match_method
           FROM video_assignments va
           WHERE va.review_status = 'raw'
           ORDER BY va.confidence ASC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    for row in rows:
        conf = round(row["confidence"] * 100) if row["confidence"] is not None else 0
        items.append({
            "id": row["id"],
            "type": "identity",
            "description": f"Review {row['pigeon_id']} assignment ({row['match_method']}, {conf}% confidence)",
            "severity": "high" if conf < 70 else "medium",
            "video_id": row["video_id"],
            "link": f"/review?assignment={row['id']}",
        })

    # Unreviewed droppings
    rows = conn.execute(
        """SELECT id, video_id, frame_idx, zone, confidence
           FROM droppings WHERE review_status = 'raw'
           ORDER BY confidence ASC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    for row in rows:
        items.append({
            "id": row["id"],
            "type": "droppings",
            "description": f"Dropping in {row['zone'] or 'unknown zone'} at frame {row['frame_idx']}",
            "severity": "low",
            "video_id": row["video_id"],
            "link": f"/videos/{row['video_id']}",
        })

    # Sort by severity then truncate
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    items.sort(key=lambda x: severity_order.get(x["severity"], 4))
    conn.close()

    return items[:limit]
