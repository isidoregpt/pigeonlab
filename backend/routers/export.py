import csv
import html
import io
import os
import uuid
from datetime import date, timedelta
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database import get_db

router = APIRouter()

EXPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "exports"


class ExportRequest(BaseModel):
    format: str = "csv"
    include: list[str] = ["features"]
    filters: dict = {}
    include_manifest: bool = False


def _period_clause(period: str | None) -> tuple[str, list]:
    if not period or period == "all":
        return "", []
    days = {"day": 1, "week": 7, "month": 30}.get(period, 7)
    since = (date.today() - timedelta(days=days)).isoformat()
    return "AND DATE(v.processed_at) >= ?", [since]


def _bool_filter(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _rows(conn, sql: str, params: list | tuple = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _row(conn, sql: str, params: list | tuple = ()) -> dict:
    found = conn.execute(sql, params).fetchone()
    return dict(found) if found else {}


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _safe(value: Any) -> str:
    return html.escape(_fmt(value), quote=True)


def _table_html(columns: list[tuple[str, str]], rows: list[dict]) -> str:
    if not rows:
        return '<p class="empty">No rows available for this section.</p>'
    header = "".join(f"<th>{_safe(label)}</th>" for _key, label in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{_safe(row.get(key))}</td>" for key, _label in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def _table_md(columns: list[tuple[str, str]], rows: list[dict]) -> str:
    if not rows:
        return "_No rows available for this section._\n"
    labels = [label for _key, label in columns]
    lines = [
        "| " + " | ".join(labels) + " |",
        "| " + " | ".join("---" for _ in labels) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(row.get(key)).replace("|", "\\|") for key, _label in columns) + " |")
    return "\n".join(lines) + "\n"


def _report_scope(filters: dict) -> tuple[str, list, bool]:
    period_sql, params = _period_clause(filters.get("period"))
    approved_only = _bool_filter(filters.get("approved_only"), True)
    approved_sql = "AND v.review_status = 'approved'" if approved_only else ""
    return f"{period_sql} {approved_sql}", params, approved_only


def _report_data(conn, filters: dict) -> dict:
    period_sql, period_params = _period_clause(filters.get("period"))
    scoped_sql, scoped_params, approved_only = _report_scope(filters)
    scope_where = f"WHERE 1=1 {scoped_sql}"
    period_where = f"WHERE 1=1 {period_sql}"

    video_summary = _row(
        conn,
        f"""WITH logical_videos AS (
                SELECT COALESCE(v.chunk_group_id, 'video-' || v.video_id) AS logical_key,
                       COUNT(*) AS chunks,
                       SUM(CASE WHEN processing_status = 'completed' THEN 1 ELSE 0 END) AS completed_chunks,
                       SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) AS failed_chunks,
                       SUM(CASE WHEN processing_status = 'completed_no_detections' THEN 1 ELSE 0 END) AS no_detection_chunks,
                       SUM(CASE WHEN review_status = 'approved' THEN 1 ELSE 0 END) AS approved_chunks,
                       SUM(COALESCE(total_frames, 0)) AS total_frames,
                       AVG(fps) AS mean_fps,
                       MIN(processed_at) AS first_processed_at,
                       MAX(processed_at) AS last_processed_at
                FROM videos v
                {period_where}
                GROUP BY logical_key
            )
            SELECT COUNT(*) AS total_videos,
                   SUM(CASE WHEN completed_chunks = chunks THEN 1 ELSE 0 END) AS completed_videos,
                   SUM(CASE WHEN failed_chunks = chunks THEN 1 ELSE 0 END) AS failed_videos,
                   SUM(CASE WHEN no_detection_chunks > 0 THEN 1 ELSE 0 END) AS videos_with_no_detection_chunks,
                   SUM(CASE WHEN approved_chunks = chunks THEN 1 ELSE 0 END) AS approved_videos,
                   SUM(total_frames) AS total_frames,
                   ROUND(AVG(mean_fps), 2) AS mean_fps,
                   MIN(first_processed_at) AS first_processed_at,
                   MAX(last_processed_at) AS last_processed_at
            FROM logical_videos""",
        period_params,
    )

    analysis_counts = _row(
        conn,
        f"""SELECT
                (SELECT COUNT(*) FROM features f JOIN videos v ON f.video_id = v.video_id {scope_where}) AS feature_rows,
                (SELECT COUNT(*) FROM behaviors b JOIN videos v ON b.video_id = v.video_id {scope_where}) AS behavior_rows,
                (SELECT COUNT(*) FROM pairwise p JOIN videos v ON p.video_id = v.video_id {scope_where}) AS pairwise_rows,
                (SELECT COUNT(*) FROM droppings d JOIN videos v ON d.video_id = v.video_id {scope_where}) AS dropping_rows,
                (SELECT COUNT(DISTINCT f.pigeon_id) FROM features f JOIN videos v ON f.video_id = v.video_id {scope_where}) AS pigeons_observed
            """,
        scoped_params * 5,
    )

    videos = _rows(
        conn,
        f"""WITH logical_videos AS (
                SELECT COALESCE(v.chunk_group_id, 'video-' || v.video_id) AS logical_key,
                       COALESCE(MAX(v.logical_video_name), MAX(v.video_name)) AS logical_video_name,
                       MIN(v.video_id) AS first_video_id,
                       MAX(v.session_id) AS session_id,
                       MAX(v.camera_type) AS camera_type,
                       COUNT(*) AS chunks,
                       SUM(CASE WHEN processing_status = 'completed' THEN 1 ELSE 0 END) AS completed_chunks,
                       SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) AS failed_chunks,
                       SUM(CASE WHEN processing_status = 'completed_no_detections' THEN 1 ELSE 0 END) AS no_detection_chunks,
                       SUM(CASE WHEN processing_status = 'processing' THEN 1 ELSE 0 END) AS processing_chunks,
                       SUM(COALESCE(total_frames, 0)) AS total_frames,
                       ROUND(AVG(fps), 2) AS fps,
                       MAX(model_version) AS model_version,
                       MAX(processed_at) AS processed_at,
                       GROUP_CONCAT(v.video_name, ', ') AS chunk_files
                FROM videos v
                {period_where}
                GROUP BY logical_key
            )
            SELECT first_video_id,
                   logical_video_name,
                   session_id,
                   camera_type,
                   chunks,
                   completed_chunks,
                   failed_chunks,
                   no_detection_chunks,
                   total_frames,
                   fps,
                   CASE
                     WHEN completed_chunks = chunks THEN 'completed'
                     WHEN failed_chunks = chunks THEN 'failed'
                     WHEN no_detection_chunks > 0 OR failed_chunks > 0 OR completed_chunks > 0 THEN 'partial'
                     WHEN processing_chunks > 0 THEN 'processing'
                     ELSE 'queued'
                   END AS processing_status,
                   model_version,
                   processed_at,
                   chunk_files
            FROM logical_videos
            ORDER BY processed_at DESC, first_video_id DESC
            LIMIT 50""",
        period_params,
    )

    no_detection_chunks = _rows(
        conn,
        f"""SELECT v.video_id,
                   COALESCE(v.logical_video_name, v.video_name) AS logical_video_name,
                   v.video_name,
                   v.chunk_index,
                   v.chunk_count,
                   v.total_frames,
                   'Chunk produced no detections. Common causes: scene change, occlusion, low contrast, or prompt mismatch.' AS note
            FROM videos v
            {period_where}
              AND v.processing_status = 'completed_no_detections'
            ORDER BY v.processed_at DESC, v.video_id DESC""",
        period_params,
    )

    identity_summary = _rows(
        conn,
        f"""SELECT va.review_status, va.match_method, COUNT(*) AS assignments
            FROM video_assignments va
            JOIN videos v ON va.video_id = v.video_id
            {scope_where}
            GROUP BY va.review_status, va.match_method
            ORDER BY assignments DESC""",
        scoped_params,
    )

    pigeons = _rows(
        conn,
        f"""SELECT f.pigeon_id,
                   COUNT(*) AS frame_observations,
                   COUNT(DISTINCT f.video_id) AS videos,
                   ROUND(AVG(f.confidence), 3) AS mean_confidence,
                   ROUND(AVG(f.velocity_mm_s), 2) AS mean_velocity_mm_s
            FROM features f
            JOIN videos v ON f.video_id = v.video_id
            {scope_where}
            GROUP BY f.pigeon_id
            ORDER BY frame_observations DESC
            LIMIT 50""",
        scoped_params,
    )

    zones = _rows(
        conn,
        f"""SELECT COALESCE(NULLIF(f.current_zone, ''), 'unknown') AS zone,
                   COUNT(*) AS frame_observations,
                   ROUND(SUM(1.0 / COALESCE(NULLIF(v.fps, 0), 30)), 2) AS estimated_seconds,
                   COUNT(DISTINCT f.pigeon_id) AS pigeons
            FROM features f
            JOIN videos v ON f.video_id = v.video_id
            {scope_where}
            GROUP BY COALESCE(NULLIF(f.current_zone, ''), 'unknown')
            ORDER BY frame_observations DESC
            LIMIT 25""",
        scoped_params,
    )

    behaviors = _rows(
        conn,
        f"""SELECT b.behavior,
                   COUNT(*) AS events,
                   ROUND(SUM(COALESCE(b.duration_seconds, 0)), 2) AS duration_seconds,
                   ROUND(AVG(b.confidence), 3) AS mean_confidence,
                   COUNT(DISTINCT b.pigeon_id) AS pigeons
            FROM behaviors b
            JOIN videos v ON b.video_id = v.video_id
            {scope_where}
            GROUP BY b.behavior
            ORDER BY duration_seconds DESC, events DESC""",
        scoped_params,
    )

    pairwise = _rows(
        conn,
        f"""SELECT p.pigeon_a, p.pigeon_b,
                   ROUND(AVG(p.distance_mm), 2) AS mean_distance_mm,
                   ROUND(MIN(p.distance_mm), 2) AS min_distance_mm,
                   COUNT(*) AS frame_observations,
                   SUM(CASE WHEN p.distance_mm IS NOT NULL AND p.distance_mm <= 300 THEN 1 ELSE 0 END) AS close_frames
            FROM pairwise p
            JOIN videos v ON p.video_id = v.video_id
            {scope_where}
            GROUP BY p.pigeon_a, p.pigeon_b
            ORDER BY close_frames DESC, mean_distance_mm ASC
            LIMIT 50""",
        scoped_params,
    )

    droppings = _rows(
        conn,
        f"""SELECT COALESCE(NULLIF(d.zone, ''), 'unknown') AS zone,
                   COUNT(*) AS detections,
                   ROUND(AVG(d.confidence), 3) AS mean_confidence,
                   SUM(CASE WHEN d.review_status = 'approved' THEN 1 ELSE 0 END) AS approved
            FROM droppings d
            JOIN videos v ON d.video_id = v.video_id
            {scope_where}
            GROUP BY COALESCE(NULLIF(d.zone, ''), 'unknown')
            ORDER BY detections DESC""",
        scoped_params,
    )

    qc = _rows(
        conn,
        f"""SELECT q.severity, q.review_status, q.rule_name, COUNT(*) AS flags
            FROM qc_flags q
            JOIN videos v ON q.video_id = v.video_id
            {period_where}
            GROUP BY q.severity, q.review_status, q.rule_name
            ORDER BY flags DESC, q.severity DESC
            LIMIT 50""",
        period_params,
    )

    settings = _rows(
        conn,
        """SELECT key, value FROM app_settings
           WHERE key LIKE 'gemma_%'
           ORDER BY key""",
    )
    env_settings = [
        {"key": key, "value": os.getenv(key, "")}
        for key in [
            "PIGEONLAB_SAM3_VERSION",
            "PIGEONLAB_SAM3_MODEL_DIR",
            "PIGEONLAB_SAM3_MAX_OBJECTS",
            "PIGEONLAB_SAM3_MULTIPLEX_COUNT",
            "PIGEONLAB_SAM3_COMPILE",
            "PIGEONLAB_SAM3_OFFLOAD_VIDEO_TO_CPU",
            "PIGEONLAB_VIDEO_CHUNK_SECONDS",
            "PIGEONLAB_VIDEO_AUTO_CHUNK_UPLOADS",
            "PIGEONLAB_GEMMA_REVIEW_MODE",
            "PIGEONLAB_GEMMA_MODEL",
        ]
        if os.getenv(key) is not None
    ]

    return {
        "filters": filters,
        "approved_only": approved_only,
        "generated_on": date.today().isoformat(),
        "video_summary": video_summary,
        "analysis_counts": analysis_counts,
        "videos": videos,
        "no_detection_chunks": no_detection_chunks,
        "identity_summary": identity_summary,
        "pigeons": pigeons,
        "zones": zones,
        "behaviors": behaviors,
        "pairwise": pairwise,
        "droppings": droppings,
        "qc": qc,
        "settings": settings + env_settings,
    }


def _render_report_html(export_id: str, data: dict) -> str:
    filters = data["filters"]
    title = f"PigeonLab Research Report {export_id}"
    summary = data["video_summary"]
    counts = data["analysis_counts"]
    css = """
    body { font-family: Arial, sans-serif; margin: 40px; color: #172026; line-height: 1.45; }
    h1, h2 { color: #0f766e; }
    .meta, .note { background: #f3f7f6; border: 1px solid #d7e5e2; padding: 14px; border-radius: 8px; }
    .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 18px 0; }
    .metric { border: 1px solid #d7e5e2; border-radius: 8px; padding: 12px; }
    .metric strong { display: block; font-size: 22px; color: #111827; }
    table { width: 100%; border-collapse: collapse; margin: 12px 0 24px; font-size: 13px; }
    th, td { border: 1px solid #d7e5e2; padding: 8px; text-align: left; vertical-align: top; }
    th { background: #eef7f5; }
    .empty { color: #6b7280; font-style: italic; }
    """
    sections = [
        ("Logical Videos", [("first_video_id", "First chunk ID"), ("logical_video_name", "Video"), ("chunks", "Chunks"), ("completed_chunks", "Completed"), ("failed_chunks", "Failed"), ("no_detection_chunks", "No detections"), ("session_id", "Session"), ("camera_type", "Camera"), ("total_frames", "Frames"), ("fps", "FPS"), ("processing_status", "Processing"), ("model_version", "Model"), ("processed_at", "Processed"), ("chunk_files", "Chunk files")], data["videos"]),
        ("No-Detection Chunks", [("video_id", "Chunk ID"), ("logical_video_name", "Video"), ("video_name", "Chunk file"), ("chunk_index", "Chunk"), ("chunk_count", "Total chunks"), ("total_frames", "Frames"), ("note", "Note")], data["no_detection_chunks"]),
        ("Identity Review Summary", [("review_status", "Review status"), ("match_method", "Match method"), ("assignments", "Assignments")], data["identity_summary"]),
        ("Per-Pigeon Tracking Summary", [("pigeon_id", "Pigeon"), ("frame_observations", "Frame observations"), ("videos", "Videos"), ("mean_confidence", "Mean confidence"), ("mean_velocity_mm_s", "Mean velocity (mm/s)")], data["pigeons"]),
        ("Zone Occupancy", [("zone", "Zone"), ("frame_observations", "Frame observations"), ("estimated_seconds", "Estimated seconds"), ("pigeons", "Pigeons")], data["zones"]),
        ("Behavior Summary", [("behavior", "Behavior"), ("events", "Events"), ("duration_seconds", "Duration seconds"), ("mean_confidence", "Mean confidence"), ("pigeons", "Pigeons")], data["behaviors"]),
        ("Pairwise Proximity", [("pigeon_a", "Pigeon A"), ("pigeon_b", "Pigeon B"), ("mean_distance_mm", "Mean distance mm"), ("min_distance_mm", "Min distance mm"), ("frame_observations", "Frame observations"), ("close_frames", "Close frames <=300mm")], data["pairwise"]),
        ("Droppings", [("zone", "Zone"), ("detections", "Detections"), ("mean_confidence", "Mean confidence"), ("approved", "Approved")], data["droppings"]),
        ("QC Flags", [("severity", "Severity"), ("review_status", "Review status"), ("rule_name", "Rule"), ("flags", "Flags")], data["qc"]),
        ("Methods and Runtime Settings", [("key", "Setting"), ("value", "Value")], data["settings"]),
    ]
    section_html = "\n".join(
        f"<h2>{_safe(name)}</h2>{_table_html(columns, rows)}"
        for name, columns, rows in sections
    )
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{_safe(title)}</title>
  <style>{css}</style>
</head>
<body>
  <h1>{_safe(title)}</h1>
  <div class="meta">
    <p><strong>Generated:</strong> {_safe(data["generated_on"])}</p>
    <p><strong>Filters:</strong> {_safe(filters)}</p>
    <p><strong>Analysis scope:</strong> {"Approved videos only" if data["approved_only"] else "All videos in selected period"}</p>
  </div>
  <div class="metrics">
    <div class="metric"><span>Videos</span><strong>{_safe(summary.get("total_videos"))}</strong></div>
    <div class="metric"><span>Completed</span><strong>{_safe(summary.get("completed_videos"))}</strong></div>
    <div class="metric"><span>No-detection videos</span><strong>{_safe(summary.get("videos_with_no_detection_chunks"))}</strong></div>
    <div class="metric"><span>Approved</span><strong>{_safe(summary.get("approved_videos"))}</strong></div>
    <div class="metric"><span>Total frames</span><strong>{_safe(summary.get("total_frames"))}</strong></div>
    <div class="metric"><span>Feature rows</span><strong>{_safe(counts.get("feature_rows"))}</strong></div>
    <div class="metric"><span>Pigeons observed</span><strong>{_safe(counts.get("pigeons_observed"))}</strong></div>
  </div>
  <div class="note">
    <strong>Interpretation note:</strong> This report is a reproducibility and screening artifact. Publication-ready
    claims should cite the exported CSV tables, study protocol, calibration procedure, and human review status.
  </div>
  {section_html}
</body>
</html>
"""


def _render_report_md(export_id: str, data: dict) -> str:
    summary = data["video_summary"]
    counts = data["analysis_counts"]
    lines = [
        f"# PigeonLab Research Report {export_id}",
        "",
        f"Generated: {data['generated_on']}",
        f"Filters: `{data['filters']}`",
        f"Analysis scope: {'Approved videos only' if data['approved_only'] else 'All videos in selected period'}",
        "",
        "## Overview",
        "",
        f"- Videos: {_fmt(summary.get('total_videos'))}",
        f"- Completed videos: {_fmt(summary.get('completed_videos'))}",
        f"- Videos with no-detection chunks: {_fmt(summary.get('videos_with_no_detection_chunks'))}",
        f"- Approved videos: {_fmt(summary.get('approved_videos'))}",
        f"- Total frames: {_fmt(summary.get('total_frames'))}",
        f"- Feature rows: {_fmt(counts.get('feature_rows'))}",
        f"- Pigeons observed: {_fmt(counts.get('pigeons_observed'))}",
        "",
        "> Interpretation note: This report is a reproducibility and screening artifact. Publication-ready claims should cite the exported CSV tables, study protocol, calibration procedure, and human review status.",
        "",
    ]
    sections = [
        ("Logical Videos", [("first_video_id", "First chunk ID"), ("logical_video_name", "Video"), ("chunks", "Chunks"), ("completed_chunks", "Completed"), ("failed_chunks", "Failed"), ("no_detection_chunks", "No detections"), ("session_id", "Session"), ("camera_type", "Camera"), ("total_frames", "Frames"), ("fps", "FPS"), ("processing_status", "Processing"), ("model_version", "Model"), ("processed_at", "Processed"), ("chunk_files", "Chunk files")], data["videos"]),
        ("No-Detection Chunks", [("video_id", "Chunk ID"), ("logical_video_name", "Video"), ("video_name", "Chunk file"), ("chunk_index", "Chunk"), ("chunk_count", "Total chunks"), ("total_frames", "Frames"), ("note", "Note")], data["no_detection_chunks"]),
        ("Identity Review Summary", [("review_status", "Review status"), ("match_method", "Match method"), ("assignments", "Assignments")], data["identity_summary"]),
        ("Per-Pigeon Tracking Summary", [("pigeon_id", "Pigeon"), ("frame_observations", "Frame observations"), ("videos", "Videos"), ("mean_confidence", "Mean confidence"), ("mean_velocity_mm_s", "Mean velocity (mm/s)")], data["pigeons"]),
        ("Zone Occupancy", [("zone", "Zone"), ("frame_observations", "Frame observations"), ("estimated_seconds", "Estimated seconds"), ("pigeons", "Pigeons")], data["zones"]),
        ("Behavior Summary", [("behavior", "Behavior"), ("events", "Events"), ("duration_seconds", "Duration seconds"), ("mean_confidence", "Mean confidence"), ("pigeons", "Pigeons")], data["behaviors"]),
        ("Pairwise Proximity", [("pigeon_a", "Pigeon A"), ("pigeon_b", "Pigeon B"), ("mean_distance_mm", "Mean distance mm"), ("min_distance_mm", "Min distance mm"), ("frame_observations", "Frame observations"), ("close_frames", "Close frames <=300mm")], data["pairwise"]),
        ("Droppings", [("zone", "Zone"), ("detections", "Detections"), ("mean_confidence", "Mean confidence"), ("approved", "Approved")], data["droppings"]),
        ("QC Flags", [("severity", "Severity"), ("review_status", "Review status"), ("rule_name", "Rule"), ("flags", "Flags")], data["qc"]),
        ("Methods and Runtime Settings", [("key", "Setting"), ("value", "Value")], data["settings"]),
    ]
    for name, columns, rows in sections:
        lines.extend([f"## {name}", "", _table_md(columns, rows), ""])
    return "\n".join(lines)


def _create_research_report(body: ExportRequest) -> dict:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    export_id = str(uuid.uuid4())[:8]
    with get_db() as conn:
        data = _report_data(conn, body.filters)

    html_name = f"research_report_{export_id}.html"
    md_name = f"research_report_{export_id}.md"
    manifest_name = f"manifest_{export_id}.txt"
    (EXPORTS_DIR / html_name).write_text(_render_report_html(export_id, data), encoding="utf-8")
    (EXPORTS_DIR / md_name).write_text(_render_report_md(export_id, data), encoding="utf-8")
    (EXPORTS_DIR / manifest_name).write_text(
        f"Export ID: {export_id}\n"
        f"Date: {date.today().isoformat()}\n"
        f"Format: research_report\n"
        f"Filters: {body.filters}\n"
        f"Files: {html_name}, {md_name}, {manifest_name}\n"
        f"Feature rows: {data['analysis_counts'].get('feature_rows')}\n",
        encoding="utf-8",
    )
    return {
        "download_url": f"/api/export/download/{html_name}",
        "files_included": [html_name, md_name, manifest_name],
        "rows_exported": int(data["analysis_counts"].get("feature_rows") or 0),
        "report_summary": {
            "videos": data["video_summary"].get("total_videos"),
            "feature_rows": data["analysis_counts"].get("feature_rows"),
            "pigeons_observed": data["analysis_counts"].get("pigeons_observed"),
        },
    }


@router.post("/")
async def create_export(body: ExportRequest):
    if body.format in {"research_report", "html_report", "report"}:
        return _create_research_report(body)

    if body.format != "csv":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported export format '{body.format}'. Only 'csv' is currently supported.",
        )

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    files_included = []
    total_rows = 0

    export_id = str(uuid.uuid4())[:8]

    with get_db() as conn:
        for table_name in body.include:
            if table_name == "features":
                period_sql, params = _period_clause(body.filters.get("period"))

                video_id = body.filters.get("video_id")
                video_sql = ""
                if video_id is not None:
                    video_sql = "AND f.video_id = ?"
                    params.append(video_id)

                pigeon_id = body.filters.get("pigeon_id")
                pigeon_sql = ""
                if pigeon_id:
                    pigeon_sql = "AND f.pigeon_id = ?"
                    params.append(pigeon_id)

                rows = conn.execute(
                    f"""SELECT f.* FROM features f
                        JOIN videos v ON f.video_id = v.video_id
                        WHERE v.review_status = 'approved'
                          {period_sql} {video_sql} {pigeon_sql}
                        ORDER BY f.video_id, f.frame_idx""",
                    params,
                ).fetchall()

                if not rows:
                    # Fall back to all features if none approved
                    rows = conn.execute(
                        f"""SELECT f.* FROM features f
                            JOIN videos v ON f.video_id = v.video_id
                            WHERE 1=1 {period_sql} {video_sql} {pigeon_sql}
                            ORDER BY f.video_id, f.frame_idx""",
                        params,
                    ).fetchall()

                filename = f"features_{export_id}.csv"
                filepath = EXPORTS_DIR / filename

                if rows:
                    columns = rows[0].keys()
                    output = io.StringIO()
                    writer = csv.writer(output)
                    writer.writerow(columns)
                    for row in rows:
                        writer.writerow([row[c] for c in columns])

                    filepath.write_text(output.getvalue())
                    total_rows += len(rows)
                else:
                    filepath.write_text("")

                files_included.append(filename)

            elif table_name == "behaviors":
                period_sql, params = _period_clause(body.filters.get("period"))

                rows = conn.execute(
                    f"""SELECT b.* FROM behaviors b
                        JOIN videos v ON b.video_id = v.video_id
                        WHERE 1=1 {period_sql}
                        ORDER BY b.video_id, b.start_frame""",
                    params,
                ).fetchall()

                filename = f"behaviors_{export_id}.csv"
                filepath = EXPORTS_DIR / filename

                if rows:
                    columns = rows[0].keys()
                    output = io.StringIO()
                    writer = csv.writer(output)
                    writer.writerow(columns)
                    for row in rows:
                        writer.writerow([row[c] for c in columns])
                    filepath.write_text(output.getvalue())
                    total_rows += len(rows)
                else:
                    filepath.write_text("")

                files_included.append(filename)

            elif table_name == "pairwise":
                period_sql, params = _period_clause(body.filters.get("period"))

                rows = conn.execute(
                    f"""SELECT p.* FROM pairwise p
                        JOIN videos v ON p.video_id = v.video_id
                        WHERE 1=1 {period_sql}
                        ORDER BY p.video_id, p.frame_idx""",
                    params,
                ).fetchall()

                filename = f"pairwise_{export_id}.csv"
                filepath = EXPORTS_DIR / filename

                if rows:
                    columns = rows[0].keys()
                    output = io.StringIO()
                    writer = csv.writer(output)
                    writer.writerow(columns)
                    for row in rows:
                        writer.writerow([row[c] for c in columns])
                    filepath.write_text(output.getvalue())
                    total_rows += len(rows)
                else:
                    filepath.write_text("")

                files_included.append(filename)

            elif table_name == "droppings":
                period_sql, params = _period_clause(body.filters.get("period"))

                rows = conn.execute(
                    f"""SELECT d.* FROM droppings d
                        JOIN videos v ON d.video_id = v.video_id
                        WHERE 1=1 {period_sql}
                        ORDER BY d.video_id, d.frame_idx""",
                    params,
                ).fetchall()

                filename = f"droppings_{export_id}.csv"
                filepath = EXPORTS_DIR / filename

                if rows:
                    columns = rows[0].keys()
                    output = io.StringIO()
                    writer = csv.writer(output)
                    writer.writerow(columns)
                    for row in rows:
                        writer.writerow([row[c] for c in columns])
                    filepath.write_text(output.getvalue())
                    total_rows += len(rows)
                else:
                    filepath.write_text("")

                files_included.append(filename)

    if body.include_manifest:
        manifest_name = f"manifest_{export_id}.txt"
        manifest_path = EXPORTS_DIR / manifest_name
        manifest_path.write_text(
            f"Export ID: {export_id}\n"
            f"Date: {date.today().isoformat()}\n"
            f"Format: {body.format}\n"
            f"Tables: {', '.join(body.include)}\n"
            f"Filters: {body.filters}\n"
            f"Files: {', '.join(files_included)}\n"
            f"Total rows: {total_rows}\n"
        )
        files_included.append(manifest_name)

    return {
        "download_url": f"/api/export/download/{files_included[0]}" if files_included else None,
        "files_included": files_included,
        "rows_exported": total_rows,
    }


@router.get("/download/{filename}")
async def download_export(filename: str):
    # Prevent path traversal on both POSIX and Windows path syntaxes.
    if (
        PurePath(filename).name != filename
        or PureWindowsPath(filename).name != filename
        or Path(filename).is_absolute()
        or PureWindowsPath(filename).is_absolute()
    ):
        raise HTTPException(status_code=400, detail="Invalid filename")

    exports_root = EXPORTS_DIR.resolve()
    filepath = (exports_root / filename).resolve()
    if filepath.parent != exports_root:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not filepath.is_file():
        raise HTTPException(status_code=404, detail=f"Export file '{filename}' not found")

    if filename.endswith(".csv"):
        media_type = "text/csv"
    elif filename.endswith(".html"):
        media_type = "text/html"
    elif filename.endswith(".md"):
        media_type = "text/markdown"
    else:
        media_type = "text/plain"
    return FileResponse(
        filepath,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
