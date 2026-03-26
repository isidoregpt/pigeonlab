# PigeonLab Blueprint

## Error Catalog

### BUG-001 — Export URL bypasses Vite dev proxy
**Status:** RESOLVED
Export downloads used `window.open()` which bypassed the Vite dev proxy, causing 404s in development. Fixed by using a temporary `<a>` element click with a relative URL, which correctly routes through the proxy.

### BUG-002 — Missing video features endpoint
**Status:** RESOLVED
The `/api/videos/{video_id}/frame/{frame_num}/features` endpoint now exists in `backend/routers/videos.py` and returns per-pigeon feature data for the requested frame.

### BUG-003 — Missing video track-edits endpoint
**Status:** RESOLVED
The `/api/videos/{video_id}/track-edits` endpoint now exists in `backend/routers/videos.py` and returns the edit history for a given video.

### BUG-004 — Review queue links to video_id=0
**Status:** RESOLVED
The review queue now uses `getNextVideoForIdentityReview()` to fetch the actual next video needing review. VideoCard review buttons link to `/review?type=identity&video_id={actual_id}`.

### INC-004 — Attention count doesn't include behaviors
**Status:** RESOLVED
The `/api/review/attention/count` endpoint now includes pending behavior reviews in its total, matching the sidebar badge and TopBar notification count.

---

## Section 3 — File Map

### Backend

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app entry point, mounts all routers under `/api` |
| `backend/database.py` | SQLite schema, `init_db()`, `get_db()` context manager, `get_connection()` |
| `backend/utils.py` | Shared utilities (`get_default_reviewer()`) |
| `backend/seed_data.py` | Sample data generator for development |
| `backend/routers/videos.py` | Video CRUD, processing, frames, features, track edits |
| `backend/routers/review.py` | Identity review, QC flags, behaviors, droppings, track corrections |
| `backend/routers/pigeons.py` | Pigeon registry and profile endpoints |
| `backend/routers/insights.py` | Stats, charts, heatmaps, social map, exports |
| `backend/routers/training.py` | Clip library, behavior labeling, model training |
| `backend/routers/settings.py` | System info, zone list, database reset/seed |

### Frontend

| File | Purpose |
|------|---------|
| `frontend/src/App.tsx` | React router setup, route definitions |
| `frontend/src/api/client.ts` | API fetch wrappers (`get`, `post`, `put`, `del`, `apiFetch`) |
| `frontend/src/api/review.ts` | Review API functions |
| `frontend/src/api/settings.ts` | Settings API functions (`getZones`, `getSystemInfo`, `resetDatabase`, `seedDatabase`) |
| `frontend/src/utils/formatTime.ts` | Time helpers (`formatRelativeTime`, `formatDateTime`, `formatDuration`) |
| `frontend/src/components/layout/Layout.tsx` | Shell layout with sidebar, top bar, skip link, keyboard shortcuts |
| `frontend/src/components/layout/TopBar.tsx` | Top bar with title, notification bell, help button |
| `frontend/src/components/layout/Sidebar.tsx` | Navigation sidebar with attention dot |
| `frontend/src/components/ui/ConfirmDialog.tsx` | Reusable confirmation modal with danger/warning/default variants |
| `frontend/src/components/ui/HeatmapCanvas.tsx` | Canvas-based heatmap renderer for zone and droppings views |
| `frontend/src/components/ui/SectionError.tsx` | Inline error display with retry button for per-section failures |
| `frontend/src/components/ui/KeyboardShortcutsModal.tsx` | Keyboard shortcuts help modal |
| `frontend/src/pages/Home.tsx` | Dashboard with per-section error handling |
| `frontend/src/pages/Videos.tsx` | Video list with filters and pagination |
| `frontend/src/pages/VideoDetail.tsx` | Frame viewer, pigeon cards, QC flags, deep linking |
| `frontend/src/pages/Pigeons.tsx` | Pigeon registry list |
| `frontend/src/pages/PigeonProfile.tsx` | Individual pigeon stats and behavior chart |
| `frontend/src/pages/Review.tsx` | Review queue (identity, QC, behavior, droppings) with batch ops |
| `frontend/src/pages/Insights.tsx` | Charts, heatmaps, social map, exports |
| `frontend/src/pages/Training.tsx` | Clip labeling and model training |
| `frontend/src/pages/LabSetup.tsx` | Settings page with danger zone |

