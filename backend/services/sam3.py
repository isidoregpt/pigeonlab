"""SAM 3 model wrapper for pigeon detection and segmentation.

Wraps both the SAM 3 image API (per-frame mask prediction) and the
video API (full video session tracking with temporal consistency).
Provides a module-level singleton via :func:`get_sam3`.
"""

import logging
from pathlib import Path

import numpy as np
import torch
from PIL import Image

# ---------------------------------------------------------------------------
# SAM 3 imports — optional dependency
# ---------------------------------------------------------------------------
SAM3_AVAILABLE = True

try:
    from sam3.model_builder import build_sam3_image_model  # type: ignore[import-untyped]
except ImportError:
    build_sam3_image_model = None  # type: ignore[assignment,misc]
    SAM3_AVAILABLE = False

try:
    from sam3.model.sam3_image_processor import Sam3Processor  # type: ignore[import-untyped]
except ImportError:
    Sam3Processor = None  # type: ignore[assignment,misc]
    SAM3_AVAILABLE = False

try:
    from sam3.model_builder import build_sam3_video_predictor  # type: ignore[import-untyped]
except ImportError:
    build_sam3_video_predictor = None  # type: ignore[assignment,misc]
    SAM3_AVAILABLE = False

logger = logging.getLogger(__name__)

# Default checkpoint path relative to the project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CHECKPOINT = str(
    _PROJECT_ROOT / "data" / "models" / "sam3" / "sam3_hiera_large.pt"
)


