"""Round A v3 regression checks.

These tests focus on the claims that were hardest to verify manually:
pre-torch environment loading, SAM3 CPU offload forwarding/fallback, upload
auto-chunking order, installer venv invocation, and delete cleanup.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def import_videos_with_fakes():
    """Import routers.videos without requiring FastAPI/Pydantic in this sandbox."""
    for name in [
        "routers.videos",
        "fastapi",
        "fastapi.responses",
        "pydantic",
        "services.ffmpeg_ingest",
        "services.frame_extractor",
        "services.sam3",
        "services.video_processor",
        "utils",
    ]:
        sys.modules.pop(name, None)

    fastapi = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class APIRouter:
        def get(self, *_args, **_kwargs):
            return lambda func: func

        def post(self, *_args, **_kwargs):
            return lambda func: func

        def delete(self, *_args, **_kwargs):
            return lambda func: func

        def put(self, *_args, **_kwargs):
            return lambda func: func

    fastapi.APIRouter = APIRouter
    fastapi.HTTPException = HTTPException
    fastapi.Query = lambda default=None, **_kwargs: default
    fastapi.Request = object
    sys.modules["fastapi"] = fastapi

    responses = types.ModuleType("fastapi.responses")
    responses.FileResponse = object
    responses.StreamingResponse = object
    sys.modules["fastapi.responses"] = responses

    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = type("BaseModel", (), {})
    pydantic.Field = lambda default=None, **_kwargs: default
    sys.modules["pydantic"] = pydantic

    ffmpeg_ingest = types.ModuleType("services.ffmpeg_ingest")
    ffmpeg_ingest.default_chunk_seconds = lambda: 60
    ffmpeg_ingest.default_output_dir = lambda: PROJECT_ROOT / "data" / "videos" / "output"
    ffmpeg_ingest.get_ffmpeg_status = lambda: {"available": True}
    ffmpeg_ingest.ingest_folder = lambda *_args, **_kwargs: {}
    ffmpeg_ingest.probe_duration = lambda _path: None
    ffmpeg_ingest.split_video = lambda *_args, **_kwargs: {"chunks": []}
    sys.modules["services.ffmpeg_ingest"] = ffmpeg_ingest

    frame_extractor = types.ModuleType("services.frame_extractor")
    frame_extractor.FrameExtractor = type(
        "FrameExtractor",
        (),
        {"cleanup_frames": lambda self, video_id: 0},
    )
    sys.modules["services.frame_extractor"] = frame_extractor

    sam3 = types.ModuleType("services.sam3")
    sam3.get_sam3_status = lambda load_model=False: {"ready": True, "errors": [], "warnings": []}
    sys.modules["services.sam3"] = sam3

    video_processor = types.ModuleType("services.video_processor")
    video_processor.VideoProcessor = type("VideoProcessor", (), {})
    sys.modules["services.video_processor"] = video_processor

    utils = types.ModuleType("utils")
    utils.get_default_reviewer = lambda: "test"
    sys.modules["utils"] = utils

    return importlib.import_module("routers.videos")


class RoundARegressionTests(unittest.TestCase):
    def test_allocator_env_is_logged_before_torch_probe(self) -> None:
        code = textwrap.dedent(
            f"""
            import os
            import sys
            sys.path.insert(0, {str(BACKEND_ROOT)!r})
            os.environ.pop("PYTORCH_CUDA_ALLOC_CONF", None)
            from env_loader import load_env_file
            load_env_file({str(PROJECT_ROOT / ".env.example")!r}, override=True)
            if "torch" in sys.modules:
                raise SystemExit("torch imported before logging setup")
            from logging_config import configure_logging
            configure_logging()
            print("ALLOC=" + os.environ.get("PYTORCH_CUDA_ALLOC_CONF", "<not set>"))
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("ALLOC=expandable_segments:True", combined)
        self.assertIn("Pre-torch PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True", combined)
        self.assertIn("torch_imported=False", combined)

    def test_sam3_offload_request_and_loader_default_patch(self) -> None:
        calls: list[object] = []
        old_modules = {
            name: sys.modules.get(name)
            for name in ("numpy", "PIL", "PIL.Image", "sam3", "sam3.model", "sam3.model.io_utils")
        }

        numpy = types.ModuleType("numpy")
        numpy.ndarray = object  # type: ignore[attr-defined]
        sys.modules["numpy"] = numpy
        pil = types.ModuleType("PIL")
        pil_image = types.ModuleType("PIL.Image")
        pil.Image = pil_image  # type: ignore[attr-defined]
        sys.modules["PIL"] = pil
        sys.modules["PIL.Image"] = pil_image

        sam3_pkg = types.ModuleType("sam3")
        model_pkg = types.ModuleType("sam3.model")
        model_pkg.__path__ = []  # type: ignore[attr-defined]
        io_utils = types.ModuleType("sam3.model.io_utils")

        def fake_loader(*_args, offload_video_to_cpu: bool = False, **_kwargs):
            calls.append(("loader_offload", offload_video_to_cpu))
            if not offload_video_to_cpu:
                calls.append("cuda_called")
            return "video_tensor", 10, 20

        io_utils.load_video_frames_from_video_file_using_cv2 = fake_loader  # type: ignore[attr-defined]
        model_pkg.io_utils = io_utils  # type: ignore[attr-defined]
        sam3_pkg.model = model_pkg  # type: ignore[attr-defined]
        sys.modules["sam3"] = sam3_pkg
        sys.modules["sam3.model"] = model_pkg
        sys.modules["sam3.model.io_utils"] = io_utils

        sam3_service = None
        old_torch_available = None
        old_patch_state = None
        old_env = os.environ.get("PIGEONLAB_SAM3_ENABLE_WINDOWS_PATCHES")
        try:
            sys.modules.pop("services.sam3", None)
            sam3_service = importlib.import_module("services.sam3")
            old_torch_available = sam3_service.TORCH_AVAILABLE
            old_patch_state = sam3_service._SAM3_RUNTIME_PATCHES_APPLIED
            sam3_service.TORCH_AVAILABLE = True
            sam3_service._SAM3_RUNTIME_PATCHES_APPLIED = False
            os.environ["PIGEONLAB_SAM3_ENABLE_WINDOWS_PATCHES"] = "1"

            sam3_service._apply_sam3_runtime_patches()
            io_utils.load_video_frames_from_video_file_using_cv2("video.mp4")
            self.assertIn(("loader_offload", True), calls)
            self.assertNotIn("cuda_called", calls)

            class FakePredictor:
                request: dict | None = None

                def handle_request(self, request):
                    self.request = request
                    return {"session_id": "session-1"}

            predictor = FakePredictor()
            wrapper = sam3_service.SAM3Wrapper.__new__(sam3_service.SAM3Wrapper)
            wrapper._loaded = True
            wrapper._using_native = True
            wrapper._video_predictor = predictor

            os.environ["PIGEONLAB_SAM3_OFFLOAD_VIDEO_TO_CPU"] = "1"
            session_id = wrapper.start_video_session("video.mp4")
            self.assertEqual(session_id, "session-1")
            self.assertIs(predictor.request["offload_video_to_cpu"], True)
        finally:
            if sam3_service is not None and old_torch_available is not None:
                sam3_service.TORCH_AVAILABLE = old_torch_available
            if sam3_service is not None and old_patch_state is not None:
                sam3_service._SAM3_RUNTIME_PATCHES_APPLIED = old_patch_state
            if old_env is None:
                os.environ.pop("PIGEONLAB_SAM3_ENABLE_WINDOWS_PATCHES", None)
            else:
                os.environ["PIGEONLAB_SAM3_ENABLE_WINDOWS_PATCHES"] = old_env
            for name, module in old_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

    def test_upload_auto_chunking_happens_before_processing_entries_are_created(self) -> None:
        videos = import_videos_with_fakes()

        old_probe = videos.probe_duration
        old_split = videos.split_video
        old_chunk_seconds = videos.default_chunk_seconds
        old_output_dir = videos.default_output_dir
        old_auto = os.environ.get("PIGEONLAB_VIDEO_AUTO_CHUNK_UPLOADS")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            chunks = [tmp_path / f"chunk_{idx}.mp4" for idx in range(3)]
            try:
                os.environ["PIGEONLAB_VIDEO_AUTO_CHUNK_UPLOADS"] = "1"
                videos.probe_duration = lambda _path: 181.0
                videos.default_chunk_seconds = lambda: 60
                videos.default_output_dir = lambda: tmp_path
                videos.split_video = lambda _path, _out, seconds: {
                    "chunks": [str(path) for path in chunks],
                    "chunk_seconds": seconds,
                }

                with self.assertLogs("routers.videos", level="INFO") as logs:
                    expanded = videos._auto_chunk_entries(
                        [
                            {
                                "video_path": str(tmp_path / "long.mp4"),
                                "video_name": "long.mp4",
                                "source_path": str(tmp_path / "long.mp4"),
                            }
                        ]
                    )

                self.assertEqual(len(expanded), 3)
                self.assertTrue(all(entry["video_name"].startswith("chunk_") for entry in expanded))
                self.assertTrue(all(entry["video_path"] != str(tmp_path / "long.mp4") for entry in expanded))
                self.assertIn("Auto-chunking long.mp4: 3 chunks of 60s each", "\n".join(logs.output))
            finally:
                videos.probe_duration = old_probe
                videos.split_video = old_split
                videos.default_chunk_seconds = old_chunk_seconds
                videos.default_output_dir = old_output_dir
                if old_auto is None:
                    os.environ.pop("PIGEONLAB_VIDEO_AUTO_CHUNK_UPLOADS", None)
                else:
                    os.environ["PIGEONLAB_VIDEO_AUTO_CHUNK_UPLOADS"] = old_auto

    def test_install_bat_invokes_py_launcher_venv_through_cmd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "pigeonlab-install"
            fake_bin = Path(tmp) / "fake-bin"
            root.mkdir()
            fake_bin.mkdir()
            shutil.copy(PROJECT_ROOT / "install.ps1", root / "install.ps1")
            shutil.copy(PROJECT_ROOT / "install.bat", root / "install.bat")

            for name in ("git", "node", "ffmpeg", "ollama"):
                (fake_bin / f"{name}.cmd").write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")

            (fake_bin / "py.cmd").write_text(
                textwrap.dedent(
                    r"""
                    @echo off
                    echo %*>>"%~dp0py-args.txt"
                    if "%~1"=="-3.12" if "%~2"=="--version" exit /b 0
                    if "%~1"=="-3.12" if "%~2"=="-m" if "%~3"=="venv" (
                        mkdir "%~4\Scripts" >nul 2>nul
                        type nul > "%~4\Scripts\python.exe"
                        exit /b 0
                    )
                    exit /b 1
                    """
                ).lstrip(),
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["PIGEONLAB_INSTALL_STOP_AFTER_VENV"] = "1"
            result = subprocess.run(
                ["cmd.exe", "/c", "install.bat"],
                cwd=root,
                env=env,
                input="\n",
                capture_output=True,
                text=True,
                timeout=60,
            )
            combined = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, combined)
            self.assertTrue((root / "backend" / "venv" / "Scripts" / "python.exe").is_file())
            args = (fake_bin / "py-args.txt").read_text(encoding="utf-8")
            self.assertIn('"-3.12" "-m" "venv"', args)

    def test_delete_video_removes_dependent_rows(self) -> None:
        import database
        videos = import_videos_with_fakes()

        old_db_path = database.DB_PATH
        old_frame_extractor = videos.FrameExtractor

        class FakeFrameExtractor:
            def cleanup_frames(self, _video_id: int) -> int:
                return 2

        with tempfile.TemporaryDirectory() as tmp:
            database.DB_PATH = Path(tmp) / "pigeonlab.db"
            videos.FrameExtractor = FakeFrameExtractor
            try:
                database.init_db()
                with database.get_db() as conn:
                    conn.execute(
                        "INSERT INTO videos (video_name, source_path, processing_status) VALUES (?, ?, ?)",
                        ("cascade.mp4", "cascade.mp4", "completed"),
                    )
                    video_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.executemany(
                        "INSERT INTO pigeons (pigeon_id) VALUES (?)",
                        [("unknown_1",), ("unknown_2",)],
                    )
                    conn.execute(
                        """INSERT INTO video_assignments
                           (video_id, video_obj_id, pigeon_id, confidence, match_method)
                           VALUES (?, 1, 'unknown_1', 1.0, 'placeholder')""",
                        (video_id,),
                    )
                    assignment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.execute(
                        "INSERT INTO identity_reviews (assignment_id, action) VALUES (?, 'confirm')",
                        (assignment_id,),
                    )
                    conn.execute(
                        """INSERT INTO features
                           (video_id, frame_idx, pigeon_id, centroid_x, centroid_y)
                           VALUES (?, 0, 'unknown_1', 1, 1)""",
                        (video_id,),
                    )
                    conn.execute(
                        """INSERT INTO pairwise
                           (video_id, frame_idx, pigeon_a, pigeon_b, distance_px)
                           VALUES (?, 0, 'unknown_1', 'unknown_2', 5)""",
                        (video_id,),
                    )
                    conn.execute(
                        """INSERT INTO behaviors
                           (video_id, pigeon_id, behavior, start_frame, end_frame)
                           VALUES (?, 'unknown_1', 'standing', 0, 1)""",
                        (video_id,),
                    )
                    conn.execute(
                        """INSERT INTO clip_library
                           (video_id, pigeon_id, start_frame, end_frame)
                           VALUES (?, 'unknown_1', 0, 1)""",
                        (video_id,),
                    )
                    clip_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.execute(
                        "INSERT INTO behavior_labels (clip_id, behavior_class) VALUES (?, 'standing')",
                        (clip_id,),
                    )
                    conn.execute(
                        "INSERT INTO droppings (video_id, frame_idx) VALUES (?, 0)",
                        (video_id,),
                    )
                    dropping_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.execute(
                        "INSERT INTO droppings_reviews (dropping_id, action) VALUES (?, 'accept')",
                        (dropping_id,),
                    )
                    conn.execute(
                        "INSERT INTO qc_flags (video_id, frame_idx, rule_name) VALUES (?, 0, 'count')",
                        (video_id,),
                    )
                    conn.execute(
                        "INSERT INTO review_tasks (task_type, video_id) VALUES ('qc', ?)",
                        (video_id,),
                    )
                    conn.execute(
                        "INSERT INTO ai_observations (video_id, frame_idx, observation_type) VALUES (?, 0, 'behavior')",
                        (video_id,),
                    )
                    conn.execute(
                        "INSERT INTO track_edits (video_id, frame_idx, edit_type) VALUES (?, 0, 'merge')",
                        (video_id,),
                    )
                    conn.commit()

                result = asyncio.run(videos.delete_video(video_id))
                self.assertTrue(result["deleted"])

                with database.get_db() as conn:
                    direct_tables = [
                        "videos",
                        "features",
                        "pairwise",
                        "behaviors",
                        "clip_library",
                        "droppings",
                        "qc_flags",
                        "review_tasks",
                        "ai_observations",
                        "video_assignments",
                        "track_edits",
                    ]
                    for table in direct_tables:
                        count = conn.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE video_id = ?",
                            (video_id,),
                        ).fetchone()[0]
                        self.assertEqual(count, 0, table)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM identity_reviews").fetchone()[0], 0)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM behavior_labels").fetchone()[0], 0)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM droppings_reviews").fetchone()[0], 0)
            finally:
                videos.FrameExtractor = old_frame_extractor
                database.DB_PATH = old_db_path


if __name__ == "__main__":
    unittest.main(verbosity=2)
