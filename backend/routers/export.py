import csv
import io
import uuid
from datetime import date, timedelta
from pathlib import Path, PurePath, PureWindowsPath

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


@router.post("/")
async def create_export(body: ExportRequest):
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

    media_type = "text/csv" if filename.endswith(".csv") else "text/plain"
    return FileResponse(
        filepath,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
