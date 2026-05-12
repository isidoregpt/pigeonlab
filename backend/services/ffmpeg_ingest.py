"""FFmpeg-backed folder ingestion for long video batches."""

from __future__ import annotations

import os
import re
import logging
import shutil
import subprocess
import time
from math import ceil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
logger = logging.getLogger(__name__)
UNSTABLE_FFMPEG_LOCATIONS = {"downloads", "desktop", "temp"}


def _configured_path(env_name: str, default_relative: str) -> Path:
    raw = os.getenv(env_name)
    path = Path(raw).expanduser() if raw else PROJECT_ROOT / default_relative
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def default_input_dir() -> Path:
    return _configured_path("PIGEONLAB_VIDEO_INPUT_DIR", "data/videos/inbox")


def default_output_dir() -> Path:
    return _configured_path("PIGEONLAB_VIDEO_OUTPUT_DIR", "data/videos/output")


def default_archive_dir() -> Path:
    return _configured_path("PIGEONLAB_VIDEO_ARCHIVE_DIR", "data/videos/archive")


def default_chunk_seconds() -> int:
    raw = os.getenv("PIGEONLAB_VIDEO_CHUNK_SECONDS", "60")
    try:
        return max(30, min(3600, int(raw)))
    except ValueError:
        return 60


def default_ffmpeg_threads() -> int:
    raw = os.getenv("PIGEONLAB_FFMPEG_THREADS", "32")
    try:
        return max(1, min(64, int(raw)))
    except ValueError:
        return 32


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_dir(value: str | None, fallback: Path) -> Path:
    path = Path(value).expanduser() if value else fallback
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _safe_stem(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("._")
    return stem or "video"


def _unique_dir(parent: Path, base_name: str) -> Path:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    candidate = parent / f"{base_name}_{timestamp}"
    if not candidate.exists():
        return candidate
    for idx in range(1, 1000):
        candidate = parent / f"{base_name}_{timestamp}_{idx:03d}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not create a unique output folder under {parent}")


def _unique_file(parent: Path, name: str) -> Path:
    candidate = parent / name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for idx in range(1, 1000):
        next_candidate = parent / f"{stem}_{idx:03d}{suffix}"
        if not next_candidate.exists():
            return next_candidate
    raise RuntimeError(f"Could not create a unique archive filename under {parent}")


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _ffmpeg_location_warnings(path_value: str | None) -> list[str]:
    if not path_value:
        return []
    path = Path(path_value)
    parts = {part.lower() for part in path.parts}
    unstable = bool(parts & UNSTABLE_FFMPEG_LOCATIONS)
    if {"appdata", "local", "temp"}.issubset(parts):
        unstable = True
    if not unstable:
        return []
    return [
        "FFmpeg detected at "
        f"{path_value}. This location is unstable - move FFmpeg to a permanent "
        "location such as C:\\ffmpeg\\bin\\ and update PATH to avoid breakage."
    ]


def get_ffmpeg_status() -> dict:
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    errors: list[str] = []
    warnings: list[str] = []
    if not ffmpeg_path:
        errors.append("ffmpeg was not found on PATH.")
    if not ffprobe_path:
        errors.append("ffprobe was not found on PATH.")
    warnings.extend(_ffmpeg_location_warnings(ffmpeg_path))
    warnings.extend(_ffmpeg_location_warnings(ffprobe_path))

    return {
        "available": not errors,
        "ffmpeg_path": ffmpeg_path,
        "ffprobe_path": ffprobe_path,
        "default_input_dir": str(default_input_dir()),
        "default_output_dir": str(default_output_dir()),
        "default_archive_dir": str(default_archive_dir()),
        "chunk_seconds": default_chunk_seconds(),
        "threads": default_ffmpeg_threads(),
        "nvenc_fallback": _env_bool("PIGEONLAB_FFMPEG_USE_NVENC", True),
        "errors": errors,
        "warnings": warnings,
    }


