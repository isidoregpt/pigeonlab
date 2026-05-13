from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from database import get_db
from utils import get_default_reviewer


class QCFlagAction(str, Enum):
    acknowledge = "acknowledge"
    resolve = "resolve"


class ResolvedAction(str, Enum):
    accepted = "accepted"
    corrected = "corrected"
    ignored = "ignored"
    dismissed = "dismissed"
    empty = ""


router = APIRouter()


# --- Schemas ---

class IdentityReviewRequest(BaseModel):
    assignment_id: int
    action: str
    pigeon_id: str = ""
    old_pigeon_id: str = ""
    new_pigeon_id: str = ""
    reviewer: str = Field(default_factory=get_default_reviewer)


class QCFlagReviewRequest(BaseModel):
    flag_id: int
    action: QCFlagAction
    resolved_action: ResolvedAction = ResolvedAction.empty
    reviewer: str = Field(default_factory=get_default_reviewer)
    notes: str = ""


class QCFlagBatchResolveRequest(BaseModel):
    flag_ids: list[int]
    action: QCFlagAction = QCFlagAction.resolve
    resolved_action: ResolvedAction = ResolvedAction.accepted
    reviewer: str = Field(default_factory=get_default_reviewer)


class MaskEditRequest(BaseModel):
    video_id: int
    frame_idx: int
    pigeon_id: str = ""
    edit_type: str = "mask"
    mask_data: str = ""
    editor: str = Field(default_factory=get_default_reviewer)
    details: str = ""


class TrackMergeRequest(BaseModel):
    video_id: int
    source_obj_id: int
    target_obj_id: int
    from_frame: int = 0
    editor: str = Field(default_factory=get_default_reviewer)
    notes: str = ""


class TrackSplitRequest(BaseModel):
    video_id: int
    obj_id: int
    at_frame: int
    editor: str = Field(default_factory=get_default_reviewer)
    notes: str = ""


class BehaviorReviewRequest(BaseModel):
    behavior_id: int
    action: str
    reviewer: str = Field(default_factory=get_default_reviewer)


class DroppingReviewRequest(BaseModel):
    dropping_id: int
    action: str
    reviewer: str = Field(default_factory=get_default_reviewer)


# --- Helpers ---

ACTION_STATUS = {
    "confirm": "approved",
    "reject": "rejected",
    "reassign": "approved",
}


def _track_candidates(video_obj_id: int, pigeon_id: str | None = None) -> list[str]:
    candidates = [f"unknown_{video_obj_id}", str(video_obj_id)]
    if pigeon_id:
        candidates.insert(0, pigeon_id)
    seen = set()
    return [c for c in candidates if not (c in seen or seen.add(c))]


def _replace_identity_references(
    conn,
    video_id: int,
    video_obj_id: int,
    old_pigeon_id: str,
    new_pigeon_id: str,
) -> int:
    """Replace a track/pigeon label across derived analysis tables."""
    conn.execute("INSERT OR IGNORE INTO pigeons (pigeon_id, first_seen) VALUES (?, datetime('now'))", (new_pigeon_id,))
    candidates = _track_candidates(video_obj_id, old_pigeon_id)
    placeholders = ",".join("?" for _ in candidates)

    params = [new_pigeon_id, video_id, *candidates]
    cur = conn.execute(
        f"UPDATE features SET pigeon_id = ? WHERE video_id = ? AND pigeon_id IN ({placeholders})",
        params,
    )
    changed = cur.rowcount if cur.rowcount is not None else 0

    conn.execute(
        f"UPDATE behaviors SET pigeon_id = ? WHERE video_id = ? AND pigeon_id IN ({placeholders})",
        params,
    )
    conn.execute(
        f"UPDATE pairwise SET pigeon_a = ? WHERE video_id = ? AND pigeon_a IN ({placeholders})",
        params,
    )
    conn.execute(
        f"UPDATE pairwise SET pigeon_b = ? WHERE video_id = ? AND pigeon_b IN ({placeholders})",
        params,
    )
    conn.execute("DELETE FROM pairwise WHERE video_id = ? AND pigeon_a = pigeon_b", (video_id,))
    return changed


