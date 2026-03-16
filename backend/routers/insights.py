from datetime import date, timedelta

from fastapi import APIRouter, Query

from database import get_connection

router = APIRouter()


def _period_clause(period: str) -> tuple[str, list]:
    if period == "all":
        return "", []
    days = {"day": 1, "week": 7, "month": 30}.get(period, 7)
    since = (date.today() - timedelta(days=days)).isoformat()
    return "AND DATE(v.processed_at) >= ?", [since]


@router.get("/heatmap")
async def insights_heatmap(
    pigeons: str = Query("all"),
    period: str = Query("week"),
):
    conn = get_connection()
    period_sql, params = _period_clause(period)

    pigeon_sql = ""
    if pigeons != "all":
        ids = [p.strip() for p in pigeons.split(",") if p.strip()]
        if ids:
            placeholders = ",".join("?" * len(ids))
            pigeon_sql = f"AND f.pigeon_id IN ({placeholders})"
            params.extend(ids)

    rows = conn.execute(
        f"""SELECT f.centroid_x, f.centroid_y
            FROM features f
            JOIN videos v ON f.video_id = v.video_id
            WHERE f.centroid_x IS NOT NULL AND f.centroid_y IS NOT NULL
              {period_sql} {pigeon_sql}""",
        params,
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

        max_val = max(cell for row in grid for cell in row)
        if max_val > 0:
            grid = [[cell / max_val for cell in row] for row in grid]

    return {"grid": grid, "width": grid_w, "height": grid_h}


@router.get("/behaviors")
async def insights_behaviors(period: str = Query("week")):
    conn = get_connection()
    period_sql, params = _period_clause(period)

    rows = conn.execute(
        f"""SELECT b.pigeon_id, b.behavior,
                   SUM(b.duration_seconds) AS total_dur, COUNT(*) AS cnt
            FROM behaviors b
            JOIN videos v ON b.video_id = v.video_id
            WHERE 1=1 {period_sql}
            GROUP BY b.pigeon_id, b.behavior""",
        params,
    ).fetchall()
    conn.close()

    pigeons: dict[str, dict[str, dict]] = {}
    for row in rows:
        pid = row["pigeon_id"]
        pigeons.setdefault(pid, {})[row["behavior"]] = {
            "duration_seconds": round(row["total_dur"], 2) if row["total_dur"] else 0.0,
            "event_count": row["cnt"],
        }

    return {"pigeons": pigeons}


@router.get("/pairwise")
async def insights_pairwise(period: str = Query("week")):
    conn = get_connection()
    period_sql, params = _period_clause(period)

    rows = conn.execute(
        f"""SELECT p.pigeon_a, p.pigeon_b,
                   AVG(p.distance_mm) AS avg_dist,
                   COUNT(*) AS prox_events,
                   COUNT(DISTINCT p.frame_idx) AS frame_count
            FROM pairwise p
            JOIN videos v ON p.video_id = v.video_id
            WHERE 1=1 {period_sql}
            GROUP BY p.pigeon_a, p.pigeon_b
            ORDER BY avg_dist ASC""",
        params,
    ).fetchall()
    conn.close()

    # Estimate duration from frame count using average fps
    pairs = []
    for row in rows:
        pairs.append({
            "pigeon_a": row["pigeon_a"],
            "pigeon_b": row["pigeon_b"],
            "avg_distance_mm": round(row["avg_dist"], 2) if row["avg_dist"] is not None else 0.0,
            "proximity_events": row["prox_events"],
            "total_duration_seconds": round(row["frame_count"] / 30.0, 2),
        })

    return {"pairs": pairs}


@router.get("/droppings")
async def insights_droppings(period: str = Query("week")):
    conn = get_connection()
    period_sql, params = _period_clause(period)

    # Total count
    row = conn.execute(
        f"""SELECT COUNT(*) AS cnt FROM droppings d
            JOIN videos v ON d.video_id = v.video_id
            WHERE 1=1 {period_sql}""",
        params,
    ).fetchone()
    total = row["cnt"] if row else 0

    # By zone
    rows = conn.execute(
        f"""SELECT COALESCE(d.zone, 'unknown') AS zone, COUNT(*) AS cnt
            FROM droppings d
            JOIN videos v ON d.video_id = v.video_id
            WHERE 1=1 {period_sql}
            GROUP BY d.zone""",
        list(params),
    ).fetchall()
    by_zone = {row["zone"]: row["cnt"] for row in rows}

    # Heatmap grid
    rows = conn.execute(
        f"""SELECT d.centroid_x, d.centroid_y
            FROM droppings d
            JOIN videos v ON d.video_id = v.video_id
            WHERE d.centroid_x IS NOT NULL AND d.centroid_y IS NOT NULL
              {period_sql}""",
        list(params),
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

        max_val = max(cell for row in grid for cell in row)
        if max_val > 0:
            grid = [[cell / max_val for cell in row] for row in grid]

    return {"total": total, "by_zone": by_zone, "grid": grid}


@router.get("/compare")
async def compare_sessions(
    a: str = Query(..., description="Session ID A"),
    b: str = Query(..., description="Session ID B"),
):
    conn = get_connection()

    def _session_data(session_id: str) -> dict:
        # Zone occupancy
        rows = conn.execute(
            """SELECT f.pigeon_id, f.current_zone, COUNT(*) AS cnt
               FROM features f
               JOIN videos v ON f.video_id = v.video_id
               WHERE v.session_id = ? AND f.current_zone IS NOT NULL
               GROUP BY f.pigeon_id, f.current_zone""",
            (session_id,),
        ).fetchall()

        pigeon_totals: dict[str, int] = {}
        pigeon_zones: dict[str, dict[str, int]] = {}
        for row in rows:
            pid = row["pigeon_id"]
            pigeon_totals[pid] = pigeon_totals.get(pid, 0) + row["cnt"]
            pigeon_zones.setdefault(pid, {})[row["current_zone"]] = row["cnt"]

        zone_occ: dict[str, dict[str, float]] = {}
        for pid, zones in pigeon_zones.items():
            total = pigeon_totals[pid]
            zone_occ[pid] = {z: round(c / total * 100, 1) for z, c in zones.items()}

        # Behavior summary
        rows = conn.execute(
            """SELECT b.pigeon_id, b.behavior, SUM(b.duration_seconds) AS total_dur, COUNT(*) AS cnt
               FROM behaviors b
               JOIN videos v ON b.video_id = v.video_id
               WHERE v.session_id = ?
               GROUP BY b.pigeon_id, b.behavior""",
            (session_id,),
        ).fetchall()

        behaviors: dict[str, dict[str, dict]] = {}
        for row in rows:
            behaviors.setdefault(row["pigeon_id"], {})[row["behavior"]] = {
                "duration_seconds": round(row["total_dur"], 2) if row["total_dur"] else 0.0,
                "event_count": row["cnt"],
            }

        # Pigeon IDs in session
        rows = conn.execute(
            """SELECT DISTINCT pigeon_id FROM video_assignments va
               JOIN videos v ON va.video_id = v.video_id
               WHERE v.session_id = ?""",
            (session_id,),
        ).fetchall()
        pigeon_ids = {row["pigeon_id"] for row in rows}

        return {"zone_occupancy": zone_occ, "behaviors": behaviors, "pigeon_ids": pigeon_ids}

    data_a = _session_data(a)
    data_b = _session_data(b)

    # Zone occupancy diff
    all_pigeons = data_a["pigeon_ids"] | data_b["pigeon_ids"]
    all_zones: set[str] = set()
    for occ in (data_a["zone_occupancy"], data_b["zone_occupancy"]):
        for zones in occ.values():
            all_zones.update(zones.keys())

    zone_diff: dict[str, dict[str, float]] = {}
    for pid in all_pigeons:
        zones_a = data_a["zone_occupancy"].get(pid, {})
        zones_b = data_b["zone_occupancy"].get(pid, {})
        zone_diff[pid] = {z: round(zones_b.get(z, 0) - zones_a.get(z, 0), 1) for z in all_zones}

    # Behavior diff
    all_behaviors: set[str] = set()
    for beh in (data_a["behaviors"], data_b["behaviors"]):
        for bs in beh.values():
            all_behaviors.update(bs.keys())

    behavior_diff: dict[str, dict[str, dict]] = {}
    for pid in all_pigeons:
        beh_a = data_a["behaviors"].get(pid, {})
        beh_b = data_b["behaviors"].get(pid, {})
        behavior_diff[pid] = {}
        for bname in all_behaviors:
            da = beh_a.get(bname, {"duration_seconds": 0, "event_count": 0})
            db = beh_b.get(bname, {"duration_seconds": 0, "event_count": 0})
            behavior_diff[pid][bname] = {
                "duration_diff": round(db["duration_seconds"] - da["duration_seconds"], 2),
                "count_diff": db["event_count"] - da["event_count"],
            }

    # Identity changes
    only_a = data_a["pigeon_ids"] - data_b["pigeon_ids"]
    only_b = data_b["pigeon_ids"] - data_a["pigeon_ids"]
    identity_changes = {
        "only_in_a": sorted(only_a),
        "only_in_b": sorted(only_b),
        "in_both": sorted(data_a["pigeon_ids"] & data_b["pigeon_ids"]),
    }

    conn.close()
    return {
        "session_a": a,
        "session_b": b,
        "zone_occupancy_diff": zone_diff,
        "behavior_diff": behavior_diff,
        "identity_changes": identity_changes,
    }
