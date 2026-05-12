# PigeonLab Memory Model

SAM3.1 resizes video frames internally to 1024x1024 before propagation, so source resolution does not directly determine VRAM use. A lower-resolution upload may decode faster and save disk, but SAM3.1 still tracks against the normalized frame size.

With `PIGEONLAB_SAM3_OFFLOAD_VIDEO_TO_CPU=1` (the default), decoded normalized frames stay in system RAM instead of being copied to the GPU at session start. Budget roughly 12 MB per frame, or about 12 GB of system RAM per 1,000 frames. Keep this on for videos longer than about 30 seconds.

The SAM3.1 multiplex checkpoint uses about 5 GB of VRAM for model weights. During propagation, VRAM also holds an object memory bank that grows with frame count and active tracks. On an RTX A6000, single-session propagation empirically ran out of VRAM near 2,500 frames, so PigeonLab auto-chunks long uploads before SAM3 sees them. The default 60-second chunks are about 1,800 frames at 30 fps, which stays below that wall on 48 GB GPUs.

## Useful Knobs

- `PIGEONLAB_SAM3_MULTIPLEX_COUNT`: must match the SAM3.1 checkpoint; keep at `16`.
- `PIGEONLAB_SAM3_MAX_OBJECTS`: object slot budget. It affects setup capacity more than steady-state memory bank growth; `8` is a good default for four-pigeon sessions.
- `PIGEONLAB_SAM3_OFFLOAD_VIDEO_TO_CPU`: keep `1` for long videos. Turning it off can allocate the entire decoded video on the GPU.
- `PIGEONLAB_VIDEO_CHUNK_SECONDS`: lower this if propagation still hits VRAM limits.
- `PIGEONLAB_VIDEO_AUTO_CHUNK_UPLOADS`: keep `1` so uploads and path-based adds are chunked before processing.

## Recommended Profiles

- 48 GB GPUs such as RTX A6000 and A40: use the default workstation profile.
- 24 GB GPUs such as RTX 4090, RTX 3090, and RTX A5000: set `PIGEONLAB_VIDEO_CHUNK_SECONDS=40`.
- 16 GB GPUs: `PIGEONLAB_VIDEO_CHUNK_SECONDS=30` may work, but this is unofficial.
- Below 16 GB VRAM: not supported for SAM3.1 video propagation.

If a machine still fails near the end of a chunk, reduce `PIGEONLAB_VIDEO_CHUNK_SECONDS`, restart the backend, and reprocess only failed chunks.

On Windows, PyTorch's CUDA allocator does not support
`expandable_segments:True`. PigeonLab strips that token before Torch imports so
startup logs do not carry a misleading unsupported-platform warning.
Fragmentation on Windows is managed through auto-chunking and CUDA cleanup after
each SAM3 session. Linux installs may still opt into allocator-specific settings
when supported by their PyTorch build.