def _assignment_for_obj(conn, video_id: int, obj_id: int) -> dict | None:
    row = conn.execute(
        """SELECT * FROM video_assignments
           WHERE video_id = ? AND video_obj_id = ?
           ORDER BY id DESC LIMIT 1""",
        (video_id, obj_id),
    ).fetchone()
    return dict(row) if row else None


def _chunk_carryover_suggestions(conn, video_id: int) -> dict:
    video = conn.execute(
        """SELECT video_id, video_name, logical_video_name, chunk_group_id,
                  chunk_index, chunk_count
           FROM videos WHERE video_id = ?""",
        (video_id,),
    ).fetchone()
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    current_video = dict(video)
    group_id = current_video.get("chunk_group_id")
    chunk_index = int(current_video.get("chunk_index") or 1)
    chunk_count = int(current_video.get("chunk_count") or 1)
    if not group_id or chunk_count <= 1:
        return {
            "eligible": False,
            "reason": "This video is not part of an auto-chunked group.",
            "current_video": current_video,
            "previous_video": None,
            "suggestions": [],
        }
    if chunk_index <= 1:
        return {
            "eligible": False,
            "reason": "The first chunk has no previous chunk to copy from.",
            "current_video": current_video,
            "previous_video": None,
            "suggestions": [],
        }

    previous = conn.execute(
        """SELECT video_id, video_name, logical_video_name, chunk_group_id,
                  chunk_index, chunk_count
           FROM videos
           WHERE chunk_group_id = ? AND chunk_index < ?
           ORDER BY chunk_index DESC, video_id DESC
           LIMIT 1""",
        (group_id, chunk_index),
    ).fetchone()
    if not previous:
        return {
            "eligible": False,
            "reason": "No earlier chunk was found for this chunk group.",
            "current_video": current_video,
            "previous_video": None,
            "suggestions": [],
        }

    current_rows = [
        dict(row) for row in conn.execute(
            """SELECT * FROM video_assignments
               WHERE video_id = ? AND review_status = 'raw'
               ORDER BY video_obj_id, id""",
            (video_id,),
        ).fetchall()
    ]
    previous_rows = [
        dict(row) for row in conn.execute(
            """SELECT * FROM video_assignments
               WHERE video_id = ? AND review_status IN ('approved', 'reviewed')
               ORDER BY video_obj_id, id""",
            (previous["video_id"],),
        ).fetchall()
    ]
    if not current_rows:
        return {
            "eligible": False,
            "reason": "This chunk has no raw identity assignments left.",
            "current_video": current_video,
            "previous_video": dict(previous),
            "suggestions": [],
        }
    if not previous_rows:
        return {
            "eligible": False,
            "reason": "Confirm the previous chunk before carrying identities forward.",
            "current_video": current_video,
            "previous_video": dict(previous),
            "suggestions": [],
        }

    suggestions: list[dict] = []
    previous_by_obj = {row["video_obj_id"]: row for row in previous_rows}
    used_previous_ids: set[int] = set()
    remaining_current: list[dict] = []
    for current in current_rows:
        previous_match = previous_by_obj.get(current["video_obj_id"])
        if previous_match:
            used_previous_ids.add(previous_match["id"])
            suggestions.append(
                {
                    "assignment_id": current["id"],
                    "video_obj_id": current["video_obj_id"],
                    "current_pigeon_id": current["pigeon_id"],
                    "suggested_pigeon_id": previous_match["pigeon_id"],
                    "previous_assignment_id": previous_match["id"],
                    "previous_video_id": previous_match["video_id"],
                    "match_basis": "same_track_id",
                }
            )
        else:
            remaining_current.append(current)

    remaining_previous = [
        row for row in previous_rows if row["id"] not in used_previous_ids
    ]
    if remaining_current and len(remaining_current) == len(remaining_previous):
        for current, previous_match in zip(remaining_current, remaining_previous):
            suggestions.append(
                {
                    "assignment_id": current["id"],
                    "video_obj_id": current["video_obj_id"],
                    "current_pigeon_id": current["pigeon_id"],
                    "suggested_pigeon_id": previous_match["pigeon_id"],
                    "previous_assignment_id": previous_match["id"],
                    "previous_video_id": previous_match["video_id"],
                    "match_basis": "sorted_track_order",
                }
            )

    return {
        "eligible": bool(suggestions),
        "reason": "" if suggestions else "No safe one-to-one previous chunk mapping was available.",
        "current_video": current_video,
        "previous_video": dict(previous),
        "suggestions": suggestions,
    }


