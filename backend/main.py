import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, get_db, DB_PATH
from routers import videos, pigeons, insights, review, training, export, stats, settings
from routers.stats import recent_activity as _activity_handler

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIRS = ["data", "data/videos", "data/clips", "data/models", "data/exports", "data/frames"]

APP_VERSION = "0.1.0"
_start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time
    _start_time = time.time()
    for d in DATA_DIRS:
        (PROJECT_ROOT / d).mkdir(parents=True, exist_ok=True)
    init_db()
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
        "uptime_seconds": uptime_seconds,
    }
