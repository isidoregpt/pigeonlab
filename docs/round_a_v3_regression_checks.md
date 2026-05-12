# Round A: v3 Regression Checks

Date: 2026-05-12

Validation command:

```powershell
python -m unittest backend.tests.test_round_a_regressions -v
```

Result:

```text
Ran 5 tests
OK
```

## 1. `PYTORCH_CUDA_ALLOC_CONF` propagates before torch import

Status: PASS

Evidence:

- Added an early startup log line in `backend/logging_config.py` before the system snapshot probes torch:
  - `Pre-torch PYTORCH_CUDA_ALLOC_CONF=<value> torch_imported=<bool>`
- Regression test loads the default install env contents from `.env.example`, configures logging, and asserts:
  - `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
  - the startup log contains `Pre-torch PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
  - the startup log records `torch_imported=False`

Fix applied:

- Added the pre-torch allocator log before `log_system_snapshot()` imports/probes torch.

## 2. `offload_video_to_cpu=True` reaches the SAM3 video loader

Status: PASS

Evidence:

- Regression test confirms `SAM3Wrapper.start_video_session()` sends:
  - `"offload_video_to_cpu": True`
- Regression test also simulates the SAM3 io_utils loader and confirms the patched loader defaults to CPU offload and does not enter the `.cuda()` path when SAM3 does not explicitly pass the kwarg.

Fix applied:

- Added a fallback runtime patch in `_apply_sam3_runtime_patches()`:
  - wraps `sam3.model.io_utils.load_video_frames_from_video_file_using_cv2`
  - defaults `offload_video_to_cpu=True` when the dispatcher omits it
  - preserves explicit caller-provided values

## 3. Auto-chunking happens before SAM3 sees the file

Status: PASS

Evidence:

- Upload/process route calls `_auto_chunk_entries()` before creating processing job entries.
- Regression test stubs a long video and verifies:
  - the original long input path is replaced by chunk paths
  - chunk entries are created before processing is queued
  - the requested upload-time log line is emitted:
    - `Auto-chunking long.mp4: 3 chunks of 60s each`

Fix applied:

- Added the requested auto-chunking log line in `backend/routers/videos.py`.

## 4. `install.bat` PowerShell venv bug

Status: PASS for the venv creation regression path; full install not executed in this sandbox

Evidence:

- Regression test runs `install.bat` in a fresh temporary folder.
- The test uses a fake `py` launcher shim because this Codex sandbox does not have Python 3.12 installed.
- The test confirms:
  - `install.bat` invokes the venv creation path without manual intervention
  - `backend\venv\Scripts\python.exe` is created
  - the launcher receives the intended args: `"-3.12" "-m" "venv"`

Fix applied:

- Changed venv creation in `install.ps1` to run through `cmd.exe /d /c`.
- Added comments explaining why: the Python launcher must receive `-3.12` as a literal argv token instead of being mis-handled by older PowerShell hosts.
- Added `PIGEONLAB_INSTALL_STOP_AFTER_VENV` as a verification-only installer stop point so the venv bug can be regression-tested without downloading the full GPU stack.

Limit:

- A full clean workstation install was not run here because the sandbox lacks Python 3.12 and cannot perform the multi-GB CUDA/SAM3 dependency install. The original bug's venv creation step is covered by the automated regression test.

## 5. Cascade delete removes dependent rows

Status: PASS for cascade cleanup logic; real SAM3 video processing not executed in this sandbox

Evidence:

- Regression test creates a completed-video database fixture with dependent rows in the actual schema:
  - `videos`
  - `features`
  - `pairwise`
  - `behaviors`
  - `clip_library`
  - `behavior_labels`
  - `droppings`
  - `droppings_reviews`
  - `qc_flags`
  - `review_tasks`
  - `ai_observations`
  - `video_assignments`
  - `identity_reviews`
  - `track_edits`
- Test calls the new `DELETE /api/videos/{video_id}` handler.
- Test confirms zero remaining rows/orphans in each dependent table.

Fix applied:

- No cascade-delete code change was required; the existing explicit cleanup passed.

Limit:

- This repository schema does not currently contain separate `detections` or `tracks` tables. The test covers the actual track-related tables present today: `video_assignments` and `track_edits`.
- A real GPU SAM3 process-to-completion run was not possible in this sandbox; the cascade claim was verified with a representative completed-video database fixture.
