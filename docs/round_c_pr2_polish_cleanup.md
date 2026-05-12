# Round C PR2: Polish and Cleanup

## Shipped

- Updated README startup loading art text to remove the stale Skip-button reference.
- Chose the lightweight per-GPU default strategy: keep the installer on the 48GB workstation profile, document 24GB/16GB overrides in `docs/memory-model.md`, and print an installer warning that smaller GPUs should use those overrides.
- Documented where uploaded videos, auto-chunked files, folder-import files, and extracted frames live on disk.
- Documented that video deletion removes database rows and extracted frames but intentionally leaves source uploads and generated chunk files on disk.
- Added startup FFmpeg path warnings when `ffmpeg` or `ffprobe` is found in Downloads, Desktop, Temp, or AppData Local Temp.
- Added README guidance to install FFmpeg in a stable location such as `C:\ffmpeg\bin`.
- Added top-level `CHANGELOG.md` in Keep a Changelog style.
- Added `CONTRIBUTING.md` guidance that future PRs should update the changelog.

## Verification

- PASS: `python -m py_compile backend/main.py backend/services/ffmpeg_ingest.py`
- PASS: `python -m backend.tests.smoke_test --offline`
- PASS: `git diff --check`
- PASS: `npm.cmd run build`
- PASS: direct FFmpeg unstable-path warning helper check for a Downloads path.

## Requires Workstation Verification

To verify the FFmpeg warning on Windows, temporarily put a test FFmpeg earlier in PATH from Downloads, start the backend, and confirm a warning appears:

```powershell
cd C:\Users\jgraziol\Documents\pigeonlab-v3
start.bat
Select-String -Path data\logs\backend-*.log -Pattern "FFmpeg detected at"
```

No CUDA-specific runtime verification is required for this PR.
