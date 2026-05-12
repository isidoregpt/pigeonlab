# Round C PR1: Operational Features

## Shipped

- Added `GET /api/health/full`, a support-friendly diagnostic JSON snapshot with SAM3 state, GPU/VRAM details, Python/Torch/CUDA versions, hardware profile, failed-video error context, active processing count, selected `PIGEONLAB_*` settings, FFmpeg status, Ollama reachability, and Gemma model presence.
- Added a **Copy diagnostics** button on Lab Setup that fetches `/api/health/full`, pretty-prints the JSON, and copies it to the clipboard for support tickets.
- Added `POST /api/videos/{video_id}/cancel` with a new `cancelled` status. Processing jobs now receive cooperative cancellation checks, close SAM3 sessions, clear partial derived rows/frames, and preserve completed chunks while cancelling queued or in-flight remaining chunks.
- Added a Cancel button to processing video cards with a confirmation dialog.
- Added `python -m backend.tests.smoke_test` for workstation end-to-end validation and `python -m backend.tests.smoke_test --offline` for fixture/database validation in non-CUDA sandboxes.
- Added a checked-in synthetic smoke fixture at `backend/tests/fixtures/smoke_video.mp4` (5 seconds, 150 frames, under 1 MB) plus a regeneration script.
- Added optional setup-check integration via `PIGEONLAB_RUN_SMOKE_TEST=1`.
- Added [docs/memory-model.md](./memory-model.md) and linked it from the README.

## Verification

- PASS: `python -m backend.tests.smoke_test --offline`
  - Validated fixture metadata: 160x120, 150 frames, 5.0 seconds, 8,992 bytes.
  - Exercised SQLite insert/readback path with a temporary database.
- PASS: `python -m py_compile backend/main.py backend/routers/videos.py backend/services/sam3.py backend/services/video_processor.py backend/scripts/setup_check.py backend/tests/smoke_test.py`
- PASS: `npm.cmd run build`
- Not run: `python -m pytest backend/tests/test_round_b_architecture.py backend/tests/test_flow.py`
  - This sandbox Python does not have `pytest` installed and there is no local backend virtual environment.

## Requires Workstation Verification

Run this after installing on the Windows + A6000 workstation:

```powershell
cd C:\Users\jgraziol\Documents\pigeonlab-v3
backend\venv\Scripts\python.exe -m backend.tests.smoke_test
```

Expected result: `PASS full smoke test` with timing breakdown under about 60 seconds.

Manual cancellation check:

1. Start a real video processing job.
2. Click **Cancel** on the processing card.
3. Confirm the video moves to `Cancelled`.
4. Confirm GPU activity falls after the next SAM3 propagation packet and no partial features remain for that video.
