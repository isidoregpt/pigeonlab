import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import videos, pigeons, insights, review, training, export, stats
from routers.stats import recent_activity as _activity_handler

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIRS = ["data", "data/videos", "data/clips", "data/models", "data/exports", "data/frames"]


@asynccontextmanager
async def lifespan(app: FastAPI):
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
app.get("/api/activity", tags=["stats"])(_activity_handler)


@app.get("/api/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
