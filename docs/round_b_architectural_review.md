# Round B: Architectural Review

Date: 2026-05-12
Branch: `codex/round-b-architectural-review`

## Summary

| Item | Decision | Evidence |
| --- | --- | --- |
| 1. Memory bank growth across chunks | Fixed cleanup/logging; requires GPU runtime verification for VRAM baseline | `backend/routers/videos.py` uses one `VideoProcessor` per queued job, and `VideoProcessor` keeps one lazy `SAM3Wrapper`; `backend/services/sam3.py` now calls `torch.cuda.empty_cache()` and logs allocated/reserved memory after every `close_video_session()`. |
| 2. Cross-chunk identity continuity | Fixed with Option A quick-confirm | Chunk metadata is now persisted in `videos`; Identity Review can apply “same as previous chunk” suggestions from the prior reviewed sibling chunk. |
| 3. Research report aggregation across chunks | Fixed | Research report now groups by logical video/chunk group and reports one logical `Pigeon1.mp4` row with chunk counts instead of three independent video rows. |
| 4. Partial completion when a chunk fails | Fixed | Chunk jobs already continued after a failed chunk, but job status and UI aggregation were incomplete; list/status endpoints now return aggregate chunk status and failed-group retry queues only failed chunks. |
| 5. Production frontend source paths | Correct as-is | `npm.cmd run build` produced no source maps and no `jdeste02`, `@fs`, or absolute developer path matches in `frontend/dist`; no cache artifacts are tracked by Git. |

## 1. Memory Bank Growth Across Chunks

Current behavior found:
- `_run_processing_job()` creates one `VideoProcessor()` for the queued list, so auto-chunked siblings run sequentially in the same backend Python process against the same `VideoProcessor` instance.
- `VideoProcessor` lazy-loads and retains one `self._sam3` wrapper across those chunks.
- `process_video()` starts a fresh SAM3 video session for each chunk and calls `close_video_session()` after successful propagation, inside the propagation failure path, and again from `finally` if a session is still open.
- Before this round, `close_video_session()` asked SAM3 to close the session but did not explicitly call `torch.cuda.empty_cache()` or log allocator state.

Correctness:
- Session closure was mostly reliable, but CUDA cache cleanup and objective VRAM evidence were absent.

Fix:
- `SAM3Wrapper.close_video_session()` now always runs `_empty_cuda_cache()` in `finally`.
- The cleanup log prints allocated/reserved CUDA memory before and after cache emptying:
  `SAM3 CUDA cleanup after close_video_session session_id=... allocated_gb X -> Y reserved_gb A -> B`

Requires GPU runtime verification:

```powershell
cd C:\Users\jgraziol\Documents\pigeonlab-v2
start.bat
# Process an auto-chunked video, then in another PowerShell:
Select-String -Path .\data\logs\backend-*.log -Pattern "SAM3 CUDA cleanup" | Select-Object -Last 20
nvidia-smi --query-gpu=timestamp,memory.used --format=csv -l 5
```

Expected: after each chunk closes, the cleanup log appears and `nvidia-smi` drops back near the model-only baseline before the next chunk begins.

## 2. Cross-Chunk Identity Continuity

Current behavior found:
- Auto-chunking produced separate `videos` rows and separate `video_assignments`.
- Chunk relationship fields were present only in transient Python dicts and were not inserted into the database.
- Identity Review had no way to know chunk 2 followed chunk 1, so a 3-chunk/4-pigeon upload could require 12 separate confirmations.

Correctness:
- Broken/absent.

Fix:
- Added persisted chunk metadata to `videos`: `logical_video_name`, `original_source_path`, `chunk_group_id`, `chunk_index`, `chunk_count`, `chunk_seconds`.
- Added `GET /api/review/identities/chunk-carryover`.
- Added `POST /api/review/identities/same-as-previous-chunk`.
- Added Identity Review UI action: “Same as previous chunk.”
- The backend maps same `video_obj_id` first, then falls back to sorted track order only when there is a one-to-one count match. It updates `video_assignments`, `features`, `behaviors`, and `pairwise` through the existing identity replacement helper.

