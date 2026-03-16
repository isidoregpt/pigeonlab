from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import get_connection

router = APIRouter()


# --- Schemas ---

class IdentityReviewRequest(BaseModel):
    assignment_id: int
    action: str
    pigeon_id: str = ""
    old_pigeon_id: str = ""
    new_pigeon_id: str = ""
    reviewer: str = ""


class QCFlagReviewRequest(BaseModel):
    flag_id: int
    action: str
    resolved_action: str = ""
    reviewer: str = ""
    notes: str = ""


class MaskEditRequest(BaseModel):
    video_id: int
    frame_idx: int
    pigeon_id: str = ""
    edit_type: str = "mask"
    mask_data: str = ""
    editor: str = ""
    details: str = ""


class TrackMergeRequest(BaseModel):
    video_id: int
    source_obj_id: int
    target_obj_id: int
    from_frame: int = 0
    editor: str = ""
    notes: str = ""


class TrackSplitRequest(BaseModel):
    video_id: int
    obj_id: int
    at_frame: int
    editor: str = ""
    notes: str = ""


class BehaviorReviewRequest(BaseModel):
    behavior_id: int
    action: str
    reviewer: str = ""


class DroppingReviewRequest(BaseModel):
    dropping_id: int
    action: str
    reviewer: str = ""


# --- Helpers ---

ACTION_STATUS = {
    "confirm": "approved",
    "reject": "rejected",
    "reassign": "approved",
}


# --- Existing endpoints ---

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
    droppings_cnt = row["cnt"] if row else 0

    conn.close()
    return {
        "total": qc + identity + droppings_cnt,
        "identity": identity,
        "qc": qc,
        "droppings": droppings_cnt,
    }


