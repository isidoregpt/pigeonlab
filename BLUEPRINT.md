# PigeonLab Blueprint

## Complete System Reference for LLM-Assisted Debugging, Review, and Development

**Last updated:** 2026-03-23
**Purpose:** This document provides complete operational understanding of PigeonLab without requiring access to the source code. Any error can be traced, any feature understood, and any file identified using only this document.

---

## Table of Contents

1. [What PigeonLab Is](#1-what-pigeonlab-is)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [File Map — Every File and Its Purpose](#3-file-map)
4. [Database Schema — Complete Reference](#4-database-schema)
5. [Backend API — Every Endpoint](#5-backend-api)
6. [Frontend — Every Page, Component, and Data Flow](#6-frontend)
7. [State Machines — Status Lifecycles](#7-state-machines)
8. [Data Flow — How Information Moves Through the System](#8-data-flow)
9. [API Client Layer — How Frontend Talks to Backend](#9-api-client-layer)
10. [Error Catalog — Known Gaps and Failure Modes](#10-error-catalog)
11. [Dependency Map — What Depends on What](#11-dependency-map)
12. [Troubleshooting Decision Tree](#12-troubleshooting)

---

## 1. What PigeonLab Is

PigeonLab is a full-stack web application for pigeon behavioral research. Researchers upload pigeon videos, and the system detects, tracks, and analyzes pigeon positions, identities, and behaviors. Researchers then review the automated results, correct mistakes, visualize spatial patterns, label behavior clips, train classification models, and export publication-ready data.

**It replaces two external tools:**
- **EZannot** — manual annotation and identity review
- **LabGym** — behavior detection, classification, and training

**Tech stack:**
- **Backend:** Python 3.10+, FastAPI, SQLite (synchronous via sqlite3, async via aiosqlite)
- **Frontend:** React 19, TypeScript, Vite 6, TailwindCSS v4, React Router v7, TanStack Query v5, Recharts, Lucide icons
- **Communication:** REST API over HTTP, JSON payloads, Vite dev proxy `/api` → `localhost:8000`

**Single-user local deployment.** No authentication. Runs on Windows 11 with an NVIDIA GPU. Backend on port 8000, frontend on port 5173.

---

## 2. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        BROWSER                               │
│  React 19 + TypeScript + TailwindCSS v4                      │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐          │
│  │  Pages   │ │Components│ │ API Layer│ │  Types  │          │
│  │ (7 pages)│ │(UI + Layout)│ │(7 modules)│ │(index.ts)│      │
│  └────┬─────┘ └────┬─────┘ └─────┬────┘ └────┬────┘         │
│       └─────────────┴─────────────┴───────────┘              │
│                         │                                     │
│              TanStack Query (caching + refetching)            │
│                         │                                     │
│              Vite Dev Proxy: /api → localhost:8000            │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP JSON
┌─────────────────────────┴───────────────────────────────────┐
│                     FastAPI Backend                           │
│  ┌──────────┐ ┌────────────┐ ┌──────────┐                   │
│  │  main.py  │ │  7 Routers │ │database.py│                  │
│  │ (CORS,    │ │ (videos,   │ │(schema,   │                  │
│  │  lifespan,│ │  pigeons,  │ │ connection│                  │
│  │  mounts)  │ │  insights, │ │ init)     │                  │
│  └──────────┘ │  review,   │ └─────┬─────┘                  │
│                │  training, │       │                         │
│                │  export,   │       │ sqlite3 / aiosqlite    │
│                │  stats)    │       │                         │
│                └────────────┘       │                         │
│                                     ▼                        │
│                          data/pigeonlab.db                    │
│                          (16 tables, 30+ indexes)            │
└──────────────────────────────────────────────────────────────┘
```

**Startup sequence:**
1. `main.py` lifespan creates `data/` subdirectories (videos, clips, models, exports, frames)
2. `init_db()` creates all 16 tables and 30+ indexes if they don't exist
3. CORS middleware allows `http://localhost:5173`
4. 7 routers are mounted under `/api/` prefix
5. One additional route `/api/activity` is mounted directly on the app (not through a router)

---

## 3. File Map

### Root Level

| File | Purpose |
|------|---------|
| `.env.example` | Template for environment variables (DATABASE_URL, ports) |
| `.gitignore` | Standard Python + Node + IDE ignores |
| `README.md` | Quick start guide, project structure, tech stack |
| `start.bat` | Windows CMD startup: creates venv, installs deps, launches both servers |
| `start.ps1` | Windows PowerShell startup: same as above |
| `pigeonlabplatformspec.md` | Architecture specification: 7 system layers, database schema, all subsystems |
| `pigeonlabuxspec.md` | UX design specification: navigation, screens, visual language, progressive disclosure |
| `pigeonlabbridge.md` | Implementation bridge: roles, state mappings, API contracts, mask correction workflow, build priority |

### Backend (`backend/`)

| File | Purpose | Key Functions/Classes |
|------|---------|----------------------|
| `main.py` | FastAPI app entry point | `lifespan()` — creates dirs + init DB; mounts 7 routers + 1 direct route; CORS config; health check |
| `database.py` | SQLite schema and connection management | `init_db()` — creates 16 tables + indexes; `get_connection()` — returns sqlite3.Connection with WAL + FK; `get_db_path()` — returns path string for aiosqlite |
| `seed_data.py` | Demo data generator | `seed()` — inserts 4 pigeons, 2 videos, 8 assignments, 2 QC flags, 80 features, 8 behaviors, 8 pairwise records |
| `requirements.txt` | Python dependencies | fastapi, uvicorn, python-multipart, aiofiles, pillow, numpy, opencv-python, torch, torchvision |
| `models/__init__.py` | Empty — placeholder for future ML model code |
| `services/__init__.py` | Empty — placeholder for future service layer |
| `routers/__init__.py` | Empty — makes routers a package |

### Backend Routers (`backend/routers/`)

| File | Prefix | Purpose | Endpoints Count |
|------|--------|---------|----------------|
| `videos.py` | `/api/videos` | Video CRUD, frames, processing | 6 endpoints |
| `pigeons.py` | `/api/pigeons` | Pigeon CRUD, heatmaps, behaviors, identity | 8 endpoints |
| `insights.py` | `/api/insights` | Heatmaps, behaviors, pairwise, droppings, session comparison | 5 endpoints |
| `review.py` | `/api/review` | Identity review, QC flags, mask edits, track merge/split, behavior review, dropping review | 13 endpoints |
| `training.py` | `/api/training` | Clips, labeling, readiness, training, models, reinference | 10 endpoints |
| `export.py` | `/api/export` | CSV export with filters, file download | 2 endpoints |
| `stats.py` | `/api/stats` | Dashboard stats, zone summary, recent activity | 3 endpoints (+1 mounted directly) |

### Frontend (`frontend/`)

| File | Purpose |
|------|---------|
| `index.html` | HTML shell, mounts React at `#root` |
| `package.json` | Dependencies and scripts (dev, build, preview) |
| `tsconfig.json` | TypeScript config: strict mode, noUnusedLocals, noUnusedParameters, noUncheckedIndexedAccess |
| `vite.config.ts` | Vite config: React plugin, TailwindCSS plugin, dev proxy `/api` → `localhost:8000` |

### Frontend Source (`frontend/src/`)

| File | Purpose |
|------|---------|
| `main.tsx` | React entry: StrictMode, QueryClientProvider (30s stale, 2 retries), BrowserRouter, ToastProvider |
| `App.tsx` | Route definitions: 10 routes wrapped in Layout + ErrorBoundary |
| `statusUtils.ts` | Maps status strings to labels, colors, and dot colors for badges |

### Frontend Pages (`frontend/src/pages/`)

| File | Route | What It Renders | API Calls |
|------|-------|-----------------|-----------|
| `Home.tsx` | `/` | Dashboard: stats cards, attention items, zone summary bars, activity feed | `getStatsToday`, `getAttentionItems`, `getStatsSummary`, `getActivity` |
| `Videos.tsx` | `/videos` | Video list grouped by date, search, pagination, Add Videos modal | `getVideos` (polling 10s) |
| `VideoDetail.tsx` | `/videos/:id` | Frame viewer with scrubber, pigeon cards per frame, QC flags, metadata sidebar, edit history | `getVideo`, `getVideoFeatures`, `getQCFlags`, `getVideoTrackEdits`, `updateVideoReview`, `reviewQCFlag` |
| `Pigeons.tsx` | `/pigeons` | Pigeon card gallery, Register New modal | `getPigeons` |
| `PigeonProfile.tsx` | `/pigeons/:id` | Header with edit, zone bar chart, behavior bar chart, identity confidence bar | `getPigeon`, `getPigeonBehaviors`, `getPigeonIdentityStatus`, `updatePigeon` |
| `Insights.tsx` | `/insights` | Heatmap canvas, behavior stacked bar chart, social network SVG, droppings heatmap, export buttons | `getInsightsHeatmap`, `getInsightsBehaviors`, `getInsightsPairwise`, `getInsightsDroppings`, `getPigeons`, `createExport` |
| `Review.tsx` | `/review` | Queue overview OR identity review flow OR QC flag review flow (routed by `?type=` param) | `getAttentionCount`, `getUnconfirmedIdentities`, `reviewIdentity`, `getQCFlags`, `reviewQCFlag`, `getPigeons`, `getFrameUrl` |
| `Training.tsx` | `/training` | 4-tab interface: Clip Library, Label Clips, Train Model, Model History | `getClips`, `labelClip`, `getReadiness`, `startTraining`, `getTrainingStatus`, `getModels`, `activateModel`, `reinferVideos` |
| `LabSetup.tsx` | `/settings` | Placeholder sections for Arena Zones, Camera Config, Behavior Rules |
| `NotFound.tsx` | `*` | 404 page with link back to home |

### Frontend Components (`frontend/src/components/`)

**Layout Components (`components/layout/`):**

| File | Purpose | Key Behavior |
|------|---------|-------------|
| `Layout.tsx` | App shell: sidebar + topbar + content area | Uses `<Outlet />` for page content; derives page title from pathname |
| `Sidebar.tsx` | Left navigation: Home, Videos, Pigeons, Insights, Training, Settings | Uses `<NavLink>` with active state styling (accent color + left border) |
| `TopBar.tsx` | Header bar with page title and notification bell | Polls `/review/attention/count` every 30 seconds; shows amber badge when items need attention |

**UI Components (`components/ui/`):**

| File | Purpose | Props |
|------|---------|-------|
| `VideoCard.tsx` | Card displaying one video with status, metadata, action buttons | `video: Video` |
| `PigeonCard.tsx` | Card displaying one pigeon with zones, session count | `pigeon: Pigeon, topZone?, sessionCount?` |
| `StatusBadge.tsx` | Colored pill showing status with dot | `status: AnyStatus, size?: "sm" \| "md"` |
| `EmptyState.tsx` | Friendly empty state with emoji, title, description, optional action button | `icon, title, description, actionLabel?, onAction?` |
| `LoadingState.tsx` | Skeleton card grid (3 cards with pulsing rectangles) | No props |
| `ErrorBoundary.tsx` | React class component catching render errors | Wraps children; shows reload button on error |
| `Toast.tsx` | Toast notification system with context provider | `ToastProvider` wraps app; `useToast()` hook returns `{success, error}` |
| `AddVideosModal.tsx` | 3-step wizard: file paths → camera assignment → processing options | `onClose, onSuccess` |
| `RegisterPigeonModal.tsx` | Form modal: name, markers, notes | `onClose, onSuccess` |

### Frontend API Layer (`frontend/src/api/`)

| File | Functions | Backend Router |
|------|-----------|---------------|
| `client.ts` | `get<T>`, `post<T>`, `put<T>`, `apiFetch` — generic HTTP helpers with error handling | N/A (shared) |
| `videos.ts` | `getVideos`, `getVideo`, `processVideos`, `getVideoStatus`, `updateVideoReview`, `getFrameUrl`, `getVideoFeatures`, `getVideoTrackEdits` | `videos.py` |
| `pigeons.ts` | `getPigeons`, `getPigeon`, `getPigeonHeatmap`, `getPigeonBehaviors`, `getPigeonIdentityStatus`, `createPigeon`, `updatePigeon` | `pigeons.py` |
| `insights.ts` | `getInsightsHeatmap`, `getInsightsBehaviors`, `getInsightsPairwise`, `getInsightsDroppings`, `compareSessionsInsight`, `createExport`, `getExportDownloadUrl` | `insights.py`, `export.py` |
| `review.ts` | `getUnconfirmedIdentities`, `reviewIdentity`, `getQCFlags`, `reviewQCFlag`, `submitMaskEdit`, `mergeTrack`, `splitTrack`, `reviewBehavior`, `reviewDropping` | `review.py` |
| `training.ts` | `getClips`, `labelClip`, `getReadiness`, `getClassCounts`, `startTraining`, `getTrainingStatus`, `getModels`, `activateModel`, `reinferVideos` | `training.py` |
| `stats.ts` | `getStatsToday`, `getStatsSummary`, `getAttentionCount`, `getAttentionItems`, `getActivity` | `stats.py`, `review.py` |

### Frontend Types (`frontend/src/types/index.ts`)

Defines all TypeScript interfaces used across the app:

| Interface | Key Fields | Used By |
|-----------|-----------|---------|
| `Video` | video_id, video_name, session_id, camera_type, total_frames, fps, review_status, processing_status | VideoCard, Videos, VideoDetail |
| `Pigeon` | pigeon_id, physical_markers, preferred_zones, total_frames_observed, notes | PigeonCard, Pigeons, PigeonProfile |
| `VideoAssignment` | id, video_id, video_obj_id, pigeon_id, confidence, match_method, review_status | Review (identity flow) |
| `Feature` | id, video_id, frame_idx, pigeon_id, centroid_x/y, velocity_mm_s, heading_deg, current_zone, confidence | VideoDetail (per-frame pigeon data) |
| `Behavior` | id, video_id, pigeon_id, behavior, source, start_frame, end_frame, duration_seconds, confidence, review_status | PigeonProfile, Insights |
| `QCFlag` | id, video_id, frame_idx, rule_name, severity, reason, review_status, resolved_action | Review (QC flow), VideoDetail |
| `ClipLibraryItem` | id, video_id, pigeon_id, start_frame, end_frame, duration_seconds, clip_path, zone, extraction_reason | Training |
| `ModelRegistryEntry` | id, model_name, model_type, version, train/val/test_accuracy, is_active, created_at | Training (Model History) |
| `DroppingDetection` | id, video_id, frame_idx, centroid_x/y, zone, confidence, review_status | Review (droppings), Insights |
| `AttentionItem` | type, description, link, severity, count | Home dashboard |
| `StatsToday` | videos_processed, pigeons_tracked | Home dashboard |

### Other Frontend Files

| File | Purpose |
|------|---------|
| `hooks/usePageTitle.ts` | Sets `document.title` to "PigeonLab — {title}" on mount, resets on unmount |
| `styles/globals.css` | Imports TailwindCSS; defines CSS theme variables (colors: bg, surface, border, text-primary, text-secondary, accent, success, warning, error) |

### Data Directory (`data/`)

Created at startup by the lifespan handler. Contains:

| Directory | Contents |
|-----------|----------|
| `data/pigeonlab.db` | SQLite database (all application state) |
| `data/videos/` | Uploaded/referenced video files |
| `data/clips/` | Extracted behavior clips for labeling |
| `data/models/` | Trained model checkpoints |
| `data/exports/` | Generated CSV export files |
| `data/frames/` | Extracted video frames as JPEGs, organized by `{video_id}/{frame_num:06d}.jpg` |

---

## 4. Database Schema

### Tables and Their Relationships

```
videos ──────────┬──── video_assignments ──── pigeons
                 │         │
                 │    identity_reviews
                 │
                 ├──── features
                 ├──── pairwise
                 ├──── behaviors
                 ├──── droppings ──── droppings_reviews
                 ├──── qc_flags
                 ├──── review_tasks
                 ├──── track_edits
                 └──── clip_library ──── behavior_labels

model_registry (standalone)
benchmark_results (standalone)
```

### Complete Table Definitions

#### `videos` — One row per uploaded/processed video file

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| video_id | INTEGER PK AUTO | | Unique identifier |
| video_name | TEXT NOT NULL | | Original filename |
| session_id | TEXT | NULL | Groups videos from same recording session |
| camera_type | TEXT | NULL | "Overhead", "Side", "Corner", "Other" |
| total_frames | INTEGER | NULL | Frame count after processing |
| fps | REAL | NULL | Frames per second |
| processed_at | TEXT | NULL | ISO timestamp of processing completion |
| review_status | TEXT | 'raw' | raw → reviewed → approved / rejected |
| processing_status | TEXT | 'queued' | queued → processing → completed / failed |
| model_version | TEXT | NULL | SAM3 version used for processing |
| config_hash | TEXT | NULL | Hash of processing config for reproducibility |
| notes | TEXT | NULL | Free-text notes |

**Indexes:** session_id, review_status, processing_status

#### `pigeons` — One row per known pigeon identity

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| pigeon_id | TEXT PK | | Human-readable name (e.g., "Alpha") |
| physical_markers | TEXT | NULL | Description of leg bands, markings, etc. |
| appearance_embedding | BLOB | NULL | Reserved for future appearance matching |
| preferred_zones | TEXT | NULL | JSON string of preferred zones |
| total_frames_observed | INTEGER | 0 | Lifetime frame count |
| first_seen | TEXT | NULL | ISO timestamp |
| last_seen | TEXT | NULL | ISO timestamp |
| notes | TEXT | NULL | Free-text notes |

#### `video_assignments` — Maps detected objects in videos to pigeon identities

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER PK AUTO | | |
| video_id | INTEGER FK→videos | | Which video |
| video_obj_id | INTEGER | | Object ID within the video's detection |
| pigeon_id | TEXT FK→pigeons | | Assigned pigeon identity |
| confidence | REAL | NULL | 0.0-1.0 confidence score |
| match_method | TEXT | NULL | "marker", "appearance", "spatial", "manual", "placeholder" |
| review_status | TEXT | 'raw' | raw → reviewed → approved / rejected |
| assigned_at | TEXT | NULL | When assignment was made |
| reviewed_at | TEXT | NULL | When human reviewed |
| reviewed_by | TEXT | NULL | Who reviewed |

**Indexes:** video_id, pigeon_id, review_status

#### `identity_reviews` — Audit log for identity review actions

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | |
| assignment_id | INTEGER FK→video_assignments | Which assignment was reviewed |
| action | TEXT NOT NULL | "confirm", "reject", "reassign" |
| old_pigeon_id | TEXT | Previous identity |
| new_pigeon_id | TEXT | New identity (for reassign) |
| reviewer | TEXT | Who did it |
| reviewed_at | TEXT | When |
| notes | TEXT | Optional notes |

#### `track_edits` — Audit log for mask/track corrections

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | |
| video_id | INTEGER FK→videos | Which video |
| frame_idx | INTEGER | Which frame |
| edit_type | TEXT NOT NULL | "merge", "split", "delete", "correct_mask", "mask" |
| old_obj_id | INTEGER | Source object (for merge/split) |
| new_obj_id | INTEGER | Target object (for merge/split) |
| editor | TEXT | Who did it |
| edited_at | TEXT | When |
| details | TEXT | JSON with edit-specific metadata |

#### `features` — Per-frame, per-pigeon spatial data

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | |
| video_id | INTEGER FK→videos | |
| frame_idx | INTEGER | Frame number |
| pigeon_id | TEXT FK→pigeons | |
| centroid_x, centroid_y | REAL | Pixel coordinates |
| centroid_mm_x, centroid_mm_y | REAL | Calibrated millimeter coordinates |
| area_px | REAL | Mask area in pixels |
| area_mm2 | REAL | Calibrated area |
| velocity_px | REAL | Pixels/frame velocity |
| velocity_mm_s | REAL | mm/second velocity |
| heading_deg | REAL | Estimated heading 0-360 |
| current_zone | TEXT | Which arena zone |
| distance_to_nearest_wall_px | REAL | |
| confidence | REAL DEFAULT 1.0 | Quality score |

**Indexes:** (video_id, frame_idx), pigeon_id, current_zone

#### `pairwise` — Per-frame distance between pigeon pairs

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | |
| video_id | INTEGER FK→videos | |
| frame_idx | INTEGER | |
| pigeon_a, pigeon_b | TEXT FK→pigeons | The two pigeons |
| distance_px, distance_mm | REAL | Distance between centroids |
| overlap_iou | REAL DEFAULT 0.0 | Mask intersection-over-union |

#### `behaviors` — Detected behavior events

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | |
| video_id | INTEGER FK→videos | |
| pigeon_id | TEXT FK→pigeons | |
| behavior | TEXT NOT NULL | "Feeding", "Resting", "Walking", etc. |
| source | TEXT | "rule_engine" or "learned_model" |
| model_version | TEXT | NULL for rule_engine |
| start_frame, end_frame | INTEGER | Frame range |
| duration_seconds | REAL | |
| confidence | REAL | |
| zone | TEXT | Where it happened |
| interacting_with | TEXT | Other pigeon ID if social behavior |
| review_status | TEXT DEFAULT 'raw' | |
| details | TEXT | JSON with behavior-specific metadata |

#### `clip_library` — Extracted video clips for behavior labeling

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | |
| video_id | INTEGER FK→videos | Source video |
| pigeon_id | TEXT FK→pigeons | Target pigeon |
| start_frame, end_frame | INTEGER | Frame range |
| duration_seconds | REAL | |
| clip_path | TEXT | Filesystem path to extracted MP4 |
| mask_overlay | BOOLEAN DEFAULT 1 | Whether mask is burned in |
| zone | TEXT | Arena zone during clip |
| velocity_context | TEXT | Average velocity metadata |
| pairwise_context | TEXT | JSON: nearby pigeons |
| extraction_reason | TEXT | "candidate_behavior", "manual", "random" |
| created_at | TEXT | |

#### `behavior_labels` — Human-assigned labels on clips

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | |
| clip_id | INTEGER FK→clip_library | Which clip |
| behavior_class | TEXT NOT NULL | "Feeding", "Resting", etc. |
| labeler | TEXT | Who labeled it |
| labeled_at | TEXT | When |
| split | TEXT DEFAULT 'train' | "train", "val", "test" |
| notes | TEXT | |

#### `model_registry` — Trained model versions

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | |
| model_name | TEXT NOT NULL | e.g., "behavior_r3d_18" |
| model_type | TEXT NOT NULL | "behavior_classifier" |
| version | TEXT | e.g., "v20260101_143000" |
| checkpoint_path | TEXT | Filesystem path to .pt file |
| training_config | TEXT | JSON with full training params |
| training_clips | INTEGER | How many clips were used |
| train_accuracy, val_accuracy, test_accuracy | REAL | |
| created_at | TEXT | |
| notes | TEXT | |
| is_active | BOOLEAN DEFAULT 0 | Only one active per model_type |

#### `droppings` — Detected pigeon droppings

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | |
| video_id | INTEGER FK→videos | |
| frame_idx | INTEGER | |
| centroid_x, centroid_y | REAL | Position |
| area_px | REAL | Size |
| zone | TEXT | Arena zone |
| confidence | REAL | Detection confidence |
| detection_method | TEXT | "sam3_text", "finetuned", "background_diff", "manual" |
| review_status | TEXT DEFAULT 'raw' | |
| deduplicated | BOOLEAN DEFAULT 0 | |

#### `droppings_reviews` — Audit log for dropping review actions

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | |
| dropping_id | INTEGER FK→droppings | |
| action | TEXT NOT NULL | "confirm" or "reject" |
| reviewer | TEXT | |
| reviewed_at | TEXT | |

#### `qc_flags` — Quality control issues detected during processing

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | |
| video_id | INTEGER FK→videos | |
| frame_idx | INTEGER | Specific frame (nullable) |
| rule_name | TEXT NOT NULL | e.g., "id_swap_detected", "low_confidence_id" |
| severity | TEXT | "low", "medium", "high", "critical" |
| reason | TEXT | Human-readable description |
| review_status | TEXT DEFAULT 'pending' | pending → acknowledged → resolved |
| resolved_action | TEXT | "accepted", "corrected", "ignored" |

#### `review_tasks` — Work queue items

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | |
| task_type | TEXT NOT NULL | "identity", "track", "mask", "behavior", "dropping", "qc_flag" |
| reference_id | INTEGER | ID in the relevant table |
| video_id | INTEGER FK→videos | |
| priority | TEXT DEFAULT 'normal' | "low", "normal", "high", "urgent" |
| status | TEXT DEFAULT 'pending' | "pending", "in_progress", "completed", "skipped" |
| assigned_to | TEXT | |
| created_at, completed_at | TEXT | |

#### `benchmark_results` — Accuracy measurements per subsystem

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK AUTO | |
| subsystem | TEXT NOT NULL | "segmentation", "tracking", "identity", "behavior", "droppings" |
| benchmark_name | TEXT | |
| model_version | TEXT | |
| metric_name | TEXT NOT NULL | "precision", "recall", "f1", "iou", etc. |
| metric_value | REAL | |
| sample_size | INTEGER | |
| run_at | TEXT | |
| config_used | TEXT | JSON |

---

## 5. Backend API — Every Endpoint

### Videos Router (`/api/videos`)

| Method | Path | Request | Response | Purpose |
|--------|------|---------|----------|---------|
| GET | `/` | `?sort=date&page=1&per_page=20` | `{videos: Video[], total, page, per_page}` | List videos with pagination |
| GET | `/{video_id}` | | `Video & {pigeon_count}` | Single video with pigeon count |
| POST | `/process` | `{video_paths, camera_assignments, text_prompt, expected_pigeon_count, session_id}` | `{job_id, videos_queued, status}` | Queue videos for processing |
| GET | `/{video_id}/status` | | `{status, progress}` | Processing progress (0/50/100) |
| GET | `/{video_id}/frame/{frame_num}` | | JPEG image | Serve extracted frame |
| PUT | `/{video_id}/review` | `{review_status, reviewer}` | `{video_id, review_status, reviewer}` | Update review status |

**⚠️ KNOWN GAP:** Frontend calls `GET /{video_id}/features?frame_idx=N` and `GET /{video_id}/track-edits` but these endpoints DO NOT EXIST in videos.py. VideoDetail page silently fails on these.

### Pigeons Router (`/api/pigeons`)

| Method | Path | Request | Response | Purpose |
|--------|------|---------|----------|---------|
| GET | `/` | | `PigeonListItem[]` (with session_count, top_zone) | List all pigeons |
| GET | `/{pigeon_id}` | | `PigeonProfile` (with avg_velocity, behavior_summary) | Full pigeon profile |
| GET | `/{pigeon_id}/heatmap` | `?period=week` | `{grid: number[][], width, height, pigeon_id}` | Position heatmap grid |
| GET | `/{pigeon_id}/behaviors` | `?period=week` | `{behaviors: {name: {duration_seconds, event_count}}}` | Behavior summary |
| GET | `/{pigeon_id}/identity-status` | | `{confirmed_sessions, unconfirmed_sessions, total_sessions}` | Identity confidence |
| POST | `/` | `{pigeon_id, physical_markers?, notes?}` | `{pigeon_id, status}` | Register new pigeon |
| PUT | `/{pigeon_id}` | `{physical_markers?, preferred_zones?, notes?}` | `{pigeon_id, status}` | Update pigeon profile |

**Helper functions:** `_get_pigeon_or_404`, `_session_count`, `_top_zone`, `_period_since`

### Insights Router (`/api/insights`)

| Method | Path | Request | Response | Purpose |
|--------|------|---------|----------|---------|
| GET | `/heatmap` | `?pigeons=all&period=week` | `{grid: number[][], width, height}` | Combined position heatmap (50x50 grid, normalized 0-1) |
| GET | `/behaviors` | `?period=week` | `{pigeons: {id: {behavior: {duration_seconds, event_count}}}}` | Per-pigeon behavior durations |
| GET | `/pairwise` | `?period=week` | `{pairs: [{pigeon_a, pigeon_b, avg_distance_mm, proximity_events, total_duration_seconds}]}` | Social proximity data |
| GET | `/droppings` | `?period=week` | `{total, by_zone: {zone: count}, grid: number[][]}` | Droppings spatial distribution |
| GET | `/compare` | `?a=session_id&b=session_id` | `{zone_occupancy_diff, behavior_diff, identity_changes}` | Session comparison |

**Heatmap algorithm:** Maps centroids to a 50x50 grid, normalizes by dividing by max value. Returns 0.0-1.0 per cell. Frontend renders via HTML Canvas.

### Review Router (`/api/review`)

| Method | Path | Request | Response | Purpose |
|--------|------|---------|----------|---------|
| GET | `/` | | `{status: "ok"}` | Health check |
| GET | `/attention/count` | | `{total, identity, qc, droppings}` | Count of items needing review |
| GET | `/attention` | `?limit=5` | `AttentionItem[]` | Prioritized attention items |
| GET | `/identities` | `?video_id=N` | `VideoAssignment[]` | Unconfirmed identities for a video |
| POST | `/identity` | `{assignment_id, action, pigeon_id?, old/new_pigeon_id?, reviewer?}` | Updated `VideoAssignment` | Confirm/reject/reassign identity |
| GET | `/qc-flags` | `?status=pending&video_id=N` | `QCFlag[]` | List QC flags |
| POST | `/qc-flag` | `{flag_id, action, resolved_action?, reviewer?, notes?}` | Updated `QCFlag` | Resolve a QC flag |
| POST | `/mask-edit` | `{video_id, frame_idx, pigeon_id?, edit_type?, mask_data?, editor?, details?}` | `{edit_id, saved}` | Save mask correction |
| POST | `/track-merge` | `{video_id, source_obj_id, target_obj_id, from_frame?, editor?, notes?}` | `{edit_id, merged, frames_affected}` | Merge two tracks |
| POST | `/track-split` | `{video_id, obj_id, at_frame, editor?, notes?}` | `{edit_id, original_obj_id, new_obj_id, split_at_frame}` | Split a track |
| POST | `/behavior` | `{behavior_id, action, reviewer?}` | Updated `Behavior` | Confirm/reject behavior |
| POST | `/dropping` | `{dropping_id, action, reviewer?}` | Updated `Dropping` | Confirm/reject dropping |

**Action → Status mapping:** `confirm` → `approved`, `reject` → `rejected`, `reassign` → `approved` (with pigeon_id change)

### Training Router (`/api/training`)

**NOTE:** This router uses **aiosqlite** (async) unlike all other routers which use synchronous sqlite3.

| Method | Path | Request | Response | Purpose |
|--------|------|---------|----------|---------|
| GET | `/` | | `{status: "ok"}` | Health check |
| GET | `/clips` | `?labeled=true/false&pigeon=id&page=1&per_page=50` | `{clips: ClipWithLabel[], total, page, per_page}` | Paginated clip library with label join |
| POST | `/label` | `{clip_id, behavior_class, labeler?, split?, notes?}` | `{id, clip_id, behavior_class, labeler, labeled_at, split}` | Label a clip |
| GET | `/readiness` | | `{classes: {name: {count, minimum, ready, needed}}, total_labeled_clips, all_ready, num_classes}` | Training readiness check (min 20 clips/class) |
| GET | `/class-counts` | | `{class_name: count}` | Simple per-class counts |
| POST | `/start` | `{backbone, epochs, batch_size, learning_rate, freeze_backbone, behavior_classes}` | `{job_id, model_id, version, status, training_clips, config}` | Launch training (stub — no actual PyTorch training) |
| GET | `/status/{job_id}` | | `{job_id, epoch, total_epochs, loss, val_acc, status, progress}` | Training progress (returns placeholder) |
| GET | `/models` | | `ModelRegistryEntry[]` | All trained models |
| POST | `/models/{model_id}/activate` | `{}` | `{model_id, model_type, is_active}` | Set active model (deactivates others of same type) |
| POST | `/reinfer` | `{model_version?, scope?, skip_already_inferred?, only_approved_videos?}` | `{job_id, model_version, videos_eligible, videos_skipped, status}` | Re-run inference (stub) |

### Export Router (`/api/export`)

| Method | Path | Request | Response | Purpose |
|--------|------|---------|----------|---------|
| POST | `/` | `{format, include: string[], filters: {period?, video_id?, pigeon_id?}, include_manifest?}` | `{download_url, files_included, rows_exported}` | Generate CSV export |
| GET | `/download/{filename}` | | File download | Serve export file (path traversal protected) |

**Supported tables for include:** "features", "behaviors", "pairwise". Each generates a separate CSV file.

### Stats Router (`/api/stats`)

| Method | Path | Request | Response | Purpose |
|--------|------|---------|----------|---------|
| GET | `/today` | | `{videos_processed, pigeons_tracked}` | Today's processing stats |
| GET | `/summary` | `?period=week` | `{pigeons: {id: {zone: percentage}}}` | Per-pigeon zone occupancy |
| GET | `/activity` | `?limit=10` | `ActivityItem[]` | Recent events (videos, reviews, training) |

**Additional direct mount:** `GET /api/activity` → same handler as `/api/stats/activity`

### Health Check

| Method | Path | Response |
|--------|------|----------|
| GET | `/api/health` | `{status: "ok"}` |

---

## 6. Frontend — Detailed Page Behavior

### Home (`/`)

**Queries on mount:**
1. `getStatsToday()` → top stat cards (videos processed, pigeons tracked)
2. `getAttentionItems(5)` → "Needs Your Attention" list
3. `getStatsSummary("week")` → zone occupancy bars per pigeon
4. `getActivity(10)` → recent activity feed

**Empty state trigger:** All stats are zero AND attention list is empty AND activity is empty → shows "No videos processed yet" with link to Videos page.

**Attention items** are sorted by severity (critical → high → medium → low) and each links to the relevant review page.

**Zone summary bars** show colored segments for each zone a pigeon occupies, with percentages. Uses 5 colors cycling through teal shades.

### Videos (`/videos`)

**Queries on mount:**
1. `getVideos("date", page, 20)` — polls every 10 seconds for live status updates

**Features:**
- Search bar filters client-side by video_name or session_id
- Videos grouped by date: "Today", "Yesterday", or formatted date
- Pagination with Previous/Next buttons
- "Add Videos" button opens 3-step modal wizard

**Video card shows:** name, session ID, camera type, frame count, pigeon count, composite status badge (processing status takes priority over review status), "Watch" and "Review" action buttons.

### VideoDetail (`/videos/:id`)

**Layout:** Two-column — left is frame viewer + pigeon cards, right is metadata sidebar.

**Frame viewer:**
- Shows frame JPEG from `/api/videos/{id}/frame/{frameNum}`
- Previous/Next buttons and range slider for scrubbing
- Arrow keys left/right for frame-by-frame navigation
- Shows loading spinner during frame transitions

**Per-frame data:** Queries features for current frame, displays pigeon cards with name, zone, and moving/stationary indicator.

**QC flags:** Filters all pending flags for current frame_idx, shows inline warning banners with "Looks Fine" and "Fix This" buttons.

**Sidebar:** Video metadata (camera, frames, FPS, pigeons, session), status badges, action buttons (Confirm Identities, Review QC Flags, Approve Video), edit history list.

### Pigeons (`/pigeons`)

**Queries:** `getPigeons()` — returns all pigeons with session_count and top_zone enrichment.

**Displays:** Card grid with pigeon emoji avatar, name, physical markers, session count, top zone. Each card navigates to profile on click.

**Register modal:** Form with name (required), physical markers, notes. Validates name is non-empty. Calls `createPigeon` then invalidates pigeons query.

### PigeonProfile (`/pigeons/:id`)

**Queries on mount (parallel):**
1. `getPigeon(id)` — full profile with avg_velocity and behavior_summary
2. `getPigeonBehaviors(id, "week")` — behavior durations
3. `getPigeonIdentityStatus(id)` — confirmed vs unconfirmed session counts

**Sections:**
1. **Header** — name, markers, edit button. Edit mode shows inline form for markers and notes.
2. **Zone chart** — horizontal bar chart from behavior_summary (actually zone data despite the field name). Uses Recharts BarChart with vertical layout.
3. **Identity confidence** — shows confirmed/total sessions with progress bar and "Review Unconfirmed" link.
4. **Behavior chart** — horizontal bar chart of behavior durations. Uses Recharts.

**⚠️ NOTE:** The zone chart data comes from `pigeon.behavior_summary` which is populated from the behaviors table where `review_status='approved'`. If no behaviors are approved, this section will be empty even if feature data exists.

### Insights (`/insights`)

**Global filters:** Period selector (day/week/month/all), Camera selector (placeholder — always "All Cameras").

**Sections:**
1. **Zone Heatmap** — canvas-rendered 50x50 grid. Pigeon filter buttons (All + individual). Colors interpolate from white to teal based on normalized density.
2. **Behavior Summary** — Recharts stacked BarChart. X-axis is pigeon names, bars are behavior types. 8 rotating colors.
3. **Social Map** — SVG network diagram. Pigeons as labeled circles arranged in a ring. Lines between pairs with thickness proportional to proximity duration.
4. **Droppings Map** — same canvas heatmap but with red accent color. Shows "Not yet benchmarked" warning banner.
5. **Export buttons** — "Export as PDF" (shows alert — not implemented), "Export Data as CSV" (calls createExport mutation).

**⚠️ KNOWN BUG:** Export URL is double-prefixed. `getExportDownloadUrl` adds `/api/export/download/` but the backend response `download_url` already contains this path.

### Review (`/review`)

**Routing logic in the Review component:**
- No type param → shows `ReviewQueue` (overview with counts)
- `?type=identity&video_id=N` → shows `IdentityReview`
- `?type=qc` or `?type=qc&video_id=N` → shows `QCReview`
- **⚠️ GAP:** `?type=dropping` is referenced in ReviewQueue but has no handler — falls through to ReviewQueue

**ReviewQueue:** Shows 3 sections (identity, qc, droppings) with counts and "Start Reviewing" links.

**IdentityReview:** One-at-a-time pigeon confirmation. Shows video frame, pigeon grid with known pigeons to click, progress dots. Confirm action calls `reviewIdentity({action: "confirm"})`.

**QCReview:** List of pending flags with severity badges. Each flag has "Looks Fine" (resolves as accepted) and "Fix This" (navigates to VideoDetail at that frame). Batch resolve button for low-severity flags.

**QC flag translations:** `rule_name` values are mapped to human-readable descriptions in a lookup table (e.g., `id_swap_detected` → "Possible identity swap between two pigeons").

### Training (`/training`)

**4-tab interface:** Clip Library, Label Clips, Train Model, Model History.

**Tab 1 — Clip Library:** Filterable grid of clip cards. Filters: pigeon selector, labeled/unlabeled/all. Each card shows pigeon, duration, zone, label status, and "Label →" link.

**Tab 2 — Label Clips:** Sequential labeling of unlabeled clips. Progress bar, video placeholder (no actual playback), behavior button grid (Feeding, Resting, Walking, Preening, Courtship, Aggression, Other). **Keyboard shortcuts:** 1-7 for behaviors, 0 for skip. Calls `labelClip` mutation, advances to next clip.

**Tab 3 — Train Model:** Readiness table (per-class clip counts vs 20 minimum), configuration form (backbone, epochs, batch size, learning rate, freeze backbone), behavior class selector (toggle chips), Launch Training button. Calls `startTraining`, polls `getTrainingStatus` every 3 seconds for progress.

**Tab 4 — Model History:** Table of all trained models with accuracy metrics. "Set as Active" button. "Apply to All Videos" reinference flow with confirmation dialog.

### LabSetup (`/settings`)

Three placeholder sections: Arena Zones, Camera Configuration, Behavior Rules. No functional UI — just descriptive text promising future implementation.

### NotFound (`*`)

Friendly 404 with pigeon emoji and "Back to Home" link.

---

## 7. State Machines

### Entity Review Status (videos, identities, behaviors, droppings)

```
   ┌─────┐     human reviews     ┌──────────┐
   │ raw │ ──────────────────────→│ reviewed  │
   └─────┘                        └─────┬─────┘
                                        │
                              ┌─────────┴─────────┐
                              ▼                   ▼
                        ┌──────────┐        ┌──────────┐
                        │ approved │        │ rejected │
                        └──────────┘        └──────────┘
```

**Database column:** `review_status` — values: `raw`, `reviewed`, `approved`, `rejected`

**Frontend label mapping:** raw → "Raw" (should be "Not yet checked" per spec), approved → "Approved" (should be "Confirmed" for non-video entities per spec)

### Video Processing Status

```
   ┌────────┐     pipeline starts     ┌────────────┐
   │ queued │ ───────────────────────→│ processing │
   └────────┘                         └──────┬──────┘
                                             │
                                   ┌─────────┴─────────┐
                                   ▼                   ▼
                             ┌───────────┐       ┌────────┐
                             │ completed │       │ failed │
                             └───────────┘       └────────┘
```

**Database column:** `processing_status` — values: `queued`, `processing`, `completed`, `failed`

### QC Flag Status (separate lifecycle)

```
   ┌─────────┐     user views     ┌──────────────┐     user resolves     ┌──────────┐
   │ pending │ ──────────────────→│ acknowledged │ ────────────────────→│ resolved │
   └─────────┘                    └──────────────┘                      └──────────┘
```

**Database column:** `review_status` on qc_flags — values: `pending`, `acknowledged`, `resolved`

### Identity Assignment Lifecycle

```
   Auto-detected ──→ raw assignment (confidence + match_method)
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
              human confirms       human reassigns
              (status→approved)    (pigeon_id changes, status→approved)
                                         │
                                    human rejects
                                    (status→rejected)
```

---

## 8. Data Flow

### Video Processing Flow (Conceptual — not yet implemented in code)

```
User adds video paths → POST /api/videos/process
                              │
                              ▼
                     Videos inserted with processing_status='queued'
                              │
                              ▼ (future: background worker)
                     SAM3 detection → masks per frame
                              │
                              ▼
                     Tracking → object IDs across frames
                              │
                              ▼
                     Identity assignment → video_assignments table
                              │
                              ▼
                     Feature extraction → features table
                              │
                              ▼
                     QC checks → qc_flags table
                              │
                              ▼
                     processing_status='completed'
```

### Review Flow

```
Home dashboard shows attention count
         │
         ▼
User clicks "Review Now" → Review page
         │
         ├──→ Identity review: one pigeon at a time
         │         │
         │         ▼
         │    Confirm/reassign → video_assignments.review_status = 'approved'
         │                     → identity_reviews audit log entry
         │
         ├──→ QC flag review: list of flagged frames
         │         │
         │         ▼
         │    "Looks Fine" → qc_flags.review_status = 'resolved'
         │    "Fix This" → navigate to VideoDetail at that frame
         │
         └──→ Behavior review: confirm/reject detected behaviors
                   │
                   ▼
              behaviors.review_status = 'approved' or 'rejected'
```

### Training Flow

```
Clips extracted from processed videos → clip_library table
         │
         ▼
User labels clips (Tab 2) → behavior_labels table
         │
         ▼
Readiness check: ≥20 clips per class? → GET /training/readiness
         │
         ▼
User configures and launches training → POST /training/start
         │
         ▼
Model registered in model_registry (is_active=0)
         │
         ▼
User activates model → POST /training/models/{id}/activate
         │
         ▼
User applies to all videos → POST /training/reinfer
```

### Heatmap Data Flow

```
features table (centroid_x, centroid_y per frame per pigeon)
         │
         ▼
GET /insights/heatmap?pigeons=Alpha&period=week
         │
         ▼
Backend: filter by pigeon + period JOIN, normalize to 50x50 grid
         │
         ▼
Frontend: HeatmapCanvas renders grid to <canvas> element
         Each cell color = interpolation from white to accent color based on 0-1 value
```

---

## 9. API Client Layer

### How Frontend Calls Backend

All API calls go through `frontend/src/api/client.ts`:

```
Frontend Component
    │
    ▼ calls api function (e.g., getVideos)
    │
    ▼ api function calls get<T>("/videos?sort=date")
    │
    ▼ get() calls request<T>() which calls fetch(`/api/videos?sort=date`)
    │
    ▼ Vite dev proxy rewrites /api → http://localhost:8000/api
    │
    ▼ FastAPI receives GET /api/videos
    │
    ▼ Router handler queries SQLite, returns JSON
    │
    ▼ Response flows back through proxy → request() → get() → component
```

**Error handling:** `request()` checks `res.ok`. If false, attempts to parse `body.detail` from the JSON error response. Throws `ApiError` with status code and message. Components catch this via TanStack Query's `isError` state.

**Caching:** TanStack Query with 30-second staleTime, 2 retries, no refetch on window focus. Individual queries can override (e.g., videos list refetches every 10 seconds).

---

## 10. Error Catalog — Known Gaps and Failure Modes

### Critical Bugs

| ID | Description | Files Involved | Impact |
|----|-------------|---------------|--------|
| BUG-001 | **Export URL double-prefix.** `getExportDownloadUrl()` adds `/api/export/download/` but `data.download_url` from backend already contains this path. Results in 404 on download. | `frontend/src/api/insights.ts` (line: `getExportDownloadUrl`), `frontend/src/pages/Insights.tsx` (export mutation onSuccess) | CSV export download fails |
| BUG-002 | **Missing video features endpoint.** Frontend calls `GET /api/videos/{id}/features?frame_idx=N` but endpoint doesn't exist. | `frontend/src/api/videos.ts` (`getVideoFeatures`), `backend/routers/videos.py` (missing) | VideoDetail shows no per-frame pigeon data |
| BUG-003 | **Missing video track-edits endpoint.** Frontend calls `GET /api/videos/{id}/track-edits` but endpoint doesn't exist. | `frontend/src/api/videos.ts` (`getVideoTrackEdits`), `backend/routers/videos.py` (missing) | VideoDetail edit history always empty |
| BUG-004 | **Review queue links to video_id=0.** Identity review section in ReviewQueue navigates to `/review?type=identity&video_id=0` which won't match any video. | `frontend/src/pages/Review.tsx` (ReviewQueue identity section action) | Identity review flow can't start from queue |

### Missing Features (Spec'd but Not Built)

| ID | Feature | Spec Reference | Status |
|----|---------|---------------|--------|
| GAP-001 | Droppings review tab in Review page | Bridge doc §6 Review Screens | `?type=dropping` route has no handler |
| GAP-002 | Mask/track visual correction editor | Bridge doc §3 (full wireframe spec) | Backend endpoints exist, no frontend UI |
| GAP-003 | Session comparison UI in Insights | UX spec Insights section, Bridge doc §5 | Backend endpoint exists, frontend doesn't call it |
| GAP-004 | Onboarding wizard for first-time users | UX spec "First-Time Experience" section | Not built — users land on empty dashboard |
| GAP-005 | Batch identity confirmation | Bridge doc §4 Batch Workflows | Not built |
| GAP-006 | Behavior review listing/flow | Bridge doc §6 Review Screens | Missing GET endpoint for behaviors by status |
| GAP-007 | Status labels don't match spec language | Bridge doc §2 "Frontend Implementation Rule" | `raw`→"Raw" instead of "Not yet checked" |

### Inconsistencies

| ID | Description | Files |
|----|-------------|-------|
| INC-001 | Training router uses aiosqlite (async), all others use synchronous sqlite3. Works but inconsistent. | `backend/routers/training.py` vs all other routers |
| INC-002 | CORS origin hardcoded to `localhost:5173` despite .env.example suggesting configurable ports. | `backend/main.py` |
| INC-003 | `reviewer` / `editor` fields default to empty strings, making audit trail useless. | All review/edit endpoints |
| INC-004 | Attention count doesn't include behaviors with review_status='raw'. | `backend/routers/review.py` (`attention_count`) |

---

## 11. Dependency Map

### Backend: What Each Router Depends On

| Router | Database Tables Read | Database Tables Written | External Dependencies |
|--------|---------------------|----------------------|----------------------|
| `videos.py` | videos | videos | Filesystem (data/frames/) |
| `pigeons.py` | pigeons, video_assignments, features, behaviors | pigeons | None |
| `insights.py` | features, behaviors, pairwise, droppings, videos, video_assignments | None | None |
| `review.py` | video_assignments, identity_reviews, qc_flags, track_edits, videos, behaviors, droppings, droppings_reviews | video_assignments, identity_reviews, qc_flags, track_edits, behaviors, droppings, droppings_reviews | None |
| `training.py` | clip_library, behavior_labels, model_registry, videos | behavior_labels, model_registry | None |
| `export.py` | features, behaviors, pairwise, videos | None | Filesystem (data/exports/) |
| `stats.py` | videos, features, identity_reviews, model_registry | None | None |

### Frontend: What Each Page Depends On

| Page | API Modules Used | Components Used | Shared Hooks |
|------|-----------------|----------------|-------------|
| Home | stats | LoadingState, EmptyState | usePageTitle |
| Videos | videos | VideoCard, LoadingState, EmptyState, AddVideosModal | usePageTitle |
| VideoDetail | videos, review | StatusBadge, LoadingState | usePageTitle |
| Pigeons | pigeons | PigeonCard, LoadingState, EmptyState, RegisterPigeonModal | usePageTitle |
| PigeonProfile | pigeons | (inline charts via Recharts) | usePageTitle |
| Insights | insights, pigeons | (inline HeatmapCanvas, SocialMap) | usePageTitle |
| Review | review, stats, videos, pigeons | StatusBadge, LoadingState, Toast | usePageTitle, useToast |
| Training | training | LoadingState, EmptyState | usePageTitle |
| LabSetup | (none) | (none) | usePageTitle |

### CSS Theme Variables (defined in globals.css, used everywhere)

| Variable | Value | Used For |
|----------|-------|----------|
| `--color-bg` | #FAFAF9 | Page background, input backgrounds |
| `--color-surface` | #FFFFFF | Cards, panels, modals |
| `--color-border` | #E7E5E4 | All borders, dividers |
| `--color-text-primary` | #1C1917 | Headings, body text, emphasis |
| `--color-text-secondary` | #78716C | Captions, labels, muted text |
| `--color-accent` | #0D9488 | Buttons, links, active states, charts |
| `--color-success` | #16A34A | Approved/confirmed states, success toasts |
| `--color-warning` | #F59E0B | Pending states, attention items, warning banners |
| `--color-error` | #DC2626 | Rejected states, error toasts, validation errors |

---

## 12. Troubleshooting Decision Tree

### "The page is blank / shows a white screen"

```
→ Check browser console for JavaScript errors
  → If "Failed to fetch" or network error:
    → Is the backend running? Check http://localhost:8000/api/health
      → If no: start backend with `uvicorn main:app --reload --port 8000`
      → If yes: check Vite proxy config in vite.config.ts
  → If React error:
    → ErrorBoundary should catch it — check if it shows "Something went wrong"
    → If ErrorBoundary not showing, check main.tsx for missing providers
```

### "Data isn't showing up on a page"

```
→ Which page?
  → Home: Check if seed data was run (python seed_data.py)
    → Check /api/stats/today — are counts > 0?
    → Check /api/review/attention?limit=5 — returns items?
  → Videos: Check /api/videos — returns videos array?
  → VideoDetail pigeon cards empty:
    → This is BUG-002 — GET /videos/{id}/features endpoint doesn't exist
  → VideoDetail edit history empty:
    → This is BUG-003 — GET /videos/{id}/track-edits endpoint doesn't exist
  → Insights heatmap blank:
    → Check /api/insights/heatmap — does grid have any non-zero values?
    → If all zeros: no features data exists for the selected period/pigeons
  → Pigeon profile zones/behaviors empty:
    → Profile zones come from behaviors table WHERE review_status='approved'
    → If no behaviors are approved, this will be empty
    → Behaviors come from /pigeons/{id}/behaviors which joins on processed_at date
```

### "A review action isn't working"

```
→ Which action?
  → Identity confirm: Check /api/review/identity POST
    → Verify assignment_id exists in video_assignments
    → Verify action is "confirm", "reject", or "reassign"
  → QC flag resolve: Check /api/review/qc-flag POST
    → Verify flag_id exists in qc_flags
  → Batch QC resolve: The frontend loops through flags sequentially
    → If it's slow, this is expected — no batch endpoint exists
```

### "Export CSV download fails"

```
→ This is BUG-001 — double-prefixed URL
→ Check browser Network tab — the download URL will look like:
  /api/export/download//api/export/download/features_abc123.csv
→ Fix: in insights.ts, getExportDownloadUrl should return the path as-is
```

### "Training readiness shows 0 clips for all classes"

```
→ Check if behavior_labels table has any rows: 
  SELECT COUNT(*) FROM behavior_labels
→ If 0: no clips have been labeled yet
→ Check if clip_library has entries:
  SELECT COUNT(*) FROM clip_library
→ If 0: no clips have been extracted from videos (future feature)
→ If using seed data: default seed_data.py does NOT create clips or labels
```

### "The attention bell always shows 0"

```
→ Check /api/review/attention/count
→ It counts: qc_flags WHERE review_status='pending' + video_assignments WHERE review_status='raw' + droppings WHERE review_status='raw'
→ NOTE: It does NOT count behaviors needing review (INC-004)
→ If using seed data: should show 2 QC flags + 8 assignments = total of 10
```

### "Processing a video stays at 'queued' forever"

```
→ This is expected — the actual processing pipeline (SAM3 detection, tracking, etc.) 
  is NOT implemented in the current codebase
→ POST /api/videos/process only inserts rows with processing_status='queued'
→ No background worker exists to process them
→ For development: use seed_data.py which creates videos with processing_status='completed'
```

---

## Appendix A: Seed Data Summary

Running `python backend/seed_data.py` creates:

| Entity | Count | Details |
|--------|-------|---------|
| Pigeons | 4 | Alpha (red band L), Beta (blue band L), Gamma (green band R), Delta (no marker) |
| Videos | 2 | session_001_overhead.mp4 (1800 frames), session_002_side.mp4 (2400 frames). Both completed. |
| Video Assignments | 8 | 4 pigeons × 2 videos. Random confidence 0.65-0.98. All review_status='raw'. |
| QC Flags | 2 | id_swap_detected (high), low_confidence_id (medium). Both pending. |
| Features | 80 | 10 sample frames × 4 pigeons × 2 videos. Random positions and velocities. |
| Behaviors | 8 | 1 per pigeon per video. Random behavior type. All review_status='raw'. |
| Pairwise | 8 | 4 pairs × 2 videos. Random distances. |
| Clips | 0 | None created by default seed |
| Labels | 0 | None created by default seed |
| Models | 0 | None created by default seed |
| Droppings | 0 | None created by default seed |

---

## Appendix B: Port and URL Reference

| Service | URL | Purpose |
|---------|-----|---------|
| Backend API | http://localhost:8000 | FastAPI server |
| Backend API docs | http://localhost:8000/docs | Swagger UI (auto-generated) |
| Frontend dev server | http://localhost:5173 | Vite dev server with HMR |
| Frontend → Backend proxy | /api/* → localhost:8000/api/* | Configured in vite.config.ts |
| Frame images | /api/videos/{id}/frame/{n} | Served from data/frames/{id}/{n:06d}.jpg |
| Export downloads | /api/export/download/{filename} | Served from data/exports/{filename} |

---

## Appendix C: Key Constants and Magic Numbers

| Constant | Value | Location | Purpose |
|----------|-------|----------|---------|
| MIN_CLIPS_PER_CLASS | 20 | `backend/routers/training.py` | Minimum labeled clips per behavior class before training is allowed |
| Heatmap grid size | 50 × 50 | `backend/routers/insights.py`, `backend/routers/pigeons.py` | Resolution of all heatmap grids |
| Estimated FPS for pairwise duration | 30 | `backend/routers/insights.py` | Used to convert frame counts to seconds in pairwise proximity |
| TanStack Query staleTime | 30,000ms | `frontend/src/main.tsx` | How long cached data is considered fresh |
| TanStack Query retry | 2 | `frontend/src/main.tsx` | Number of retry attempts on failed queries |
| Videos list poll interval | 10,000ms | `frontend/src/pages/Videos.tsx` | How often the video list refetches for status updates |
| TopBar attention poll interval | 30,000ms | `frontend/src/components/layout/TopBar.tsx` | How often the bell badge updates |
| Training status poll interval | 3,000ms | `frontend/src/pages/Training.tsx` | How often training progress is checked (when active) |
| Toast auto-dismiss | 4,000ms | `frontend/src/components/ui/Toast.tsx` | How long toasts stay visible |

---

## Appendix D: File-to-File Relationship Quick Reference

**"If I change X, what else might break?"**

| If You Change... | Also Check... |
|-----------------|--------------|
| `database.py` (schema) | `seed_data.py`, all backend routers, frontend types |
| `main.py` (routes) | Frontend API client expectations |
| Any router endpoint signature | Corresponding `frontend/src/api/*.ts` function |
| `frontend/src/types/index.ts` | All pages and API modules that import types |
| `frontend/src/statusUtils.ts` | `StatusBadge.tsx`, `VideoCard.tsx`, anywhere badges appear |
| `frontend/src/api/client.ts` | Every API module (all import from client) |
| `frontend/src/styles/globals.css` (theme vars) | Every component using `bg-*`, `text-*`, `border-*` classes |
| `frontend/src/App.tsx` (routes) | Sidebar.tsx (nav links must match routes) |
| `vite.config.ts` (proxy) | All API calls fail if proxy misconfigured |
| `backend/requirements.txt` | Backend startup may fail if deps missing |
| `frontend/package.json` | Frontend build may fail if deps missing |
