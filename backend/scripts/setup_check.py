"""PigeonLab pre-flight environment check.

Run from the project root:

    python backend/scripts/setup_check.py
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

try:
    from env_loader import load_env_file

    load_env_file(PROJECT_ROOT / ".env")
except Exception:
    pass

passes = 0
failures = 0
failed_items: list[str] = []


def check(label: str, passed: bool, msg: str, fix: str = "") -> None:
    """Print a single check result and update counters."""
    global passes, failures
    if passed:
        print(f"  [OK]   {label}: {msg}")
        passes += 1
    else:
        print(f"  [FAIL] {label}: {msg}")
        failures += 1
        failed_items.append(f"{label}: {fix}" if fix else f"{label}: {msg}")


def _run_command(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = (result.stdout or result.stderr).strip()
    return result.returncode == 0, output


def _get_json(url: str, timeout: int = 3) -> tuple[bool, dict | str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
        return True, json.loads(body)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return False, str(exc)


def _round_gb(value_bytes: int | float | None) -> float | None:
    if value_bytes is None:
        return None
    return round(float(value_bytes) / (1024 ** 3), 2)


def _env_summary() -> dict[str, str]:
    keys = [
        "PIGEONLAB_HARDWARE_PROFILE",
        "PIGEONLAB_SAM3_VERSION",
        "PIGEONLAB_SAM3_MODEL_DIR",
        "PIGEONLAB_SAM3_MAX_OBJECTS",
        "PIGEONLAB_SAM3_MULTIPLEX_COUNT",
        "PIGEONLAB_SAM3_COMPILE",
        "PIGEONLAB_SAM3_OFFLOAD_VIDEO_TO_CPU",
        "PIGEONLAB_SAM3_FALLBACK_PER_FRAME",
        "PIGEONLAB_VIDEO_CHUNK_SECONDS",
        "PIGEONLAB_VIDEO_AUTO_CHUNK_UPLOADS",
        "PIGEONLAB_GEMMA_REVIEW_MODE",
        "PIGEONLAB_GEMMA_MODEL",
        "PYTORCH_CUDA_ALLOC_CONF",
    ]
    return {key: os.getenv(key, "") for key in keys if os.getenv(key) is not None}


def _torch_snapshot() -> dict:
    snapshot = {
        "torch_version": None,
        "cuda_version": None,
        "gpu_name": None,
        "vram_total_gb": None,
        "vram_used_gb": None,
        "vram_free_gb": None,
    }
    try:
        import torch
    except ImportError:
        return snapshot

    snapshot["torch_version"] = torch.__version__
    snapshot["cuda_version"] = torch.version.cuda
    if not torch.cuda.is_available():
        return snapshot

    try:
        free_bytes, total_bytes = torch.cuda.mem_get_info(0)
        used_bytes = total_bytes - free_bytes
    except Exception:
        props = torch.cuda.get_device_properties(0)
        total_bytes = int(props.total_memory)
        used_bytes = torch.cuda.memory_allocated(0)
        free_bytes = max(0, total_bytes - used_bytes)

    snapshot.update(
        {
            "gpu_name": torch.cuda.get_device_name(0),
            "vram_total_gb": _round_gb(total_bytes),
            "vram_used_gb": _round_gb(used_bytes),
            "vram_free_gb": _round_gb(free_bytes),
        }
    )
    return snapshot


def _database_snapshot() -> dict:
    snapshot = {
        "last_processing_error": None,
        "active_jobs": 0,
    }
    try:
        from database import get_db

        with get_db() as conn:
            row = conn.execute(
                """SELECT video_id, processing_error, processed_at
                   FROM videos
                   WHERE processing_status = 'failed'
                     AND processing_error IS NOT NULL
                   ORDER BY COALESCE(processed_at, '') DESC, video_id DESC
                   LIMIT 1"""
            ).fetchone()
            if row:
                snapshot["last_processing_error"] = {
                    "video_id": row["video_id"],
                    "error": row["processing_error"],
                    "timestamp": row["processed_at"],
                }
            active = conn.execute(
                "SELECT COUNT(*) AS cnt FROM videos WHERE processing_status = 'processing'"
            ).fetchone()
            snapshot["active_jobs"] = active["cnt"] if active else 0
    except Exception as exc:
        snapshot["database_error"] = str(exc)
    return snapshot


def collect_runtime_diagnostics(load_model: bool = False) -> dict:
    """Collect the structured diagnostics used by /api/health/full."""
    try:
        from services.ffmpeg_ingest import get_ffmpeg_status
    except Exception:
        get_ffmpeg_status = None  # type: ignore[assignment]
    try:
        from services.sam3 import get_sam3_status
    except Exception:
        get_sam3_status = None  # type: ignore[assignment]

    torch_info = _torch_snapshot()
    sam3_status = (
        get_sam3_status(load_model=load_model)
        if get_sam3_status is not None
        else {"loaded": False, "version": os.getenv("PIGEONLAB_SAM3_VERSION", "sam3.1"), "backend": None}
    )

    ffmpeg_status = get_ffmpeg_status() if get_ffmpeg_status is not None else {"available": False}

    gemma_model = os.getenv("PIGEONLAB_GEMMA_MODEL", "gemma4:e4b")
    gemma_base_url = os.getenv("PIGEONLAB_GEMMA_BASE_URL", "http://localhost:11434").rstrip("/")
    ollama_ok, ollama_data = _get_json(f"{gemma_base_url}/api/tags")
    installed_models: list[str] = []
    if ollama_ok and isinstance(ollama_data, dict):
        installed_models = sorted(
            item.get("name", "")
            for item in ollama_data.get("models", [])
            if item.get("name")
        )

    db_info = _database_snapshot()
    return {
        "model_loaded": bool(sam3_status.get("loaded")),
        "sam3_version": sam3_status.get("version"),
        "sam3_backend": sam3_status.get("backend"),
        "gpu_name": torch_info["gpu_name"] or sam3_status.get("gpu_name"),
        "vram_total_gb": torch_info["vram_total_gb"],
        "vram_used_gb": torch_info["vram_used_gb"],
        "vram_free_gb": torch_info["vram_free_gb"],
        "cuda_version": torch_info["cuda_version"] or sam3_status.get("cuda_version"),
        "torch_version": torch_info["torch_version"] or sam3_status.get("torch_version"),
        "python_version": platform.python_version(),
        "hardware_profile": os.getenv("PIGEONLAB_HARDWARE_PROFILE", "default"),
        "last_processing_error": db_info.get("last_processing_error"),
        "active_jobs": db_info.get("active_jobs", 0),
        "env_summary": _env_summary(),
        "ffmpeg_available": bool(ffmpeg_status.get("available")),
        "ffmpeg_path": ffmpeg_status.get("ffmpeg_path"),
        "ollama_reachable": bool(ollama_ok),
        "gemma_model_present": gemma_model in installed_models,
        "gemma_model": gemma_model,
        "gemma_installed_models": installed_models,
        "sam3_ready": sam3_status.get("ready", False),
        "sam3_errors": sam3_status.get("errors", []),
        "sam3_warnings": sam3_status.get("warnings", []),
    }


def run_optional_smoke_check() -> None:
    """Run the smoke test when explicitly requested by environment."""
    if os.getenv("PIGEONLAB_RUN_SMOKE_TEST", "").strip().lower() not in {"1", "true", "yes", "on"}:
        print("  [INFO] Smoke test: skipped (set PIGEONLAB_RUN_SMOKE_TEST=1 to run)")
        return
    try:
        result = subprocess.run(
            [sys.executable, "-m", "backend.tests.smoke_test"],
            capture_output=True,
            text=True,
            timeout=90,
        )
        ok = result.returncode == 0
        output = (result.stdout or result.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        ok = False
        output = str(exc)
    first_line = output.splitlines()[0] if output else ""
    check(
        "Smoke test",
        ok,
        first_line or "completed",
        "Run python -m backend.tests.smoke_test from the project root.",
    )


def run_checks() -> None:
    """Run environment checks."""
    print("=" * 60)
    print("  PigeonLab Environment Check")
    print("=" * 60)
    print()

    version = sys.version_info
    check(
        "Python >= 3.10",
        version >= (3, 10),
        f"Python {version.major}.{version.minor}.{version.micro}",
        "Install Python 3.10+ for the app, Python 3.12+ for SAM3.1.",
    )
    check(
        "Python >= 3.12 for SAM3.1",
        version >= (3, 12),
        f"Python {version.major}.{version.minor}.{version.micro}",
        "Install Python 3.12+ before using SAM3.1.",
    )
    if os.name == "nt":
        check(
            "Python 3.12 active on Windows",
            version.major == 3 and version.minor == 12,
            f"Python {version.major}.{version.minor}.{version.micro}",
            "Run install.bat so the SAM3.1 venv is created with Python 3.12, not PATH Python.",
        )
    check(
        "Hardware profile",
        True,
        os.getenv("PIGEONLAB_HARDWARE_PROFILE", "default"),
    )

    ok, output = _run_command(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
    check(
        "NVIDIA driver",
        ok,
        output if ok else "nvidia-smi not found",
        "Install or update the NVIDIA RTX A6000 driver.",
    )

    try:
        import torch

        check("PyTorch installed", True, f"torch {torch.__version__}")
        parts = torch.__version__.split(".")
        major = int(parts[0])
        minor = int(parts[1].split("+")[0].split("a")[0].split("b")[0].split("rc")[0])
        check(
            "PyTorch >= 2.7",
            (major, minor) >= (2, 7),
            f"torch {torch.__version__}",
            "Install PyTorch 2.7+ with CUDA 12.6 support.",
        )
        cuda = torch.cuda.is_available()
        check("CUDA available", cuda, "Yes" if cuda else "No", "Install NVIDIA drivers and CUDA 12.6.")
        if cuda:
            check("GPU detected", True, torch.cuda.get_device_name(0))
        else:
            check("GPU detected", False, "No GPU found", "Install CUDA-compatible GPU drivers.")
    except ImportError:
        check("PyTorch installed", False, "Not installed", "pip install torch torchvision")
        check("PyTorch >= 2.7", False, "Not installed", "pip install torch torchvision")
        check("CUDA available", False, "PyTorch not installed")
        check("GPU detected", False, "PyTorch not installed")

    try:
        from sam3.model_builder import build_sam3_predictor  # noqa: F401

        check("SAM3.1 native package", True, "build_sam3_predictor found")
    except ImportError as exc:
        check(
            "SAM3.1 native package",
            False,
            str(exc),
            "pip install git+https://github.com/facebookresearch/sam3.git && pip install pycocotools",
        )

    try:
        import transformers
        from transformers import Sam3Model  # noqa: F401

        check("Transformers SAM3", True, f"transformers {transformers.__version__}")
    except ImportError:
        check("Transformers SAM3", False, "Not available", "pip install transformers accelerate")

    for package, import_name, fix in [
        ("numpy", "numpy", "pip install numpy"),
        ("pillow", "PIL", "pip install pillow"),
        ("aiosqlite", "aiosqlite", "pip install aiosqlite>=0.19.0"),
        ("opencv-python", "cv2", "pip install opencv-python>=4.8.0"),
        ("huggingface_hub", "huggingface_hub", "pip install huggingface_hub>=0.20.0"),
        ("httpx", "httpx", "pip install httpx"),
        ("einops", "einops", "pip install einops"),
        ("pycocotools", "pycocotools", "pip install pycocotools"),
        ("psutil", "psutil", "pip install psutil"),
    ]:
        try:
            module = __import__(import_name)
            version_label = getattr(module, "__version__", "OK")
            check(package, True, str(version_label))
        except ImportError:
            check(package, False, "Not installed", fix)

    if os.name == "nt":
        try:
            import triton

            check("Triton for Windows", True, f"triton {triton.__version__}")
        except ImportError:
            check(
                "Triton for Windows",
                False,
                "Not installed",
                "pip install triton-windows",
            )

    try:
        import cv2
        import numpy

        numpy_major = int(str(numpy.__version__).split(".", 1)[0])
        cv2_parts = str(cv2.__version__).split(".")
        cv2_major_minor = (int(cv2_parts[0]), int(cv2_parts[1]))
        check(
            "SAM3 NumPy/OpenCV ABI",
            numpy_major < 2 and cv2_major_minor < (4, 11),
            f"numpy {numpy.__version__}, opencv {cv2.__version__}",
            'pip install "numpy>=1.26,<2" "opencv-python>=4.8,<4.11"',
        )
    except Exception as exc:
        check("SAM3 NumPy/OpenCV ABI", False, str(exc), "Reinstall backend requirements.")

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    check(
        "FFmpeg available",
        ffmpeg_path is not None,
        ffmpeg_path or "Not found",
        "Install FFmpeg and add it to PATH for folder ingestion.",
    )
    check(
        "FFprobe available",
        ffprobe_path is not None,
        ffprobe_path or "Not found",
        "Install FFmpeg and add it to PATH for duration checks.",
    )

    gemma_mode = os.getenv("PIGEONLAB_GEMMA_REVIEW_MODE", "off").lower()
    gemma_model = os.getenv("PIGEONLAB_GEMMA_MODEL", "gemma4:e4b")
    gemma_base_url = os.getenv("PIGEONLAB_GEMMA_BASE_URL", "http://localhost:11434").rstrip("/")
    ok, ollama_data = _get_json(f"{gemma_base_url}/api/tags")
    ollama_optional = gemma_mode == "off"
    check(
        "Ollama reachable",
        ok or ollama_optional,
        "Optional; Gemma reviewer is off" if not ok and ollama_optional else gemma_base_url,
        "Start Ollama or set PIGEONLAB_GEMMA_REVIEW_MODE=off.",
    )
    if ok and isinstance(ollama_data, dict):
        models = sorted(
            item.get("name", "")
            for item in ollama_data.get("models", [])
            if item.get("name")
        )
        model_found = gemma_model in models
        installed_gemma = ", ".join(name for name in models if name.startswith("gemma4:")) or "none"
        check(
            "Gemma Ollama model",
            model_found or ollama_optional,
            gemma_model if model_found else f"Optional; Gemma reviewer is off; installed Gemma 4: {installed_gemma}",
            f"Run: ollama pull {gemma_model}",
        )
    else:
        check(
            "Gemma Ollama model",
            ollama_optional,
            "Optional; Gemma reviewer is off" if ollama_optional else "Ollama not reachable",
            f"Run: ollama pull {gemma_model}",
        )

    try:
        from services.sam3 import get_sam3_status

        sam3_status = get_sam3_status(load_model=False)
        check(
            "SAM3 app readiness",
            sam3_status["ready"],
            f"{sam3_status['version']} via {sam3_status['backend'] or 'none'}",
            "; ".join(sam3_status["errors"]),
        )
        for warning in sam3_status["warnings"]:
            print(f"  [WARN] SAM3: {warning}")
    except Exception as exc:
        check("SAM3 app readiness", False, str(exc), "Check backend/services/sam3.py imports.")

    ok, output = _run_command(["node", "--version"])
    check("Node.js available", ok, output if ok else "Not found", "Install Node.js 18+.")

    node_modules = PROJECT_ROOT / "frontend" / "node_modules"
    check(
        "frontend/node_modules",
        node_modules.exists(),
        "OK" if node_modules.exists() else "Not found",
        "cd frontend && npm install",
    )

    model_dir = PROJECT_ROOT / "data" / "models" / "sam3.1"
    checkpoint_files = list(model_dir.glob("*.pt")) if model_dir.exists() else []
    check(
        "SAM3.1 model files",
        len(checkpoint_files) > 0,
        f"{len(checkpoint_files)} checkpoint(s) found" if checkpoint_files else "Not found",
        "python backend/scripts/download_sam3.py --version sam3.1",
    )

    db = PROJECT_ROOT / "data" / "pigeonlab.db"
    check(
        "Database",
        db.exists(),
        "OK" if db.exists() else "Not found",
        "Run the backend once to auto-create the database.",
    )
    run_optional_smoke_check()

    print()
    print("-" * 60)
    total = passes + failures
    print(f"  Results: {passes}/{total} checks passed")
    print()

    if failures == 0:
        print("  PigeonLab is fully ready. Run start.bat to launch.")
    else:
        print(f"  {failures} item(s) need attention before PigeonLab will work.")
        print()
        print("  NEXT STEPS:")
        for item in failed_items:
            print(f"    - {item}")
    print()


if __name__ == "__main__":
    run_checks()