def probe_duration(video_path: Path) -> float | None:
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        return None

    result = _run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
    )
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def _segment_with_copy(ffmpeg_path: str, video_path: Path, output_pattern: Path, chunk_seconds: int):
    return _run(
        [
            ffmpeg_path,
            "-hide_banner",
            "-y",
            "-threads",
            str(default_ffmpeg_threads()),
            "-i",
            str(video_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c",
            "copy",
            "-f",
            "segment",
            "-segment_time",
            str(chunk_seconds),
            "-reset_timestamps",
            "1",
            str(output_pattern),
        ]
    )


def _segment_with_encode(ffmpeg_path: str, video_path: Path, output_pattern: Path, chunk_seconds: int):
    return _run(
        [
            ffmpeg_path,
            "-hide_banner",
            "-y",
            "-threads",
            str(default_ffmpeg_threads()),
            "-i",
            str(video_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-f",
            "segment",
            "-segment_time",
            str(chunk_seconds),
            "-reset_timestamps",
            "1",
            str(output_pattern),
        ]
    )


def _segment_with_nvenc(ffmpeg_path: str, video_path: Path, output_pattern: Path, chunk_seconds: int):
    return _run(
        [
            ffmpeg_path,
            "-hide_banner",
            "-y",
            "-threads",
            str(default_ffmpeg_threads()),
            "-i",
            str(video_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p4",
            "-cq",
            "22",
            "-c:a",
            "aac",
            "-f",
            "segment",
            "-segment_time",
            str(chunk_seconds),
            "-reset_timestamps",
            "1",
            str(output_pattern),
        ]
    )


def _copy_chunks_too_coarse(
    duration_seconds: float | None,
    chunk_seconds: int,
    chunk_count: int,
) -> bool:
    if duration_seconds is None or duration_seconds <= chunk_seconds:
        return False
    expected_chunks = max(1, ceil(duration_seconds / chunk_seconds))
    minimum_reasonable_chunks = max(2, expected_chunks // 2)
    return chunk_count < minimum_reasonable_chunks


def split_video(video_path: Path, output_dir: Path, chunk_seconds: int) -> dict:
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg was not found on PATH.")

    video_path = video_path.resolve()
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if video_path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError(f"Unsupported video format: {video_path.name}")

    chunk_seconds = max(30, min(3600, int(chunk_seconds)))
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_stem = _safe_stem(video_path)
    target_dir = _unique_dir(output_dir, safe_stem)
    target_dir.mkdir(parents=True, exist_ok=False)

    suffix = video_path.suffix.lower() if video_path.suffix else ".mp4"
    copy_pattern = target_dir / f"{safe_stem}_part%03d{suffix}"
    duration_seconds = probe_duration(video_path)

    result = _segment_with_copy(ffmpeg_path, video_path, copy_pattern, chunk_seconds)
    chunks = sorted(str(path.resolve()) for path in target_dir.iterdir() if path.is_file())
    used_fallback = False

    if (
        result.returncode != 0
        or not chunks
        or _copy_chunks_too_coarse(duration_seconds, chunk_seconds, len(chunks))
    ):
        for stale_file in target_dir.iterdir():
            if stale_file.is_file():
                stale_file.unlink()
        encode_pattern = target_dir / f"{safe_stem}_part%03d.mp4"
        if _env_bool("PIGEONLAB_FFMPEG_USE_NVENC", True):
            result = _segment_with_nvenc(ffmpeg_path, video_path, encode_pattern, chunk_seconds)
            if result.returncode != 0:
                logger.warning(
                    "NVENC segmentation failed for %s; falling back to CPU x264. stderr=%s",
                    video_path,
                    (result.stderr or result.stdout or "")[-1000:],
                )
                result = _segment_with_encode(ffmpeg_path, video_path, encode_pattern, chunk_seconds)
        else:
            result = _segment_with_encode(ffmpeg_path, video_path, encode_pattern, chunk_seconds)
        chunks = sorted(str(path.resolve()) for path in target_dir.iterdir() if path.is_file())
        used_fallback = True

    if result.returncode != 0 or not chunks:
        stderr = (result.stderr or result.stdout or "FFmpeg did not create any chunks.").strip()
        raise RuntimeError(stderr[-2000:])

    return {
        "source_path": str(video_path),
        "source_name": video_path.name,
        "source_stem": video_path.stem,
        "duration_seconds": duration_seconds,
        "chunk_seconds": chunk_seconds,
        "output_dir": str(target_dir.resolve()),
        "chunks": chunks,
        "chunk_count": len(chunks),
        "used_encode_fallback": used_fallback,
        "ffmpeg_threads": default_ffmpeg_threads(),
    }


def ingest_folder(
    input_dir: str | None = None,
    output_dir: str | None = None,
    archive_dir: str | None = None,
    chunk_seconds: int | None = None,
    archive_originals: bool = False,
    limit: int | None = None,
) -> dict:
    status = get_ffmpeg_status()
    if not status["available"]:
        raise RuntimeError(" ".join(status["errors"]))

    input_path = _resolve_dir(input_dir, default_input_dir())
    output_path = _resolve_dir(output_dir, default_output_dir())
    archive_path = _resolve_dir(archive_dir, default_archive_dir())
    seconds = chunk_seconds if chunk_seconds is not None else default_chunk_seconds()
    seconds = max(30, min(3600, int(seconds)))

    input_path.mkdir(parents=True, exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)
    if archive_originals:
        archive_path.mkdir(parents=True, exist_ok=True)

    candidates = sorted(
        path
        for path in input_path.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )
    if limit is not None:
        candidates = candidates[: max(0, int(limit))]

    results: list[dict] = []
    errors: list[dict] = []
    archived: list[dict] = []

    for video_path in candidates:
        try:
            split_result = split_video(video_path, output_path, seconds)
            results.append(split_result)
            if archive_originals:
                destination = _unique_file(archive_path, video_path.name)
                shutil.move(str(video_path), str(destination))
                archived.append(
                    {
                        "source_path": split_result["source_path"],
                        "archive_path": str(destination.resolve()),
                    }
                )
        except Exception as exc:
            errors.append({"source_path": str(video_path.resolve()), "error": str(exc)})

    return {
        "input_dir": str(input_path),
        "output_dir": str(output_path),
        "archive_dir": str(archive_path),
        "chunk_seconds": seconds,
        "videos_found": len(candidates),
        "videos_imported": len(results),
        "chunks_created": sum(item["chunk_count"] for item in results),
        "videos": results,
        "archived": archived,
        "errors": errors,
    }