@router.get("/attention")
async def attention_items(limit: int = Query(5, ge=1, le=50)):
    conn = get_connection()
    items = []

    rows = conn.execute(
        """SELECT id, video_id, rule_name, severity, reason
           FROM qc_flags WHERE review_status = 'pending'
           ORDER BY
             CASE severity
               WHEN 'critical' THEN 0 WHEN 'high' THEN 1
               WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4
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

    rows = conn.execute(
        """SELECT id, video_id, pigeon_id, confidence, match_method
           FROM video_assignments WHERE review_status = 'raw'
           ORDER BY confidence ASC LIMIT ?""",
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

    rows = conn.execute(
        """SELECT id, video_id, frame_idx, zone, confidence
           FROM droppings WHERE review_status = 'raw'
           ORDER BY confidence ASC LIMIT ?""",
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

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    items.sort(key=lambda x: severity_order.get(x["severity"], 4))
    conn.close()
    return items[:limit]


# --- Identity review ---

@router.get("/identities/next-video")
async def next_video_for_identity_review():
    conn = get_connection()
    row = conn.execute(
        "SELECT video_id FROM video_assignments WHERE review_status = 'raw' "
        "ORDER BY video_id LIMIT 1"
    ).fetchone()
    conn.close()
    return {"video_id": row["video_id"] if row else None}


@router.get("/identities")
async def list_unconfirmed_identities(video_id: int = Query(...)):
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, video_obj_id, pigeon_id, confidence, match_method, review_status
           FROM video_assignments
           WHERE video_id = ? AND review_status = 'raw'
           ORDER BY confidence ASC""",
        (video_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/identity")
async def review_identity(body: IdentityReviewRequest):
    conn = get_connection()

    row = conn.execute(
        "SELECT * FROM video_assignments WHERE id = ?", (body.assignment_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Assignment {body.assignment_id} not found")

    assignment = dict(row)
    new_status = ACTION_STATUS.get(body.action)
    if not new_status:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Invalid action '{body.action}'. Use confirm, reject, or reassign.")

    old_pigeon = body.old_pigeon_id or assignment["pigeon_id"]
    new_pigeon = body.new_pigeon_id or assignment["pigeon_id"]

    if body.action == "reassign" and body.new_pigeon_id:
        conn.execute(
            "UPDATE video_assignments SET pigeon_id = ?, review_status = ?, reviewed_at = datetime('now'), reviewed_by = ? WHERE id = ?",
            (body.new_pigeon_id, new_status, body.reviewer, body.assignment_id),
        )
    elif body.action == "reject":
        conn.execute(
            "UPDATE video_assignments SET review_status = 'rejected', reviewed_at = datetime('now'), reviewed_by = ? WHERE id = ?",
            (body.reviewer, body.assignment_id),
        )
    else:
        conn.execute(
            "UPDATE video_assignments SET review_status = ?, reviewed_at = datetime('now'), reviewed_by = ? WHERE id = ?",
            (new_status, body.reviewer, body.assignment_id),
        )

    conn.execute(
        """INSERT INTO identity_reviews (assignment_id, action, old_pigeon_id, new_pigeon_id, reviewer, reviewed_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))""",
        (body.assignment_id, body.action, old_pigeon, new_pigeon, body.reviewer),
    )
    conn.commit()

    updated = conn.execute(
        "SELECT * FROM video_assignments WHERE id = ?", (body.assignment_id,)
    ).fetchone()
    conn.close()

    return dict(updated)


# --- QC flags ---

@router.get("/qc-flags")
async def list_qc_flags(
    status: str = Query("pending"),
    video_id: int | None = Query(None),
):
    conn = get_connection()

    query = "SELECT * FROM qc_flags WHERE review_status = ?"
    params: list = [status]

    if video_id is not None:
        query += " AND video_id = ?"
        params.append(video_id)

    query += """ ORDER BY
        CASE severity
          WHEN 'critical' THEN 0 WHEN 'high' THEN 1
          WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4
        END"""

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/qc-flag")
async def review_qc_flag(body: QCFlagReviewRequest):
    conn = get_connection()

    row = conn.execute("SELECT * FROM qc_flags WHERE id = ?", (body.flag_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"QC flag {body.flag_id} not found")

    conn.execute(
        "UPDATE qc_flags SET review_status = 'resolved', resolved_action = ? WHERE id = ?",
        (body.resolved_action or body.action, body.flag_id),
    )
    conn.commit()

    updated = conn.execute("SELECT * FROM qc_flags WHERE id = ?", (body.flag_id,)).fetchone()
    conn.close()
    return dict(updated)


# --- Mask edit ---

@router.post("/mask-edit")
async def mask_edit(body: MaskEditRequest):
    conn = get_connection()

    row = conn.execute("SELECT video_id FROM videos WHERE video_id = ?", (body.video_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Video {body.video_id} not found")

    cur = conn.execute(
        """INSERT INTO track_edits (video_id, frame_idx, edit_type, editor, edited_at, details)
           VALUES (?, ?, ?, ?, datetime('now'), ?)""",
        (body.video_id, body.frame_idx, body.edit_type, body.editor, body.details),
    )
    conn.commit()
    edit_id = cur.lastrowid
    conn.close()

    return {"edit_id": edit_id, "saved": True}


# --- Track merge ---

@router.post("/track-merge")
async def track_merge(body: TrackMergeRequest):
    conn = get_connection()

    row = conn.execute("SELECT video_id FROM videos WHERE video_id = ?", (body.video_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Video {body.video_id} not found")

    details = f"merge source={body.source_obj_id} into target={body.target_obj_id} from_frame={body.from_frame}"
    if body.notes:
        details += f" notes={body.notes}"

    cur = conn.execute(
        """INSERT INTO track_edits (video_id, frame_idx, edit_type, old_obj_id, new_obj_id, editor, edited_at, details)
           VALUES (?, ?, 'merge', ?, ?, ?, datetime('now'), ?)""",
        (body.video_id, body.from_frame, body.source_obj_id, body.target_obj_id, body.editor, details),
    )
    conn.commit()
    edit_id = cur.lastrowid

    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM features WHERE video_id = ? AND frame_idx >= ?",
        (body.video_id, body.from_frame),
    ).fetchone()
    frames_affected = row["cnt"] if row else 0

    conn.close()
    return {"edit_id": edit_id, "merged": True, "frames_affected": frames_affected}


# --- Track split ---

@router.post("/track-split")
async def track_split(body: TrackSplitRequest):
    conn = get_connection()

    row = conn.execute("SELECT video_id FROM videos WHERE video_id = ?", (body.video_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Video {body.video_id} not found")

    row = conn.execute(
        "SELECT COALESCE(MAX(new_obj_id), 0) AS max_id FROM track_edits WHERE video_id = ?",
        (body.video_id,),
    ).fetchone()
    new_obj_id = (row["max_id"] or 0) + 1
    # Ensure new_obj_id is higher than the source
    if new_obj_id <= body.obj_id:
        new_obj_id = body.obj_id + 1000

    details = f"split obj={body.obj_id} at frame={body.at_frame}"
    if body.notes:
        details += f" notes={body.notes}"

    cur = conn.execute(
        """INSERT INTO track_edits (video_id, frame_idx, edit_type, old_obj_id, new_obj_id, editor, edited_at, details)
           VALUES (?, ?, 'split', ?, ?, ?, datetime('now'), ?)""",
        (body.video_id, body.at_frame, body.obj_id, new_obj_id, body.editor, details),
    )
    conn.commit()
    edit_id = cur.lastrowid
    conn.close()

    return {
        "edit_id": edit_id,
        "original_obj_id": body.obj_id,
        "new_obj_id": new_obj_id,
        "split_at_frame": body.at_frame,
    }


# --- Behavior review ---

@router.post("/behavior")
async def review_behavior(body: BehaviorReviewRequest):
    conn = get_connection()

    row = conn.execute("SELECT * FROM behaviors WHERE id = ?", (body.behavior_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Behavior {body.behavior_id} not found")

    new_status = ACTION_STATUS.get(body.action)
    if not new_status:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Invalid action '{body.action}'. Use confirm or reject.")

    conn.execute(
        "UPDATE behaviors SET review_status = ? WHERE id = ?",
        (new_status, body.behavior_id),
    )
    conn.commit()

    updated = conn.execute("SELECT * FROM behaviors WHERE id = ?", (body.behavior_id,)).fetchone()
    conn.close()
    return dict(updated)


# --- Dropping review ---

@router.get("/droppings")
async def list_droppings(
    status: str = Query("raw"),
    limit: int = Query(50, ge=1, le=200),
):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM droppings WHERE review_status = ? ORDER BY confidence ASC LIMIT ?",
        (status, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/dropping")
async def review_dropping(body: DroppingReviewRequest):
    conn = get_connection()

    row = conn.execute("SELECT * FROM droppings WHERE id = ?", (body.dropping_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Dropping {body.dropping_id} not found")

    new_status = ACTION_STATUS.get(body.action)
    if not new_status:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Invalid action '{body.action}'. Use confirm or reject.")

    conn.execute(
        "UPDATE droppings SET review_status = ? WHERE id = ?",
        (new_status, body.dropping_id),
    )
    conn.execute(
        """INSERT INTO droppings_reviews (dropping_id, action, reviewer, reviewed_at)
           VALUES (?, ?, ?, datetime('now'))""",
        (body.dropping_id, body.action, body.reviewer),
    )
    conn.commit()

    updated = conn.execute("SELECT * FROM droppings WHERE id = ?", (body.dropping_id,)).fetchone()
    conn.close()
    return dict(updated)
