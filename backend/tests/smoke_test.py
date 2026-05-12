"""PigeonLab workstation smoke test.

Full runtime test:
    python -m backend.tests.smoke_test

Fixture/DB-only sandbox test:
    python -m backend.tests.smoke_test --offline
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
FIXTURE = BACKEND_ROOT / "tests" / "fixtures" / "smoke_video.mp4"
sys.path.insert(0, str(BACKEND_ROOT))


def _elapsed(start: float) -> float:
    return round(time.perf_counter() - start, 2)


def _run(args: list[str], timeout: int = 20) -> tuple[bool, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = (result.stdout or result.stderr).strip()
    return result.returncode == 0, output


def validate_fixture() -> dict:
    if not FIXTURE.is_file():
        raise RuntimeError(f"Smoke video fixture is missing: {FIXTURE}")
    size = FIXTURE.stat().st_size
    if size >= 1_000_000:
        raise RuntimeError(f"Smoke video fixture must stay under 1 MB; found {size} bytes")

    metadata = {"path": str(FIXTURE), "size_bytes": size}
    ok, output = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,nb_frames,duration",
            "-of",
            "json",
            str(FIXTURE),
        ]
    )
    if ok:
        try:
            stream = json.loads(output)["streams"][0]
            metadata.update(
                {
                    "width": int(stream.get("width") or 0),
                    "height": int(stream.get("height") or 0),
                    "frames": int(stream.get("nb_frames") or 0),
                    "duration_seconds": round(float(stream.get("duration") or 0), 2),
                }
            )
        except Exception:
            metadata["ffprobe_output"] = output[:500]
    else:
        metadata["ffprobe_warning"] = output[:500]
    return metadata


def run_offline() -> int:
    timings: dict[str, float] = {}
    started = time.perf_counter()
    fixture = validate_fixture()
    timings["fixture_validation_s"] = _elapsed(started)

    db_start = time.perf_counter()
    import database

    with tempfile.TemporaryDirectory() as tmpdir:
        database.DB_PATH = Path(tmpdir) / "pigeonlab.db"
        database.init_db()
        with database.get_db() as conn:
            cursor = conn.execute(
                """INSERT INTO videos
                   (video_name, source_path, logical_video_name, original_source_path,
                    chunk_index, chunk_count, camera_type, processing_status)
                   VALUES (?, ?, ?, ?, 1, 1, 'Smoke fixture', 'queued')""",
                (FIXTURE.name, str(FIXTURE), FIXTURE.name, str(FIXTURE)),
            )
            video_id = cursor.lastrowid
            conn.commit()
            row = conn.execute(
                "SELECT video_id, video_name, source_path FROM videos WHERE video_id = ?",
                (video_id,),
            ).fetchone()
            if not row or row["source_path"] != str(FIXTURE):
                raise RuntimeError("Smoke DB insert/readback failed")
    timings["db_upload_s"] = _elapsed(db_start)

    print("PASS smoke fixture/DB test")
    print(json.dumps({"fixture": fixture, "timings": timings}, indent=2))
    return 0


async def run_runtime(timeout_seconds: int) -> int:
    fixture = validate_fixture()
    timings: dict[str, float] = {}

    import database
    from main import app
    import httpx

    database.init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        upload_start = time.perf_counter()
        with FIXTURE.open("rb") as handle:
            response = await client.post(
                "/api/videos/upload",
                files={"files": (FIXTURE.name, handle, "video/mp4")},
                data={
                    "process_now": "true",
                    "text_prompt": "pigeon",
                    "expected_pigeon_count": "2",
                    "camera_type": "Smoke fixture",
                },
            )
        if response.status_code != 200:
            raise RuntimeError(f"Upload failed: {response.status_code} {response.text}")
        payload = response.json()
        job_id = payload["job_id"]
        uploaded = payload.get("uploaded_files") or []
        video_ids = [item["video_id"] for item in uploaded if item.get("video_id")]
        timings["upload_s"] = _elapsed(upload_start)

        process_start = time.perf_counter()
        deadline = time.perf_counter() + timeout_seconds
        job_status = {"status": "running"}
        while time.perf_counter() < deadline:
            await asyncio.sleep(2)
            status_response = await client.get(f"/api/videos/jobs/{job_id}")
            if status_response.status_code == 200:
                job_status = status_response.json()
                if job_status.get("status") in {"completed", "partial", "failed", "cancelled"}:
                    break
        timings["processing_s"] = _elapsed(process_start)
        if job_status.get("status") != "completed":
            raise RuntimeError(f"Smoke processing did not complete: {job_status}")

        verify_start = time.perf_counter()
        with database.get_db() as conn:
            placeholders = ",".join("?" for _ in video_ids)
            rows = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM features WHERE video_id IN ({placeholders})",
                video_ids,
            ).fetchone()
            feature_rows = rows["cnt"] if rows else 0
        if feature_rows <= 0:
            raise RuntimeError("Smoke processing completed but wrote no feature rows")
        timings["verify_s"] = _elapsed(verify_start)

        cleanup_start = time.perf_counter()
        for video_id in video_ids:
            await client.delete(f"/api/videos/{video_id}")
        timings["cleanup_s"] = _elapsed(cleanup_start)

    print("PASS full smoke test")
    print(
        json.dumps(
            {
                "fixture": fixture,
                "job_id": job_id,
                "video_ids": video_ids,
                "feature_rows": feature_rows,
                "timings": timings,
            },
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Validate the checked-in fixture and DB insert path without FastAPI/SAM3/CUDA.",
    )
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    try:
        if args.offline:
            return run_offline()
        return asyncio.run(run_runtime(args.timeout))
    except Exception as exc:
        print(f"FAIL smoke test: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
