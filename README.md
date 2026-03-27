> ⚠️ This software is free for academic and research use. Commercial use,
> including selling derivative works, is prohibited without a license.
> See [LICENSE](./LICENSE) for details.

# PigeonLab

A full-stack web application for pigeon behavioral tracking from video. Upload videos, track pigeon positions and identities, review QC flags, visualize zone heatmaps and social networks, and train behavior classification models.

## Prerequisites

- **Python 3.10+** with `pip`
- **Node.js 18+** with `npm`

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
python seed_data.py          # optional: populate demo data
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                  # starts on http://localhost:5173
```

### Windows (one-click)

```powershell
.\start.ps1
# or
start.bat
```

## Project Structure

```
pigeonlab/
├── backend/
│   ├── main.py              # FastAPI app, lifespan, health check
│   ├── database.py          # SQLite schema & helpers
│   ├── seed_data.py         # Demo data seeder
│   ├── routers/
│   │   ├── videos.py        # Video CRUD, frames, features, edits
│   │   ├── pigeons.py       # Pigeon CRUD, behaviors, identity
│   │   ├── insights.py      # Heatmaps, behaviors, pairwise, droppings
│   │   ├── review.py        # Identity confirmation, QC flags
│   │   ├── training.py      # Clips, labeling, model training
│   │   ├── export.py        # CSV/PDF export
│   │   └── stats.py         # Dashboard stats, attention items
│   ├── services/
│   │   ├── sam3.py          # SAM3 wrapper (dual install paths)
│   │   ├── video_processor.py  # Processing pipeline orchestrator
│   │   ├── frame_extractor.py  # OpenCV frame extraction
│   │   ├── tracker.py       # Multi-object tracker
│   │   ├── feature_extractor.py  # Spatial features
│   │   └── qc_rules.py      # Automated QC checks
│   └── scripts/
│       ├── download_sam3.py # SAM3 checkpoint downloader
│       └── setup_check.py   # 16-point environment diagnostic
├── frontend/
│   ├── src/
│   │   ├── pages/           # Home, Videos, Pigeons, Insights, Review, Training, LabSetup
│   │   ├── components/      # Layout (Sidebar), UI (cards, modals, badges, toast)
│   │   ├── api/             # Typed API client layer
│   │   ├── hooks/           # usePageTitle
│   │   └── types/           # TypeScript interfaces
│   └── index.html
├── data/                    # Created at startup: videos, clips, models, exports, frames
├── start.bat
└── start.ps1
```

## Tech Stack

- **Backend:** FastAPI, SQLite (sqlite3 + aiosqlite), Python
- **Frontend:** React 19, TypeScript, Vite, TailwindCSS v4, React Router v7, TanStack Query v5, Recharts, lucide-react
