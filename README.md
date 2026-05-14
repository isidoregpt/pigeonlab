> ⚠️ This software is free for academic and research use. Commercial use,
> including selling derivative works, is prohibited without a license.
> See [LICENSE](./LICENSE) for details.

# PigeonLab

A full-stack web application for pigeon behavioral tracking from video. Upload videos, track pigeon positions and identities, review QC flags, visualize zone heatmaps and social networks, and train behavior classification models.

## Prerequisites

- **Python 3.12** with `pip` for SAM3.1 video processing on Windows
- **Node.js 18+** with `npm`
- **NVIDIA CUDA GPU** for SAM3.1 inference
- **FFmpeg** on PATH for long-video ingestion. Prefer a permanent install
  location such as `C:\ffmpeg\bin`; Downloads, Desktop, and Temp locations are
  easy to clean up accidentally.
- **Ollama** for optional Gemma reviewer automation

## Quick Start

### One-Click Workstation Install

On the Threadripper + RTX A6000 workstation, double-click:

```powershell
install.bat
```

The installer creates an optimized `.env`, installs Python/Node/Git/FFmpeg/Ollama
with WinGet when missing, creates `backend/venv`, installs the CUDA PyTorch
stack pinned to the workstation-tested `torch==2.11.0+cu126` family, installs
SAM3.1 from GitHub, runs `npm install`, pulls the configured Gemma model with
Ollama, optionally downloads the gated SAM3.1 checkpoint from cached
Hugging Face auth, and
runs the setup checker. Installer logs are written to `data/logs/install-*.log`.
The workstation profile assumes a 48GB GPU; for 24GB or smaller GPUs, see
[docs/memory-model.md](./docs/memory-model.md).

After install, start the app with:

```powershell
start.bat
```

If troubleshooting is needed, double-click `diagnostics.bat`. It creates a
redacted zip under `data/logs/diagnostics/` with setup checks, hardware info,
package versions, and recent logs.

### Startup Loading Art

Drop your loading-screen images into:

```text
frontend/public/loading
```

Use PNG, JPG, JPEG, WEBP, or GIF files. The next `start.bat` run refreshes
`frontend/public/loading/manifest.json` automatically, and the app fades through
one image before revealing the main workspace.

### Backend

```bash
cd backend
pip install -r requirements.txt
python seed_data.py          # optional: populate demo data
uvicorn main:app --reload --port 8000
```

### SAM3.1 Setup

SAM3.1 uses the official `facebookresearch/sam3` package and a local
checkpoint. On Windows, use Python 3.12 for the virtual environment. The
installer handles this automatically, including the `triton-windows`, NumPy, and
OpenCV versions that avoid the common SAM3.1 Windows import/runtime failures.
Run `hf auth login` before `install.bat` if you want the installer to download
the gated checkpoint automatically. The installer no longer asks you to paste a
hidden token into cmd.exe because that paste path is unreliable on Windows.
After installing `backend/requirements.txt`, install the SAM3 repo:

```bash
pip install git+https://github.com/facebookresearch/sam3.git
hf auth login
python backend/scripts/download_sam3.py --version sam3.1
python backend/scripts/setup_check.py
```

### Gemma Reviewer Setup

Gemma review is optional and defaults to human review mode. When enabled, the
pipeline samples processed frames, sends them to a local Ollama vision model,
and writes behavior, dropping, object, facing-direction, QC, and identity
suggestions into the review tables.

```bash
ollama pull gemma4:e4b
```

Then open Settings -> Gemma Reviewer and choose:

- `Off`: human review only.
- `Assist`: Gemma queues suggestions for human approval.
- `Auto`: Gemma approves confident labels and leaves uncertain items for review.

Useful environment overrides:

```bash
PIGEONLAB_GEMMA_REVIEW_MODE=assist
PIGEONLAB_GEMMA_MODEL=gemma4:e4b
PIGEONLAB_GEMMA_BASE_URL=http://localhost:11434
PIGEONLAB_GEMMA_SAMPLE_SECONDS=15
PIGEONLAB_GEMMA_MAX_FRAMES=20
PIGEONLAB_GEMMA_CONFIDENCE_THRESHOLD=0.65
```

### Workstation Optimization

The installer writes defaults tuned for a 64-core Threadripper, 128GB RAM, RTX
A6000 48GB, and fast NVMe storage:

- Keep `PIGEONLAB_UVICORN_WORKERS=1` so SAM3/Gemma are not loaded multiple times into VRAM.
- Use `PIGEONLAB_SAM3_COMPILE=0`, `PIGEONLAB_SAM3_MULTIPLEX_COUNT=16`, and
  `PIGEONLAB_SAM3_MAX_OBJECTS=8`. The native SAM3.1 checkpoint expects 16-way
  multiplexing, and torch.compile currently selects Triton kernels that exceed
  the RTX A6000 shared-memory limit.
- Keep `PIGEONLAB_SAM3_OFFLOAD_VIDEO_TO_CPU=1` and
  `PIGEONLAB_SAM3_FALLBACK_PER_FRAME=0` so long-video failures are surfaced
  clearly instead of silently degrading to non-temporal per-frame detections.
