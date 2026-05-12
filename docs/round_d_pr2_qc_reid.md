# Round D PR2: QC and Re-ID Quality Pass

## Shipped

- Replaced per-frame count/disappearance QC spam with chunk-level detection-density summaries.
- Added a single `no_detections` QC flag for empty chunks instead of one flag per frame.
- Made velocity-spike QC fps-aware so 15 fps footage is not judged with 30 fps frame-step assumptions.
- Added QC rule-count logging during processing, e.g. `Video 7 QC summary: {'low_detection_density': 1}`.
- Added grouped QC Review patterns and `Dismiss Similar` batch actions using the existing batch-resolve endpoint.
- Added conservative within-chunk re-identification for short track gaps:
  - color histogram over the masked/cropped pigeon region,
  - spatial distance from the previous fragment,
  - configurable gap/appearance thresholds,
  - no SAM3 internals changed.
- Added workstation defaults for:
  - `PIGEONLAB_REID_ENABLED=1`
  - `PIGEONLAB_REID_APPEARANCE_THRESHOLD=0.3`
  - `PIGEONLAB_REID_GAP_FRAMES=30`
  - `PIGEONLAB_REID_SPATIAL_THRESHOLD_PX=120`

## Sandbox Verification

- CPU unit tests cover QC aggregation, empty-chunk QC, fps-aware velocity, Re-ID fragment merging, and DB label rewriting.
- Offline smoke test remains valid without CUDA.
- Frontend production build verifies the grouped QC UI compiles.

## Requires Workstation Verification

Run this on the Windows + RTX A6000 workstation after installing this build:

```powershell
cd C:\Users\jgraziol\Documents\pigeonlab-v3
start.bat
```

Then reset, re-upload `Pigeon1.mp4`, and confirm:

- total QC flags drop from 2,835 to under 400,
- processing logs include a compact `QC summary`,
- Review -> QC shows grouped patterns and `Dismiss Similar`,
- chunk track counts move toward the physical count of 4 pigeons,
- no chunk regresses into SAM3 OOM or per-frame fallback.