---

## Section 5 — API Endpoint Reference

### Videos Router (`/api/videos`)

| Method | Path | Params | Returns | Description |
|--------|------|--------|---------|-------------|
| GET | `/sessions` | — | `string[]` | List of distinct session IDs across all videos |
| GET | `/` | `page`, `per_page`, `session_id`, `status` | Paginated video list with `pigeon_count` | List videos with optional filters |
| POST | `/process` | Body: `video_paths`, `camera_assignments`, `session_id` | `{job_id, videos_queued, status}` | Queue videos for processing |
| GET | `/{video_id}` | — | Video object | Single video detail |
| GET | `/{video_id}/status` | — | `{status, progress}` | Processing progress |
| GET | `/{video_id}/frame/{frame_num}` | — | Frame image | Raw frame image |
| GET | `/{video_id}/frame/{frame_num}/features` | — | Feature list | Per-pigeon features for a frame |
| GET | `/{video_id}/track-edits` | — | Edit list | Track edit history for a video |

### Review Router (`/api/review`)

| Method | Path | Params | Returns | Description |
|--------|------|--------|---------|-------------|
| GET | `/attention/count` | — | `{total, qc_flags, identities, behaviors}` | Counts of items needing attention |
| GET | `/attention/items` | — | Item list | Detailed attention items |
| GET | `/identities/next-video` | — | `{video_id: int \| null}` | Next video needing identity review |
| GET | `/identities` | `video_id` | Assignment list | Identity assignments for a video |
| POST | `/identities/confirm` | Body: `assignment_id`, `action`, `pigeon_id`, `reviewer` | Updated assignment | Confirm or reassign a single identity |
| POST | `/identities/batch` | Body: `assignments[]`, `reviewer` | `{confirmed: int}` | Batch confirm multiple identities |
| GET | `/behaviors` | `status` (default `raw`), `video_id`, `limit` (1-200) | Behavior list | List behaviors filtered by review status |
| GET | `/droppings` | `status` (default `raw`), `limit` (1-200) | Droppings list | List droppings filtered by review status |
| GET | `/qc-flags` | `video_id` | QC flag list | QC flags for a video |
| POST | `/qc-flags/resolve` | Body: `flag_id`, `action`, `resolved_action`, `reviewer` | Resolved flag | Resolve a single QC flag |
| POST | `/qc-flags/batch-resolve` | Body: `flag_ids[]`, `action`, `resolved_action`, `reviewer` | Resolved flag list | Batch resolve multiple QC flags |
| POST | `/track-edits` | Body: `video_id`, `frame_idx`, `edit_type`, `editor`, `details` | Created edit | Record a track edit |
| POST | `/track-merges` | Body: merge params | Created merge | Merge two tracks |
| POST | `/track-splits` | Body: split params | Created split | Split a track |
| POST | `/droppings/review` | Body: `dropping_id`, `action`, `reviewer` | Updated dropping | Review a dropping detection |

### Settings Router (`/api/settings`)

| Method | Path | Params | Returns | Description |
|--------|------|--------|---------|-------------|
| GET | `/info` | — | `{database_path, database_size_mb, total_videos, total_pigeons, ...}` | System info with DB stats and entity counts |
| GET | `/zones` | — | `{zones: string[]}` | Distinct zones from feature data |
| DELETE | `/reset` | — | `{status: "reset"}` | Drop and recreate the database |
| POST | `/seed` | — | `{status: "seeded"}` | Load sample data (409 if data exists) |

### Pigeons Router (`/api/pigeons`)