- Keep `PIGEONLAB_REID_ENABLED=1` to merge short within-chunk track fragments
  before exports and Identity Review are populated. The default Re-ID profile
  allows up to 90 frames of absence and uses conservative appearance matching
  when a pigeon leaves and re-enters the frame.
- Use `PIGEONLAB_TORCH_DTYPE=auto`; the backend chooses CUDA bfloat16 when supported and float16 otherwise.
- Keep `PIGEONLAB_SAM3_ENABLE_WINDOWS_PATCHES=1` on Windows. It applies narrow SAM3.1 compatibility patches for the native multiplex predictor and SDPA fallback kernels.
- Use `PIGEONLAB_FFMPEG_THREADS=32` and `PIGEONLAB_FFMPEG_USE_NVENC=1` for FFmpeg fallback re-encoding.
- Use `PIGEONLAB_OPENCV_THREADS=32`, `OMP_NUM_THREADS=32`, and `MKL_NUM_THREADS=32` while leaving CPU headroom for the OS.

See [docs/memory-model.md](./docs/memory-model.md) for the SAM3.1 CPU RAM/VRAM
budget, auto-chunking rationale, and recommended per-GPU overrides.

### Logs

Runtime logs are intentionally verbose:

- `data/logs/pigeonlab.log`: rotating human-readable backend log.
- `data/logs/pigeonlab.jsonl`: rotating JSONL log for LLM-assisted debugging.
- `data/logs/backend-*.log`: backend process output from `start.bat`.
- `data/logs/frontend-*.log`: frontend process output from `start.bat`.
- `data/logs/install-*.log`: full installer transcript.

### Long Video Folder Ingest

PigeonLab can watch a simple local workflow: place new source videos in
`data/videos/inbox`, split them into SAM3-sized chunks under
`data/videos/output`, and optionally archive the originals under
`data/videos/archive`.

Direct uploads and path-based video adds also auto-split videos longer than
`PIGEONLAB_VIDEO_CHUNK_SECONDS` when `PIGEONLAB_VIDEO_AUTO_CHUNK_UPLOADS=1`.

Install FFmpeg, then use the Videos page "Import Folder" action or call the API:

```bash
curl -X POST http://localhost:8000/api/videos/import-folder \
  -H "Content-Type: application/json" \
  -d "{\"chunk_seconds\":60,\"process_now\":true,\"expected_pigeon_count\":4,\"text_prompt\":\"pigeon\",\"limit\":10}"
```

Useful environment overrides:

```bash
PIGEONLAB_VIDEO_INPUT_DIR=E:/PigeonLab/input
PIGEONLAB_VIDEO_OUTPUT_DIR=E:/PigeonLab/output
PIGEONLAB_VIDEO_ARCHIVE_DIR=E:/PigeonLab/archive
PIGEONLAB_VIDEO_CHUNK_SECONDS=60
PIGEONLAB_VIDEO_AUTO_CHUNK_UPLOADS=1
```

### Where Files Live

- Browser uploads are copied to `data/videos/uploads` with a unique prefix.
- Auto-chunked uploads and path-based adds write chunk files under
  `data/videos/output/<source-name>_<timestamp>/`.
- Folder import reads from `data/videos/inbox`, writes chunks to
  `data/videos/output`, and only moves originals to `data/videos/archive` when
  archive mode is enabled.
- Extracted JPG frames for the Watch view live under `data/frames/<video_id>/`.
- Deleting a video removes database rows and extracted frames. Source uploads
  and generated chunk files are intentionally left on disk so researchers do not
  lose original media by clicking Delete in the UI.

### Research Reports

The Insights page includes a **Research Report** export for publication prep and
lab review. It creates an HTML report plus a Markdown copy and manifest under
`data/exports`, summarizing videos, review scope, identities, per-pigeon
tracking, zone occupancy, behaviors, pairwise proximity, droppings, QC flags,
and runtime settings. Use the CSV export alongside the report for statistical
analysis in R, Python, SPSS, or paper reproducibility packages.

### Research Workflows

PigeonLab supports rotation-style social behavior studies where one bird is
cycled into or out of an enclosure while researchers measure how the remaining
birds respond. Use Identity Review to confirm the same named pigeons across
chunks/sessions, then compare Pairwise Map, zone occupancy, heatmaps, and the
Research Report across baseline, rotation, and recovery videos.

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
│   │   ├── ffmpeg_ingest.py # Folder import and chunking
│   │   ├── gemma_reviewer.py # Optional Ollama/Gemma review pass
│   │   ├── frame_extractor.py  # OpenCV frame extraction
│   │   ├── tracker.py       # Multi-object tracker
│   │   ├── feature_extractor.py  # Spatial features
│   │   └── qc_rules.py      # Automated QC checks
│   └── scripts/
│       ├── download_sam3.py # SAM3 checkpoint downloader
│       └── setup_check.py   # Environment diagnostic
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
