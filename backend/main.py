import os
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from env_loader import load_env_file

load_env_file()

from logging_config import configure_logging

configure_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, get_db, DB_PATH
from routers import videos, pigeons, insights, review, training, export, stats, settings
from routers.stats import recent_activity as _activity_handler
from scripts.setup_check import collect_runtime_diagnostics
from services.ffmpeg_ingest import get_ffmpeg_status
from services.sam3 import get_sam3_status

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIRS = [
    "data",
    "data/videos",
    "data/videos/inbox",
    "data/videos/output",
    "data/videos/archive",
    "data/clips",
    "data/models",
    "data/exports",
    "data/frames",
]

APP_VERSION = "0.1.0"
_start_time: float = 0.0
logger = logging.getLogger("pigeonlab.api")
if os.getenv("PIGEONLAB_STRIPPED_CUDA_ALLOC_CONF"):
    logger.info(
        "expandable_segments stripped from PYTORCH_CUDA_ALLOC_CONF - not supported on Windows"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time
    _start_time = time.time()
    for d in DATA_DIRS:
        (PROJECT_ROOT / d).mkdir(parents=True, exist_ok=True)
    init_db()
    for warning in get_ffmpeg_status().get("warnings", []):
        logger.warning(warning)
    sam3_status = get_sam3_status(load_model=False)
    active_patches = [
        name for name, active in sam3_status.get("runtime_patches", {}).items() if active
    ]
    if active_patches:
        logger.info("SAM3 runtime patches active: %s", ", ".join(active_patches))
    yield


app = FastAPI(title="PigeonLab API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(pigeons.router, prefix="/api/pigeons", tags=["pigeons"])
app.include_router(insights.router, prefix="/api/insights", tags=["insights"])
app.include_router(review.router, prefix="/api/review", tags=["review"])
app.include_router(training.router, prefix="/api/training", tags=["training"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.get("/api/activity", tags=["stats"])(_activity_handler)


@app.middleware("http")
async def request_logging_middleware(request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.perf_counter()
    logger.debug(
        "request.start id=%s method=%s path=%s client=%s",
        request_id,
        request.method,
        request.url.path,
        request.client.host if request.client else None,
    )
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request.error id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        raise
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["x-request-id"] = request_id
    logger.info(
        "request.end id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/api/health", tags=["health"])
async def health_check():
    db_ok = False
    db_size_bytes = None
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
            db_ok = True
        if DB_PATH.exists():
            db_size_bytes = DB_PATH.stat().st_size
    except Exception:
        pass

    uptime_seconds = round(time.time() - _start_time, 1) if _start_time else 0

    return {
        "status": "ok" if db_ok else "degraded",
        "version": APP_VERSION,
        "database": {
            "status": "connected" if db_ok else "error",
            "size_bytes": db_size_bytes,
        },
        "sam3": get_sam3_status(load_model=False),
        "uptime_seconds": uptime_seconds,
    }


@app.get("/api/health/full", tags=["health"])
async def full_health_check():
    """Return support-ticket diagnostics without forcing model load."""
    return collect_runtime_diagnostics(load_model=False)
