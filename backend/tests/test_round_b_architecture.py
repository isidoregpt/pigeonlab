"""Round B architecture regression checks.

These tests avoid CUDA and SAM3 runtime work. They verify the database-facing
contracts that make chunked videos behave like one logical upload.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import fastapi  # noqa: F401
    import pydantic  # noqa: F401
except Exception:
    fastapi_fake = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class APIRouter:
        def get(self, *_args, **_kwargs):
            return lambda func: func

        def post(self, *_args, **_kwargs):
            return lambda func: func

        def put(self, *_args, **_kwargs):
            return lambda func: func

        def delete(self, *_args, **_kwargs):
            return lambda func: func

    def Query(default=None, **_kwargs):
        return default

    def Field(default=None, default_factory=None, **_kwargs):
        return default_factory() if default_factory is not None else default

    class Request:
        pass

    fastapi_fake.APIRouter = APIRouter
    fastapi_fake.HTTPException = HTTPException
    fastapi_fake.Query = Query
    fastapi_fake.Request = Request
    sys.modules["fastapi"] = fastapi_fake

    responses_fake = types.ModuleType("fastapi.responses")
    responses_fake.FileResponse = object
    responses_fake.StreamingResponse = object
    sys.modules["fastapi.responses"] = responses_fake

    pydantic_fake = types.ModuleType("pydantic")

    class BaseModel:
        def __init__(self, **kwargs):
            for name, value in self.__class__.__dict__.items():
                if not name.startswith("_") and name not in kwargs and not callable(value):
                    setattr(self, name, value)
            for key, value in kwargs.items():
                setattr(self, key, value)

    pydantic_fake.BaseModel = BaseModel
    pydantic_fake.Field = Field
    sys.modules["pydantic"] = pydantic_fake

services_sam3_fake = types.ModuleType("services.sam3")
services_sam3_fake.get_sam3_status = lambda load_model=False: {"ready": True, "errors": [], "warnings": []}
sys.modules.setdefault("services.sam3", services_sam3_fake)

services_video_processor_fake = types.ModuleType("services.video_processor")

class VideoProcessor:
    async def process_video(self, *_args, **_kwargs):
        return {"status": "completed"}

services_video_processor_fake.VideoProcessor = VideoProcessor
sys.modules.setdefault("services.video_processor", services_video_processor_fake)

services_frame_extractor_fake = types.ModuleType("services.frame_extractor")

class FrameExtractor:
    def cleanup_frames(self, _video_id: int) -> int:
        return 0

services_frame_extractor_fake.FrameExtractor = FrameExtractor
sys.modules.setdefault("services.frame_extractor", services_frame_extractor_fake)

import database  # noqa: E402
from routers import export, review, videos  # noqa: E402


class RoundBArchitectureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self.tmp.name) / "pigeonlab.db"
        database.init_db()
        self._seed_chunk_group()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _seed_chunk_group(self) -> None:
        with database.get_db() as conn:
            for pigeon_id in ["Alpha", "Bravo", "unknown_0", "unknown_1"]:
                conn.execute(
                    "INSERT OR IGNORE INTO pigeons (pigeon_id, first_seen) VALUES (?, datetime('now'))",
                    (pigeon_id,),
                )

            for idx, status in enumerate(["completed", "completed", "failed"], start=1):
                conn.execute(
                    """INSERT INTO videos
                       (video_id, video_name, source_path, logical_video_name,
                        original_source_path, chunk_group_id, chunk_index,
                        chunk_count, chunk_seconds, session_id, camera_type,
                        total_frames, fps, processed_at, review_status,
                        processing_status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 3, 60, 'session-a',
                               'Uploaded video', 100, 30.0, '2026-05-12T12:00:00',
                               'approved', ?)""",
                    (
                        idx,
                        f"Pigeon1_part{idx - 1:03d}.mp4",
                        f"C:/videos/Pigeon1_part{idx - 1:03d}.mp4",
                        "Pigeon1.mp4",
                        "C:/videos/Pigeon1.mp4",
                        "group-1",
                        idx,
                        status,
                    ),
                )

            conn.execute(
                """INSERT INTO video_assignments
                   (video_id, video_obj_id, pigeon_id, confidence, match_method,
                    review_status)
                   VALUES (1, 0, 'Alpha', 0.95, 'manual', 'approved'),
                          (1, 1, 'Bravo', 0.92, 'manual', 'approved'),
                          (2, 0, 'unknown_0', 0.80, 'placeholder', 'raw'),
                          (2, 1, 'unknown_1', 0.81, 'placeholder', 'raw')"""
            )
            conn.execute(
                """INSERT INTO features
                   (video_id, frame_idx, pigeon_id, centroid_x, centroid_y,
                    confidence, current_zone)
                   VALUES (2, 0, 'unknown_0', 10, 20, 0.8, 'left'),
                          (2, 0, 'unknown_1', 30, 40, 0.8, 'right')"""
            )
            conn.execute(
                """INSERT INTO pairwise
                   (video_id, frame_idx, pigeon_a, pigeon_b, distance_px, distance_mm)
                   VALUES (2, 0, 'unknown_0', 'unknown_1', 10, 100)"""
            )
            conn.commit()

    def test_chunk_group_status_reports_partial_completion(self) -> None:
        with database.get_db() as conn:
            status = videos._chunk_group_statuses(conn, ["group-1"])["group-1"]
        self.assertEqual(status["chunk_group_status"], "partial")
        self.assertEqual(status["chunk_group_completed"], 2)
        self.assertEqual(status["chunk_group_failed"], 1)
        self.assertEqual(status["chunk_group_status_label"], "Partial (2/3, 1 failed)")

    def test_previous_chunk_identity_carryover_updates_analysis_rows(self) -> None:
        result = asyncio.run(
            review.apply_chunk_carryover_identities(
                review.ChunkCarryoverRequest(video_id=2, reviewer="round-b-test")
            )
        )
        self.assertEqual(result["applied"], 2)

        with database.get_db() as conn:
            assignments = conn.execute(
                """SELECT video_obj_id, pigeon_id, review_status, match_method
                   FROM video_assignments
                   WHERE video_id = 2
                   ORDER BY video_obj_id"""
            ).fetchall()
            features = conn.execute(
                "SELECT pigeon_id FROM features WHERE video_id = 2 ORDER BY pigeon_id"
            ).fetchall()
            pairwise = conn.execute(
                "SELECT pigeon_a, pigeon_b FROM pairwise WHERE video_id = 2"
            ).fetchone()

        self.assertEqual([row["pigeon_id"] for row in assignments], ["Alpha", "Bravo"])
        self.assertTrue(all(row["review_status"] == "approved" for row in assignments))
        self.assertTrue(all(row["match_method"] == "manual_chunk_carryover" for row in assignments))
        self.assertEqual([row["pigeon_id"] for row in features], ["Alpha", "Bravo"])
        self.assertEqual((pairwise["pigeon_a"], pairwise["pigeon_b"]), ("Alpha", "Bravo"))

    def test_research_report_aggregates_chunks_as_one_logical_video(self) -> None:
        with database.get_db() as conn:
            data = export._report_data(conn, {"period": "all", "approved_only": False})

        self.assertEqual(data["video_summary"]["total_videos"], 1)
        self.assertEqual(data["videos"][0]["logical_video_name"], "Pigeon1.mp4")
        self.assertEqual(data["videos"][0]["chunks"], 3)
        self.assertEqual(data["videos"][0]["processing_status"], "partial")


if __name__ == "__main__":
    unittest.main()
