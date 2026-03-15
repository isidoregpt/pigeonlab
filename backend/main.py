from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import videos, pigeons, insights, review, training, export, stats

app = FastAPI(title="PigeonLab API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
