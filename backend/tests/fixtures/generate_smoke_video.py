"""Regenerate the checked-in smoke video fixture.

Requires OpenCV and NumPy:
    python backend/tests/fixtures/generate_smoke_video.py
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


OUT = Path(__file__).with_name("smoke_video.mp4")
WIDTH, HEIGHT = 160, 120
FPS = 30
FRAMES = 150


def main() -> None:
    writer = cv2.VideoWriter(
        str(OUT),
        cv2.VideoWriter_fourcc(*"mp4v"),
        FPS,
        (WIDTH, HEIGHT),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not create {OUT}")

    for frame_idx in range(FRAMES):
        frame = np.full((HEIGHT, WIDTH, 3), (42, 48, 55), dtype=np.uint8)
        cv2.line(frame, (0, 90), (WIDTH, 90), (74, 85, 99), 1)
        x1 = 24 + frame_idx * 70 // FRAMES
        y1 = 42 + int(10 * np.sin(frame_idx / 18))
        x2 = 132 - frame_idx * 66 // FRAMES
        y2 = 76 + int(8 * np.cos(frame_idx / 15))
        cv2.circle(frame, (x1, y1), 9, (214, 214, 206), -1)
        cv2.circle(frame, (x1 + 5, y1 - 3), 4, (230, 230, 220), -1)
        cv2.circle(frame, (x2, y2), 8, (116, 161, 196), -1)
        cv2.circle(frame, (x2 - 4, y2 - 4), 4, (145, 184, 213), -1)
        writer.write(frame)

    writer.release()
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
