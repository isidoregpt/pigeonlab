"""Application logging setup for PigeonLab."""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import platform
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "data" / "logs"
_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """Compact JSONL formatter for LLM-friendly troubleshooting logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.threadName,
        }
        if record.exc_info:
            payload["exception"] = "".join(traceback.format_exception(*record.exc_info))
        if hasattr(record, "request_id"):
            payload["request_id"] = getattr(record, "request_id")
        return json.dumps(payload, ensure_ascii=True, default=str)


def configure_logging() -> Path:
    """Configure console, text-file, and JSONL logs."""
    global _CONFIGURED
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "pigeonlab.log"
    json_file = LOG_DIR / "pigeonlab.jsonl"

    if _CONFIGURED:
        return log_file

    level_name = os.getenv("PIGEONLAB_LOG_LEVEL", "DEBUG").upper()
    level = getattr(logging, level_name, logging.DEBUG)
    max_bytes = int(os.getenv("PIGEONLAB_LOG_MAX_BYTES", "52428800"))
    backups = int(os.getenv("PIGEONLAB_LOG_BACKUPS", "10"))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setLevel(os.getenv("PIGEONLAB_CONSOLE_LOG_LEVEL", "INFO").upper())
    console.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    root.addHandler(console)

    text_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backups,
        encoding="utf-8",
    )
    text_handler.setLevel(level)
    text_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(process)d:%(threadName)s] "
            "%(name)s:%(lineno)d %(message)s"
        )
    )
    root.addHandler(text_handler)

    if os.getenv("PIGEONLAB_LOG_JSON", "1").lower() in {"1", "true", "yes", "on"}:
        json_handler = logging.handlers.RotatingFileHandler(
            json_file,
            maxBytes=max_bytes,
            backupCount=backups,
            encoding="utf-8",
        )
        json_handler.setLevel(level)
        json_handler.setFormatter(JsonFormatter())
        root.addHandler(json_handler)

    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"]:
        logging.getLogger(logger_name).setLevel(level)

    logging.captureWarnings(True)
    _CONFIGURED = True
    logging.getLogger(__name__).info("Logging initialized at %s", log_file)
    logging.getLogger("pigeonlab.startup").info(
        "Pre-torch PYTORCH_CUDA_ALLOC_CONF=%s torch_imported=%s",
        os.environ.get("PYTORCH_CUDA_ALLOC_CONF", "<not set>"),
        "torch" in sys.modules,
    )
    log_system_snapshot()
    return log_file


def log_system_snapshot() -> None:
    """Log enough machine context to make future support much easier."""
    logger = logging.getLogger("pigeonlab.system")
    disk = shutil.disk_usage(PROJECT_ROOT)
    snapshot: dict[str, Any] = {
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "project_root": str(PROJECT_ROOT),
        "disk_total_gb": round(disk.total / (1024**3), 2),
        "disk_free_gb": round(disk.free / (1024**3), 2),
        "hardware_profile": os.getenv("PIGEONLAB_HARDWARE_PROFILE", "default"),
        "ffmpeg_threads": os.getenv("PIGEONLAB_FFMPEG_THREADS"),
        "opencv_threads": os.getenv("PIGEONLAB_OPENCV_THREADS"),
        "sam3_compile": os.getenv("PIGEONLAB_SAM3_COMPILE"),
        "sam3_multiplex_count": os.getenv("PIGEONLAB_SAM3_MULTIPLEX_COUNT"),
        "gemma_model": os.getenv("PIGEONLAB_GEMMA_MODEL"),
    }
    try:
        import torch

        snapshot["torch"] = torch.__version__
        snapshot["cuda_available"] = torch.cuda.is_available()
        snapshot["cuda_version"] = torch.version.cuda
        if torch.cuda.is_available():
            snapshot["gpu"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            snapshot["gpu_memory_gb"] = round(props.total_memory / (1024**3), 2)
    except Exception as exc:
        snapshot["torch_probe_error"] = str(exc)

    try:
        import psutil

        mem = psutil.virtual_memory()
        snapshot["system_ram_gb"] = round(mem.total / (1024**3), 2)
    except Exception:
        pass

    logger.info("System snapshot: %s", json.dumps(snapshot, ensure_ascii=True, sort_keys=True))