| Method | Path | Params | Returns | Description |
|--------|------|--------|---------|-------------|
| GET | `/` | — | Pigeon list | All registered pigeons |
| GET | `/{pigeon_id}` | — | Pigeon profile | Detailed pigeon profile with stats |
| POST | `/` | Body: `pigeon_id`, `physical_markers`, `notes` | Created pigeon | Register a new pigeon |

### Insights Router (`/api/insights`)

| Method | Path | Params | Returns | Description |
|--------|------|--------|---------|-------------|
| GET | `/stats` | `period` | Dashboard stats | Aggregate statistics |
| GET | `/behavior-chart` | `period`, `pigeon_id` | Chart data | Behavior time series |
| GET | `/social-map` | `period` | Node and edge data | Pairwise social proximity map |
| GET | `/zone-heatmap` | `period`, `pigeon_id` | Heatmap data | Zone occupancy heatmap |
| GET | `/droppings-heatmap` | `period` | Heatmap data | Droppings spatial distribution |
| POST | `/exports` | Body: `format`, `filters` | `{export_id, download_url}` | Create a data export |
| GET | `/exports/{export_id}/download` | — | File download | Download a generated export |

### Training Router (`/api/training`)

| Method | Path | Params | Returns | Description |
|--------|------|--------|---------|-------------|
| GET | `/clips` | `labeled`, `limit` | Clip list | Clips from the clip library |
| POST | `/label` | Body: `clip_id`, `behavior_class`, `labeler`, `split`, `notes` | Created label | Label a training clip |
| GET | `/models` | — | Model list | All models in the registry |
| POST | `/train` | Body: `backbone`, `epochs`, `learning_rate`, `notes` | `{model_id, status}` | Start model training |

---

## Section 11 — Dependency Map

### Backend Router Dependencies

Each router depends on `database.py` for DB access via `get_db()` / `get_connection()`.

```
main.py
├── routers/videos.py    → database (get_db), utils (get_default_reviewer)
├── routers/review.py    → database (get_db), utils (get_default_reviewer)
├── routers/pigeons.py   → database (get_db)
├── routers/insights.py  → database (get_db, aiosqlite)
├── routers/training.py  → database (get_db, aiosqlite), utils (get_default_reviewer)
└── routers/settings.py  → database (get_db, init_db, DB_PATH), seed_data
```

### Frontend Page Dependencies

```
App.tsx (router)
└── Layout.tsx
    ├── Sidebar.tsx         → api/client (apiFetch)
    ├── TopBar.tsx          → api/client (apiFetch)
    └── Pages:
        ├── Home.tsx        → api/client
        ├── Videos.tsx      → api/client
        ├── VideoDetail.tsx → api/client, api/review
        ├── Pigeons.tsx     → api/client
        ├── PigeonProfile.tsx → api/client
        ├── Review.tsx      → api/review, api/client
        ├── Insights.tsx    → api/client
        ├── Training.tsx    → api/client
        └── LabSetup.tsx    → api/settings, api/client
```

---

## Appendix A — Seed Data Summary

The `backend/seed_data.py` script creates the following sample data for development:

| Entity             | Count   | Notes                                           |
|--------------------|---------|------------------------------------------------|
| Pigeons            | 4       | Alpha, Beta, Gamma, Delta with physical markers |
| Videos             | 4       | 2 sessions, mixed cameras, all status=completed |
| Video assignments  | 16      | 4 pigeons x 4 videos, status=raw               |
| QC flags           | 4       | 1 per video, mixed severity, status=pending     |
| Features           | ~varies | Per-pigeon per-frame tracking data              |
| Behavior records   | ~varies | Aggregated behavior observations                |
| Pairwise records   | ~varies | Inter-pigeon distance measurements              |
| Droppings          | 15-20   | Randomly distributed across videos              |
| Clips              | 10      | Extracted segments with varied reasons           |
| Behavior labels    | 5       | 5 of 10 clips labeled with behavior classes     |
| Model registry     | 1       | Single baseline behavior classifier             |
