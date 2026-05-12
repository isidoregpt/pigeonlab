# Changelog

All notable changes to PigeonLab are documented here. This project follows the
[Keep a Changelog](https://keepachangelog.com/) format.

## [Unreleased]

### Added

- CHANGELOG and contribution guidance requiring future PRs to update it.

### Changed

- Documented stable FFmpeg install locations, uploaded-video storage paths, chunk storage paths, and per-GPU workstation guidance.
- Added startup warning when FFmpeg is discovered in Downloads, Desktop, Temp, or AppData Local Temp.
- Updated startup loading art documentation to match the current no-skip loader.

## [0.3.0] - 2026-05-12

### Added

- `GET /api/health/full` diagnostic endpoint for support snapshots (#15).
- Copy diagnostics action in Lab Setup (#15).
- Cancellable in-progress video processing with a `cancelled` status and card-level Cancel action (#15).
- `python -m backend.tests.smoke_test` plus a checked-in synthetic smoke video fixture (#15).
- SAM3.1 memory model documentation (#15).

## [0.2.0] - 2026-05-12

### Added

- Auto-chunked long-video processing, partial chunk status, and failed-chunk retry.
- Identity Review chunk-continuity workflow with same-as-previous quick mapping.
- Research Report export for publication prep and lab review.

### Fixed

- SAM3.1 runtime memory cleanup between video sessions.
- Production frontend builds no longer ship stale developer-machine Vite caches.
- Startup loading artwork now rotates one image per app launch.

## [0.1.0] - 2026-05-11

### Added

- Turnkey Windows workstation installer with SAM3.1, CUDA PyTorch, FFmpeg, Ollama, and setup checks.
- Video upload, path-based processing, frame extraction, tracking, features, QC flags, review pages, insights, exports, and training screens.
- Optional Gemma reviewer settings and Ollama integration.

### Fixed

- CUDA PyTorch install guidance and setup checks for Windows workstations.
- SAM3.1 checkpoint compatibility defaults for RTX A6000-class machines.
- Video upload/backend endpoint mismatch from earlier packages.