Test evidence:

```powershell
python backend\tests\test_round_b_architecture.py
```

Result: 3 tests passed, including previous-chunk carryover and analysis row updates.

## 3. Research Report Aggregation Across Chunks

Current behavior found:
- The report queried raw `videos` rows directly.
- With chunked uploads, that would list `Pigeon1_part000.mp4`, `Pigeon1_part001.mp4`, and `Pigeon1_part002.mp4` separately.
- Heatmap, zone occupancy, and pairwise summaries already aggregate over `features`/`pairwise`; after identity carryover, those rows naturally merge by confirmed pigeon identity.

Correctness:
- Video section was wrong for the user's mental model: one uploaded video should be one logical report section.

Fix:
- Research report video summary now groups by `COALESCE(chunk_group_id, 'video-' || video_id)`.
- The report now emits a “Logical Videos” table with `logical_video_name`, `chunks`, `completed_chunks`, `failed_chunks`, aggregate frames/FPS/status, and included chunk files.

Test evidence:

```powershell
python backend\tests\test_round_b_architecture.py
```

Result: seeded three chunks report as one logical `Pigeon1.mp4` row with `chunks = 3` and `processing_status = partial`.

## 4. Partial Completion When a Chunk Fails

Current behavior found:
- `_run_processing_job()` already catches per-video exceptions and continues processing later queued entries.
- However, mixed success/failure reported the job as `completed`, not `partial`.
- The Videos UI showed chunks as independent rows without aggregate chunk status.
- Retry existed only for one `video_id`, which is correct for a failed chunk but not discoverable as a logical group action.

Correctness:
- Partially correct internally, incomplete in status/UI.

Fix:
- `_run_processing_job()` now returns `partial` when at least one chunk succeeds and at least one fails.
- List/status responses now include chunk group aggregate fields:
  `chunk_group_total`, `chunk_group_completed`, `chunk_group_failed`, `chunk_group_status`, `chunk_group_status_label`.
- Videos cards show logical video name, chunk index, and aggregate status such as `Partial (2/3, 1 failed)`.
- Added `POST /api/videos/chunk-groups/{chunk_group_id}/retry-failed`, which queues only failed chunks in that group.

Test evidence:

```powershell
python backend\tests\test_round_b_architecture.py
```

Result: seeded group reports `Partial (2/3, 1 failed)`.

## 5. Frontend Source Paths in Production Builds

Current behavior found:
- `npm run build` under PowerShell hit the standard `npm.ps1` execution policy issue, so verification used `npm.cmd run build`.
- Production build completed successfully.
- `frontend/dist` contains no `*.map` files.
- Search found no `jdeste02`, `@fs`, `C:\Users`, `C:/Users`, local repo absolute path, `/Users/`, or `sourceMappingURL` references.
- No `dist`, `build`, `.vite`, `.turbo`, or `node_modules` artifacts are tracked by Git.

Correctness:
- Correct as-is. The v2 `@fs/C:/Users/jdeste02/...` symptom was a dev-server/cache artifact, not a current production build leak.

Verification commands:

```powershell
cd frontend
npm.cmd run build
cd ..
Get-ChildItem -Recurse frontend\dist -Filter *.map | Measure-Object | Select-Object -ExpandProperty Count
rg -n "jdeste02|@fs|C:\\Users|C:/Users|E:\\AI Models|/Users/|sourceMappingURL" frontend\dist
git ls-files | Select-String -Pattern '(^|/)(dist|build|\.vite|\.turbo|node_modules)(/|$)'
```

Observed locally:
- Build passed.
- Source map count: `0`.
- Path search: no matches.
- Tracked cache/artifact search: no matches.

## Local Verification Run

```powershell
python backend\tests\test_round_b_architecture.py
python -m py_compile backend\routers\videos.py backend\routers\review.py backend\routers\export.py backend\services\sam3.py backend\database.py backend\tests\test_round_b_architecture.py
cd frontend
npm.cmd run build
```

Results:
- `backend\tests\test_round_b_architecture.py`: PASS, 3 tests.
- `py_compile`: PASS.
- `npm.cmd run build`: PASS.