class SAM3Wrapper:
    """Wrapper around Meta's SAM 3 for pigeon detection and segmentation.

    Exposes both the image API (single-frame masks) and the video API
    (session-based tracking across frames).

    Usage::

        wrapper = SAM3Wrapper()
        wrapper.load()
        detections = wrapper.predict_frame(frame_bgr, "pigeon")
    """

    def __init__(
        self,
        checkpoint_path: str | None = None,
        device: str = "cuda",
    ) -> None:
        """Initialise the wrapper.

        Args:
            checkpoint_path: Path to the SAM 3 checkpoint. ``None`` lets
                SAM 3 load from HuggingFace directly.
            device: PyTorch device string. Falls back to ``"cpu"`` when
                CUDA is requested but unavailable.
        """
        self._checkpoint_path = checkpoint_path

        if device == "cuda" and not torch.cuda.is_available():
            logger.warning(
                "CUDA requested but unavailable — falling back to CPU. "
                "Inference will be significantly slower."
            )
            self._device = "cpu"
        else:
            self._device = device

        self._image_model = None
        self._video_predictor = None
        self._loaded = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        """Return ``True`` if the model has been loaded into memory."""
        return self._loaded

    @property
    def device(self) -> str:
        """Return the PyTorch device string the model is running on."""
        return self._device

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load SAM 3 image and video models.

        Raises:
            ImportError: If the ``sam3`` package is not installed.
        """
        if not SAM3_AVAILABLE:
            raise ImportError(
                "The sam3 package is not installed. Install it with:\n"
                "  git clone https://github.com/facebookresearch/sam3.git\n"
                "  cd sam3 && pip install -e . && cd ..\n"
                "Then retry loading the model."
            )

        logger.info("Loading SAM 3 image model on device=%s …", self._device)
        self._image_model = build_sam3_image_model()
        self._image_model.to(self._device)

        logger.info("Loading SAM 3 video predictor on device=%s …", self._device)
        self._video_predictor = build_sam3_video_predictor()
        self._video_predictor.to(self._device)

        self._loaded = True
        logger.info("SAM 3 loaded on %s", self._device)

    # ------------------------------------------------------------------
    # Image API — single-frame prediction
    # ------------------------------------------------------------------

    def predict_frame(
        self,
        frame_bgr: np.ndarray,
        text_prompt: str,
    ) -> list[dict]:
        """Run segmentation on a single BGR image frame.

        Args:
            frame_bgr: NumPy array ``(H, W, 3)`` in BGR colour order.
            text_prompt: Natural-language description of objects to segment,
                e.g. ``"pigeon"``.

        Returns:
            List of detection dicts with keys ``mask`` (bool ``HxW``),
            ``bbox`` (``[x1, y1, x2, y2]``), ``confidence`` (float),
            ``obj_id`` (sequential int).

        Raises:
            RuntimeError: If :meth:`load` has not been called.
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        # Convert BGR numpy to RGB PIL Image
        rgb = frame_bgr[:, :, ::-1]
        image = Image.fromarray(rgb)

        processor = Sam3Processor(self._image_model)
        inference_state = processor.set_image(image)
        output = processor.set_text_prompt(
            state=inference_state,
            prompt=text_prompt,
        )

        masks = output["masks"]
        boxes = output["boxes"]
        scores = output["scores"]

        results: list[dict] = []
        for idx in range(len(scores)):
            mask = masks[idx]
            if isinstance(mask, torch.Tensor):
                mask = mask.cpu().numpy()
            mask_bool = mask.astype(bool)

            box = boxes[idx]
            if isinstance(box, torch.Tensor):
                box = box.cpu().tolist()
            bbox = [int(box[0]), int(box[1]), int(box[2]), int(box[3])]

            score = float(scores[idx])

            results.append({
                "mask": mask_bool,
                "bbox": bbox,
                "confidence": round(score, 4),
                "obj_id": idx,
            })

        # Sort by confidence descending, re-assign obj_id
        results.sort(key=lambda d: d["confidence"], reverse=True)
        for i, det in enumerate(results):
            det["obj_id"] = i

        logger.debug(
            "SAM 3 image API: %d detection(s) for prompt=%r on %dx%d frame",
            len(results), text_prompt, frame_bgr.shape[1], frame_bgr.shape[0],
        )
        return results

    # ------------------------------------------------------------------
    # Video API — session-based tracking
    # ------------------------------------------------------------------

    def start_video_session(self, video_path: str) -> str:
        """Start a SAM 3 video tracking session.

        Args:
            video_path: Path to the video file.

        Returns:
            A session ID string for use with :meth:`predict_video_frame`.

        Raises:
            RuntimeError: If :meth:`load` has not been called.
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        response = self._video_predictor.handle_request(
            type="start_session",
            resource_path=video_path,
        )
        session_id: str = response["session_id"]
        logger.info(
            "SAM 3 video session started: %s for %s", session_id, video_path,
        )
        return session_id

    def predict_video_frame(
        self,
        session_id: str,
        frame_index: int,
        text_prompt: str,
    ) -> list[dict]:
        """Run segmentation on a single frame within a video session.

        Uses SAM 3's video API for temporally-consistent tracking.

        Args:
            session_id: Session ID from :meth:`start_video_session`.
            frame_index: Zero-based frame index.
            text_prompt: Object description, e.g. ``"pigeon"``.

        Returns:
            List of detection dicts with keys ``mask``, ``bbox``,
            ``confidence``, ``obj_id``.

        Raises:
            RuntimeError: If :meth:`load` has not been called.
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        response = self._video_predictor.handle_request(
            type="add_prompt",
            session_id=session_id,
            frame_index=frame_index,
            text=text_prompt,
        )

        outputs = response.get("outputs", [])
        results: list[dict] = []

        for idx, out in enumerate(outputs):
            mask = out.get("mask")
            if isinstance(mask, torch.Tensor):
                mask = mask.cpu().numpy()
            if mask is not None:
                mask = mask.astype(bool)

            box = out.get("box", out.get("bbox", [0, 0, 0, 0]))
            if isinstance(box, torch.Tensor):
                box = box.cpu().tolist()
            bbox = [int(box[0]), int(box[1]), int(box[2]), int(box[3])]

            score = float(out.get("score", out.get("confidence", 0.0)))

            results.append({
                "mask": mask,
                "bbox": bbox,
                "confidence": round(score, 4),
                "obj_id": idx,
            })

        results.sort(key=lambda d: d["confidence"], reverse=True)
        for i, det in enumerate(results):
            det["obj_id"] = i

        logger.debug(
            "SAM 3 video API: %d detection(s) at frame %d, session=%s",
            len(results), frame_index, session_id,
        )
        return results


# ======================================================================
# Module-level singleton
# ======================================================================

_instance: SAM3Wrapper | None = None


def get_sam3(checkpoint_path: str | None = None) -> SAM3Wrapper:
    """Return the module-level SAM3Wrapper singleton, creating if needed.

    On first call the model is instantiated and :meth:`SAM3Wrapper.load`
    is invoked. Subsequent calls return the cached instance.

    Args:
        checkpoint_path: Path to the SAM 3 checkpoint. Defaults to
            ``data/models/sam3/sam3_hiera_large.pt`` when *None*.

    Returns:
        A loaded :class:`SAM3Wrapper` ready for inference.
    """
    global _instance

    if _instance is not None:
        return _instance

    wrapper = SAM3Wrapper(checkpoint_path=checkpoint_path)
    wrapper.load()
    _instance = wrapper
    return _instance
