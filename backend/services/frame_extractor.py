"""Frame extraction service for PigeonLab.

Extracts frames from video files using OpenCV and saves them as JPEGs
to disk for use by the processing pipeline and the frame viewer endpoint.
"""

import logging
import os
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class FrameExtractor:
    """Extract and manage video frames on disk.

    Frames are saved as JPEG files under ``{frames_dir}/{video_id}/{frame:06d}.jpg``.
    """

    def __init__(self, frames_dir: str = "data/frames") -> None:
        """Initialise the extractor.

        Args:
            frames_dir: Root directory for saved frames. Created if missing.
        """
        self._frames_dir = Path(frames_dir)
        self._frames_dir.mkdir(parents=True, exist_ok=True)
        try:
            threads = int(os.getenv("PIGEONLAB_OPENCV_THREADS", "32"))
            if threads > 0:
                cv2.setNumThreads(threads)
        except Exception:
            logger.debug("Could not set OpenCV thread count", exc_info=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_frames(
        self,
        video_path: str,
        video_id: int,
        sample_rate: int = 1,
    ) -> dict:
        """Extract frames from a video file and save as JPEGs.

        Args:
            video_path: Path to the video file.
            video_id: Database ID — used to organise the output directory.
            sample_rate: Save every *n*-th frame (1 = every frame).

        Returns:
            Dict with ``total_frames``, ``fps``, ``width``, ``height``,
            ``frames_extracted``, and ``output_dir``.

        Raises:
            FileNotFoundError: If *video_path* does not exist.
        """
        vpath = Path(video_path)
        if not vpath.is_file():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        output_dir = self._frames_dir / str(video_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(str(vpath))
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            extracted = 0
            frame_num = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_num % sample_rate == 0:
                    out_path = output_dir / f"{frame_num:06d}.jpg"
                    cv2.imwrite(
                        str(out_path), frame,
                        [cv2.IMWRITE_JPEG_QUALITY, 95],
                    )
                    extracted += 1

                    if extracted % 100 == 0:
                        logger.debug(
                            "Extracted %d frames so far (frame_num=%d) for video %d",
                            extracted, frame_num, video_id,
                        )

                frame_num += 1
        finally:
            cap.release()

        logger.info(
            "Frame extraction complete for video %d: %d/%d frames saved to %s",
            video_id, extracted, frame_num, output_dir,
        )

        return {
            "total_frames": frame_num,
            "fps": fps,
            "width": width,
            "height": height,
            "frames_extracted": extracted,
            "output_dir": str(output_dir),
        }

    def get_frame(self, video_id: int, frame_num: int) -> np.ndarray | None:
        """Load a saved frame from disk.

        Args:
            video_id: Database video ID.
            frame_num: Zero-based frame number.

        Returns:
            BGR NumPy array, or ``None`` if the file does not exist.
        """
        path = self._frame_path(video_id, frame_num)
        if not path.is_file():
            return None
        return cv2.imread(str(path))

    def frame_exists(self, video_id: int, frame_num: int) -> bool:
        """Return ``True`` if the frame JPEG exists on disk."""
        return self._frame_path(video_id, frame_num).is_file()

    def count_frames(self, video_id: int) -> int:
        """Count saved ``.jpg`` files for *video_id*."""
        video_dir = self._frames_dir / str(video_id)
        if not video_dir.is_dir():
            return 0
        return len(list(video_dir.glob("*.jpg")))

    def cleanup_frames(self, video_id: int) -> int:
        """Delete all saved frames for *video_id*.

        Returns:
            Number of files deleted.
        """
        video_dir = self._frames_dir / str(video_id)
        if not video_dir.is_dir():
            return 0

        deleted = 0
        for f in video_dir.iterdir():
            if f.is_file():
                f.unlink()
                deleted += 1

        # Remove the now-empty directory
        try:
            video_dir.rmdir()
        except OSError:
            pass

        logger.info("Cleaned up %d frame files for video %d", deleted, video_id)
        return deleted

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _frame_path(self, video_id: int, frame_num: int) -> Path:
        """Return the expected path for a frame JPEG."""
        return self._frames_dir / str(video_id) / f"{frame_num:06d}.jpg"


if __name__ == "__main__":
    print("FrameExtractor ready.")
