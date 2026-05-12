# Round D PR1: Correctness Fixes

## Shipped

- Removed `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` from the Windows workstation `.env` template.
- Added defensive Windows startup sanitization that strips `expandable_segments` before Torch imports if an older `.env` still contains it.
- Documented the Windows allocator limitation in `docs/memory-model.md`.
- Added SAM3 runtime patch tracking and surfaced it through `/api/health/full` as `sam3_patches`.
- Added an explicit SAM3 loader wrapper that defaults `load_video_frames_from_video_file_using_cv2(..., offload_video_to_cpu=True)`.
- Added startup patch logging, including `Applied SAM3.1 load_video_frames offload_video_to_cpu default patch`.
- Added `completed_no_detections` status for chunks that finish the pipeline with zero tracks and zero feature rows.
- Updated logical-video aggregate status and Research Report output so no-detection chunks are visible instead of being counted as normal completions.
- Changed Video Detail metadata from `Pigeons` to `Tracks` and added `Confirmed Pigeons` after identity review.
- Added `track_count` and `confirmed_pigeon_count` to `GET /api/videos/{id}`.

## Verification

- PASS: `python -m py_compile backend/env_loader.py backend/main.py backend/routers/videos.py backend/routers/export.py backend/services/sam3.py backend/services/video_processor.py backend/scripts/setup_check.py backend/tests/test_round_b_architecture.py`
- PASS: `python backend/tests/test_round_b_architecture.py`
- PASS: `python -m backend.tests.smoke_test --offline`
- PASS: `npm.cmd run build`
- PASS: `python -c "from backend.scripts.setup_check import collect_runtime_diagnostics; ..."` confirmed `/api/health/full` source includes `sam3_patches`.
- PASS: `git diff --check`

## Requires Workstation Verification

Run after pulling this PR on Windows + A6000:

```powershell
cd C:\Users\jgraziol\Documents\pigeonlab-v3
start.bat
Select-String -Path data\logs\backend-*.log -Pattern "expandable_segments|Applied SAM3.1|SAM3 runtime patches active"
curl http://localhost:8000/api/health/full
```

Expected:

- No `expandable_segments not supported on this platform` warning.
- Log includes all three SAM3 patch lines.
- Health JSON includes `sam3_patches.load_video_frames_offload_video_to_cpu_default: true` after startup.
