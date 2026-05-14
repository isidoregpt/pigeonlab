# Round E: v5 Install and Runtime Follow-Ups

Date: 2026-05-14

This round addresses the v4 verification findings that surfaced only on the
Windows RTX A6000 workstation.

## Shipped

- Pinned the Windows CUDA PyTorch stack to the known-good versions:
  `torch==2.11.0+cu126`, `torchvision==0.26.0+cu126`, and
  `torchaudio==2.11.0+cu126`.
- Added `setup_check.py` driver compatibility detection. On Windows,
  `torch>=2.12` with an NVIDIA driver older than 555 is now reported as a
  failed compatibility check instead of passing silently.
- Fixed the model-load failure cleanup path by initializing `session_id` before
  SAM3 model loading starts.
- Removed the brittle hidden Hugging Face token prompt from `install.ps1`.
  The installer now uses an existing `hf auth login` cache when present and
  prints explicit login/download instructions when absent.
- Relaxed within-chunk Re-ID defaults and matching logic so strong appearance
  matches can bridge larger re-entry jumps while still rejecting weak matches.
- Documented the rotation-style research workflow for social reaction studies.

## Requires Workstation Verification

Run these on the Windows + A6000 workstation after a fresh install:

```powershell
cd C:\Users\jgraziol\Documents\pigeonlab-v5\backend
venv\Scripts\python.exe scripts\setup_check.py
venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

Expected PyTorch output:

```text
2.11.0+cu126
True
NVIDIA RTX A6000
```

Then process `Pigeon1.mp4` and compare per-chunk track counts against the v4
baseline of `2, 12, 7, 4, 0`. Re-ID should reduce inflated counts in chunks
where SAM3 fragmented the same physical bird into multiple track IDs. The log
should include either `Re-ID merged ... fragmented track(s)` or
`Re-ID evaluated ... candidate track link(s); no safe merges` for each chunk.