def _replace_track_label_after_frame(
    conn,
    video_id: int,
    from_frame: int,
    source_obj_id: int,
    source_label: str,
    target_label: str,
) -> int:
    conn.execute("INSERT OR IGNORE INTO pigeons (pigeon_id, first_seen) VALUES (?, datetime('now'))", (target_label,))
    candidates = _track_candidates(source_obj_id, source_label)
    placeholders = ",".join("?" for _ in candidates)
    params = [target_label, video_id, from_frame, *candidates]

    cur = conn.execute(
        f"""UPDATE features
            SET pigeon_id = ?
            WHERE video_id = ? AND frame_idx >= ? AND pigeon_id IN ({placeholders})""",
        params,
    )
    changed = cur.rowcount if cur.rowcount is not None else 0

    conn.execute(
        f"""UPDATE pairwise
            SET pigeon_a = ?
            WHERE video_id = ? AND frame_idx >= ? AND pigeon_a IN ({placeholders})""",
        params,
    )
    conn.execute(
        f"""UPDATE pairwise
            SET pigeon_b = ?
            WHERE video_id = ? AND frame_idx >= ? AND pigeon_b IN ({placeholders})""",
        params,
    )
    conn.execute(
        "DELETE FROM pairwise WHERE video_id = ? AND frame_idx >= ? AND pigeon_a = pigeon_b",
        (video_id, from_frame),
    )
    return changed


# --- Existing endpoints ---

@router.get("/")
async def get_review():
    return {"status": "ok", "route": "review"}


@router.get("/attention/count")
async def attention_count():
    with get_db() as conn:
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

        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM behaviors WHERE review_status = 'raw'"
        ).fetchone()
        behaviors_cnt = row["cnt"] if row else 0

    return {
        "total": qc + identity + droppings_cnt + behaviors_cnt,
        "identity": identity,
        "qc": qc,
        "droppings": droppings_cnt,
        "behaviors": behaviors_cnt,
    }


@router.get("/attention")
async def attention_items(limit: int = Query(5, ge=1, le=50)):
    with get_db() as conn:
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

        rows = conn.execute(
            """SELECT id, video_id, pigeon_id, behavior, confidence, zone
               FROM behaviors WHERE review_status = 'raw'
               ORDER BY confidence ASC LIMIT ?""",
            (limit,),
        ).fetchall()
        for row in rows:
            conf = round(row["confidence"] * 100) if row["confidence"] is not None else 0
            items.append({
                "id": row["id"],
                "type": "behavior",
                "description": f"{row['pigeon_id']} — {row['behavior'].replace('_', ' ')}"
                               + (f" in {row['zone']}" if row["zone"] else "")
                               + f" ({conf}% confidence)",
                "severity": "high" if conf < 70 else "medium",
                "video_id": row["video_id"],
                "link": "/review?type=behavior",
            })

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        items.sort(key=lambda x: severity_order.get(x["severity"], 4))

    return items[:limit]


# --- Identity review ---

