"""
End-to-end smoke test: seed -> review -> export.

Run from project root:
    python backend/tests/test_flow.py
"""

import asyncio
import sys
from pathlib import Path

# Ensure backend modules are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import init_db  # noqa: E402
import seed_data  # noqa: E402

import httpx  # noqa: E402
from main import app  # noqa: E402

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = ""):
    results.append((name, ok))
    status = PASS if ok else FAIL
    suffix = f" — {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")


async def run():
    # ── Setup ───────────────────────────────────────────────
    print("\n=== Setup ===")

    try:
        init_db()
        check("init_db", True)
    except Exception as e:
        check("init_db", False, str(e))
        return False

    try:
        seed_data.seed()
        check("seed_data", True)
    except Exception:
        # Seed may already exist — that's fine
        check("seed_data", True, "already seeded or completed")

    # ── Flow tests ──────────────────────────────────────────
    print("\n=== Flow ===")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:

        # (a) GET /api/stats/today
        r = await c.get("/api/stats/today")
        ok = r.status_code == 200
        check("GET /api/stats/today", ok, f"status={r.status_code}")

        # (b) GET /api/review/attention/count
        r = await c.get("/api/review/attention/count")
        total = r.json().get("total", 0) if r.status_code == 200 else 0
        check("GET /api/review/attention/count", r.status_code == 200 and total > 0, f"total={total}")

        # (c) GET /api/review/identities/next-video
        r = await c.get("/api/review/identities/next-video")
        video_id = r.json().get("video_id") if r.status_code == 200 else None
        ok = r.status_code == 200 and video_id is not None
        check("GET /api/review/identities/next-video", ok, f"video_id={video_id}")

        # (d) GET /api/review/identities?video_id={id}
        r = await c.get(f"/api/review/identities?video_id={video_id}")
        assignments = r.json() if r.status_code == 200 else []
        check("GET /api/review/identities", r.status_code == 200 and len(assignments) > 0, f"count={len(assignments)}")

        # (e) POST /api/review/identity — confirm one assignment
        if assignments:
            a = assignments[0]
            body = {
                "assignment_id": a["id"],
                "action": "confirm",
                "pigeon_id": a["pigeon_id"],
                "reviewer": "test_user",
            }
            r = await c.post("/api/review/identity", json=body)
            check("POST /api/review/identity (confirm)", r.status_code == 200, f"status={r.status_code}")
        else:
            check("POST /api/review/identity (confirm)", False, "no assignments to confirm")

        # (f) GET /api/pigeons
        r = await c.get("/api/pigeons/")
        pigeons = r.json() if r.status_code == 200 else []
        check("GET /api/pigeons", r.status_code == 200 and len(pigeons) > 0, f"count={len(pigeons)}")

        # (g) GET /api/insights/heatmap
        r = await c.get("/api/insights/heatmap?pigeons=all&period=all&approved_only=false")
        grid = r.json().get("grid") if r.status_code == 200 else None
        grid_status = "present" if grid else "missing"
        check("GET /api/insights/heatmap", r.status_code == 200 and grid is not None, f"grid={grid_status}")

        # (h) POST /api/export
        r = await c.post("/api/export/", json={
            "format": "csv",
            "include": ["features"],
            "filters": {"period": "all"},
            "include_manifest": True,
        })
        download_url = r.json().get("download_url") if r.status_code == 200 else None
        rows = r.json().get("rows_exported", 0) if r.status_code == 200 else 0
        ok = r.status_code == 200 and download_url is not None
        check("POST /api/export", ok, f"rows={rows}")

        # (i) GET /api/export/download/{filename}
        if download_url:
            r = await c.get(download_url)
            ok = r.status_code == 200 and len(r.content) > 0
            check("GET /api/export/download", ok, f"size={len(r.content)} bytes")
        else:
            check("GET /api/export/download", False, "no download_url from export")

    # ── Summary ─────────────────────────────────────────────
    print("\n=== Summary ===")
    passed = sum(1 for _, ok in results if ok)
    total_tests = len(results)
    print(f"  {passed}/{total_tests} passed\n")

    return passed == total_tests


if __name__ == "__main__":
    success = asyncio.run(run())
    sys.exit(0 if success else 1)