@router.get("/identities/next-video")
async def next_video_for_identity_review():
    with get_db() as conn:
        row = conn.execute(
            "SELECT video_id FROM video_assignments WHERE review_status = 'raw' "
            "ORDER BY video_id LIMIT 1"
        ).fetchone()
    return {"video_id": row["video_id"] if row else None}


@router.get("/identities")
async def list_unconfirmed_identities(video_id: int = Query(...)):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, video_id, video_obj_id, pigeon_id, confidence, match_method, review_status
               FROM video_assignments
               WHERE video_id = ? AND review_status = 'raw'
               ORDER BY confidence ASC""",
            (video_id,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            candidates = _track_candidates(row["video_obj_id"], row["pigeon_id"])
            placeholders = ",".join("?" for _ in candidates)
            sample = conn.execute(
                f"""SELECT MIN(frame_idx) AS frame_idx
                    FROM features
                    WHERE video_id = ? AND pigeon_id IN ({placeholders})""",
                [video_id, *candidates],
            ).fetchone()
            item["sample_frame_idx"] = sample["frame_idx"] if sample else 0
            result.append(item)
    return result


@router.post("/identity")
async def review_identity(body: IdentityReviewRequest):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM video_assignments WHERE id = ?", (body.assignment_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Assignment {body.assignment_id} not found")

        assignment = dict(row)
        VALID_ACTIONS = ["confirm", "reject", "reassign"]
        if body.action not in VALID_ACTIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action '{body.action}'. Must be one of: {', '.join(VALID_ACTIONS)}.",
            )
        new_status = ACTION_STATUS[body.action]

        old_pigeon = body.old_pigeon_id or assignment["pigeon_id"]
        new_pigeon = body.new_pigeon_id or body.pigeon_id or assignment["pigeon_id"]

        if body.action == "reassign" and new_pigeon:
            conn.execute(
                """UPDATE video_assignments SET pigeon_id = ?, review_status = ?,
                   reviewed_at = datetime('now'), reviewed_by = ? WHERE id = ?""",
                (new_pigeon, new_status, body.reviewer, body.assignment_id),
            )
        elif body.action == "reject":
            conn.execute(
                """UPDATE video_assignments SET review_status = 'rejected',
                   reviewed_at = datetime('now'), reviewed_by = ? WHERE id = ?""",
                (body.reviewer, body.assignment_id),
            )
        else:
            conn.execute(
                """UPDATE video_assignments SET review_status = ?,
                   reviewed_at = datetime('now'), reviewed_by = ? WHERE id = ?""",
                (new_status, body.reviewer, body.assignment_id),
            )

        if body.action in ("confirm", "reassign") and new_pigeon:
            _replace_identity_references(
                conn,
                assignment["video_id"],
                assignment["video_obj_id"],
                old_pigeon,
                new_pigeon,
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

    return dict(updated)


# --- Batch identity confirmation ---


class BatchIdentityItem(BaseModel):
    assignment_id: int
    pigeon_id: str


class BatchIdentityRequest(BaseModel):
    assignments: list[BatchIdentityItem]
    reviewer: str = Field(default_factory=get_default_reviewer)


class ChunkCarryoverRequest(BaseModel):
    video_id: int
    reviewer: str = Field(default_factory=get_default_reviewer)


@router.get("/identities/chunk-carryover")
async def get_chunk_carryover_suggestions(video_id: int = Query(...)):
    """Suggest identity assignments from the previous auto-chunked sibling."""
    with get_db() as conn:
        return _chunk_carryover_suggestions(conn, video_id)


@router.post("/identities/same-as-previous-chunk")
async def apply_chunk_carryover_identities(body: ChunkCarryoverRequest):
    """Confirm current chunk assignments from the previous reviewed chunk."""
    applied = 0
    with get_db() as conn:
        payload = _chunk_carryover_suggestions(conn, body.video_id)
        suggestions = payload["suggestions"]
        if not suggestions:
            raise HTTPException(
                status_code=400,
                detail=payload.get("reason") or "No previous chunk suggestions are available.",
            )

        for suggestion in suggestions:
            row = conn.execute(
                "SELECT * FROM video_assignments WHERE id = ?",
                (suggestion["assignment_id"],),
            ).fetchone()
            if not row:
                continue
            assignment = dict(row)
            old_pigeon = assignment["pigeon_id"]
            new_pigeon = suggestion["suggested_pigeon_id"]
            conn.execute(
                """UPDATE video_assignments
                   SET pigeon_id = ?,
                       review_status = 'approved',
                       match_method = 'manual_chunk_carryover',
                       reviewed_at = datetime('now'),
                       reviewed_by = ?
                   WHERE id = ?""",
                (new_pigeon, body.reviewer, assignment["id"]),
            )
            _replace_identity_references(
                conn,
                assignment["video_id"],
                assignment["video_obj_id"],
                old_pigeon,
                new_pigeon,
            )
            conn.execute(
                """INSERT INTO identity_reviews
                   (assignment_id, action, old_pigeon_id, new_pigeon_id, reviewer, reviewed_at, notes)
                   VALUES (?, 'confirm', ?, ?, ?, datetime('now'), ?)""",
                (
                    assignment["id"],
                    old_pigeon,
                    new_pigeon,
                    body.reviewer,
                    (
                        "Same as previous chunk assignment "
                        f"{suggestion['previous_assignment_id']} "
                        f"({suggestion['match_basis']})."
                    ),
                ),
            )
            applied += 1
        conn.commit()

    return {
        "video_id": body.video_id,
        "applied": applied,
        "suggestions": suggestions,
    }


@router.post("/identities/batch")
async def batch_confirm_identities(body: BatchIdentityRequest):
    """Confirm multiple identity assignments in one request."""
    if not body.assignments:
        raise HTTPException(status_code=400, detail="assignments list must not be empty.")

    confirmed = 0
    with get_db() as conn:
        for item in body.assignments:
            row = conn.execute(
                "SELECT * FROM video_assignments WHERE id = ?", (item.assignment_id,)
            ).fetchone()
            if not row:
                continue

            old_pigeon = row["pigeon_id"]

            if item.pigeon_id != old_pigeon:
                conn.execute(
                    """UPDATE video_assignments SET pigeon_id = ?, review_status = 'approved',
                       reviewed_at = datetime('now'), reviewed_by = ? WHERE id = ?""",
                    (item.pigeon_id, body.reviewer, item.assignment_id),
                )
            else:
                conn.execute(
                    """UPDATE video_assignments SET review_status = 'approved',
                       reviewed_at = datetime('now'), reviewed_by = ? WHERE id = ?""",
                    (body.reviewer, item.assignment_id),
                )

            _replace_identity_references(
                conn,
                row["video_id"],
                row["video_obj_id"],
                old_pigeon,
                item.pigeon_id,
            )

            conn.execute(
                """INSERT INTO identity_reviews
                   (assignment_id, action, old_pigeon_id, new_pigeon_id, reviewer, reviewed_at)
                   VALUES (?, 'confirm', ?, ?, ?, datetime('now'))""",
                (item.assignment_id, old_pigeon, item.pigeon_id, body.reviewer),
            )
            confirmed += 1

        conn.commit()

    return {"confirmed": confirmed}


# --- QC flags ---

@router.get("/qc-flags")
async def list_qc_flags(
    status: str = Query("pending"),
    video_id: int | None = Query(None),
):
    with get_db() as conn:
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
    return [dict(r) for r in rows]


@router.post("/qc-flag")
async def review_qc_flag(body: QCFlagReviewRequest):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM qc_flags WHERE id = ?", (body.flag_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"QC flag {body.flag_id} not found")

        conn.execute(
            "UPDATE qc_flags SET review_status = 'resolved', resolved_action = ? WHERE id = ?",
            (body.resolved_action or body.action, body.flag_id),
        )
        conn.commit()

        updated = conn.execute("SELECT * FROM qc_flags WHERE id = ?", (body.flag_id,)).fetchone()
    return dict(updated)


@router.post("/qc-flags/batch-resolve")
async def batch_resolve_qc_flags(body: QCFlagBatchResolveRequest):
    if not body.flag_ids:
        raise HTTPException(status_code=400, detail="flag_ids must not be empty")

    with get_db() as conn:
        placeholders = ",".join("?" for _ in body.flag_ids)
        resolved_action = body.resolved_action or body.action

        conn.execute(
            f"UPDATE qc_flags SET review_status = 'resolved', resolved_action = ? "
            f"WHERE id IN ({placeholders})",
            [resolved_action] + body.flag_ids,
        )
        conn.commit()

        rows = conn.execute(
            f"SELECT * FROM qc_flags WHERE id IN ({placeholders})",
            body.flag_ids,
        ).fetchall()
    return [dict(r) for r in rows]


# --- Mask edit ---

@router.post("/mask-edit")
async def mask_edit(body: MaskEditRequest):
    with get_db() as conn:
        row = conn.execute("SELECT video_id FROM videos WHERE video_id = ?", (body.video_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Video {body.video_id} not found")

        cur = conn.execute(
            """INSERT INTO track_edits (video_id, frame_idx, edit_type, editor, edited_at, details)
               VALUES (?, ?, ?, ?, datetime('now'), ?)""",
            (body.video_id, body.frame_idx, body.edit_type, body.editor, body.details),
        )
        conn.commit()
        edit_id = cur.lastrowid

    return {
        "edit_id": edit_id,
        "saved": True,
        "applied_to_features": False,
        "message": "Mask edit was recorded. This project does not store per-frame mask blobs yet.",
    }


# --- Track merge ---

@router.post("/track-merge")
async def track_merge(body: TrackMergeRequest):
    with get_db() as conn:
        row = conn.execute("SELECT video_id FROM videos WHERE video_id = ?", (body.video_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Video {body.video_id} not found")

        source_assignment = _assignment_for_obj(conn, body.video_id, body.source_obj_id)
        target_assignment = _assignment_for_obj(conn, body.video_id, body.target_obj_id)
        source_label = source_assignment["pigeon_id"] if source_assignment else f"unknown_{body.source_obj_id}"
        target_label = target_assignment["pigeon_id"] if target_assignment else f"unknown_{body.target_obj_id}"

        details = f"merge source={body.source_obj_id} into target={body.target_obj_id} from_frame={body.from_frame}"
        if body.notes:
            details += f" notes={body.notes}"

        frames_affected = _replace_track_label_after_frame(
            conn,
            body.video_id,
            body.from_frame,
            body.source_obj_id,
            source_label,
            target_label,
        )

        if source_assignment:
            conn.execute(
                """UPDATE video_assignments
                   SET pigeon_id = ?, review_status = 'approved',
                       match_method = 'manual', reviewed_at = datetime('now'), reviewed_by = ?
                   WHERE id = ?""",
                (target_label, body.editor, source_assignment["id"]),
            )

        cur = conn.execute(
            """INSERT INTO track_edits
               (video_id, frame_idx, edit_type, old_obj_id, new_obj_id, editor, edited_at, details)
               VALUES (?, ?, 'merge', ?, ?, ?, datetime('now'), ?)""",
            (body.video_id, body.from_frame, body.source_obj_id, body.target_obj_id, body.editor, details),
        )
        conn.commit()
        edit_id = cur.lastrowid

    return {"edit_id": edit_id, "merged": True, "frames_affected": frames_affected}


# --- Track split ---

@router.post("/track-split")
async def track_split(body: TrackSplitRequest):
    with get_db() as conn:
        row = conn.execute("SELECT video_id FROM videos WHERE video_id = ?", (body.video_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Video {body.video_id} not found")

        row = conn.execute(
            """SELECT MAX(max_id) AS max_id FROM (
                   SELECT COALESCE(MAX(new_obj_id), 0) AS max_id FROM track_edits WHERE video_id = ?
                   UNION ALL
                   SELECT COALESCE(MAX(video_obj_id), 0) AS max_id FROM video_assignments WHERE video_id = ?
               )""",
            (body.video_id, body.video_id),
        ).fetchone()
        new_obj_id = (row["max_id"] or 0) + 1
        if new_obj_id <= body.obj_id:
            new_obj_id = body.obj_id + 1

        source_assignment = _assignment_for_obj(conn, body.video_id, body.obj_id)
        source_label = source_assignment["pigeon_id"] if source_assignment else f"unknown_{body.obj_id}"
        new_label = f"unknown_{new_obj_id}"

        frames_affected = _replace_track_label_after_frame(
            conn,
            body.video_id,
            body.at_frame,
            body.obj_id,
            source_label,
            new_label,
        )

        conn.execute(
            """INSERT INTO video_assignments
               (video_id, video_obj_id, pigeon_id, confidence, match_method, review_status, assigned_at)
               VALUES (?, ?, ?, ?, 'manual_split', 'raw', datetime('now'))""",
            (body.video_id, new_obj_id, new_label, 1.0),
        )

        details = f"split obj={body.obj_id} at frame={body.at_frame}"
        if body.notes:
            details += f" notes={body.notes}"

        cur = conn.execute(
            """INSERT INTO track_edits
               (video_id, frame_idx, edit_type, old_obj_id, new_obj_id, editor, edited_at, details)
               VALUES (?, ?, 'split', ?, ?, ?, datetime('now'), ?)""",
            (body.video_id, body.at_frame, body.obj_id, new_obj_id, body.editor, details),
        )
        conn.commit()
        edit_id = cur.lastrowid

    return {
        "edit_id": edit_id,
        "original_obj_id": body.obj_id,
        "new_obj_id": new_obj_id,
        "split_at_frame": body.at_frame,
        "frames_affected": frames_affected,
    }


# --- Behavior review ---

@router.post("/behavior")
async def review_behavior(body: BehaviorReviewRequest):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM behaviors WHERE id = ?", (body.behavior_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Behavior {body.behavior_id} not found")

        new_status = ACTION_STATUS.get(body.action)
        if not new_status:
            raise HTTPException(status_code=400, detail=f"Invalid action '{body.action}'. Use confirm or reject.")

        conn.execute(
            "UPDATE behaviors SET review_status = ? WHERE id = ?",
            (new_status, body.behavior_id),
        )
        conn.commit()

        updated = conn.execute("SELECT * FROM behaviors WHERE id = ?", (body.behavior_id,)).fetchone()
    return dict(updated)


# --- Behavior review listing ---

@router.get("/behaviors")
async def list_behaviors(
    status: str = Query("raw"),
    video_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    with get_db() as conn:
        query = "SELECT * FROM behaviors WHERE review_status = ?"
        params: list = [status]

        if video_id is not None:
            query += " AND video_id = ?"
            params.append(video_id)

        query += " ORDER BY confidence ASC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# --- Dropping review ---

@router.get("/droppings")
async def list_droppings(
    status: str = Query("raw"),
    limit: int = Query(50, ge=1, le=200),
):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM droppings WHERE review_status = ? ORDER BY confidence ASC LIMIT ?",
            (status, limit),
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/dropping")
async def review_dropping(body: DroppingReviewRequest):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM droppings WHERE id = ?", (body.dropping_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Dropping {body.dropping_id} not found")

        new_status = ACTION_STATUS.get(body.action)
        if not new_status:
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
    return dict(updated)
