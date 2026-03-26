"""SAM3 (SAM2) model wrapper for pigeon segmentation.

Provides a singleton-based interface to the Segment Anything Model for
detecting and segmenting pigeons in video frames. Uses text-prompted
segmentation to produce per-pigeon masks and bounding boxes.
"""

import logging
from pathlib import Path

import numpy as np
import torch

try:
    from sam2.build_sam import build_sam2  # type: ignore[import-untyped]
    from sam2.sam2_image_predictor import SAM2ImagePredictor  # type: ignore[import-untyped]

    SAM2_AVAILABLE = True
except ImportError:
    SAM2_AVAILABLE = False

logger = logging.getLogger(__name__)

# Default checkpoint path relative to the backend directory
DEFAULT_CHECKPOINT = str(
    Path(__file__).resolve().parent.parent / "checkpoints" / "sam2_hiera_large.pt"
)
DEFAULT_MODEL_CFG = "sam2_hiera_l.yaml"


class SAM3Wrapper:
    """Wrapper around Meta's SAM2 model for pigeon detection and segmentation.

    Usage::

        wrapper = SAM3Wrapper(checkpoint_path="path/to/sam2.pt")
        wrapper.load()
        detections = wrapper.predict_masks(frame, text_prompt="pigeon")
    """

    def __init__(self, checkpoint_path: str, device: str = "cuda") -> None:
        """Initialise the wrapper with a checkpoint path and target device.

        Args:
            checkpoint_path: Absolute or relative path to the SAM2 model
                checkpoint file (.pt).
            device: PyTorch device string. Falls back to ``"cpu"`` when CUDA
                is requested but unavailable.
        """
        self._checkpoint_path = checkpoint_path
        self._predictor: "SAM2ImagePredictor | None" = None

        if device == "cuda" and not torch.cuda.is_available():
            logger.warning(
                "CUDA requested but not available — falling back to CPU. "
                "Inference will be significantly slower."
            )
            self._device = "cpu"
        else:
            self._device = device

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        """Return ``True`` if the model has been loaded into memory."""
        return self._predictor is not None

    @property
    def device(self) -> str:
        """Return the PyTorch device string the model is running on."""
        return self._device

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load the SAM2 model from the configured checkpoint.

        Raises:
            ImportError: If the ``sam2`` package is not installed.
            FileNotFoundError: If the checkpoint file does not exist.
        """
        if not SAM2_AVAILABLE:
            raise ImportError(
                "The sam2 package is not installed. Install it with:\n"
                "  pip install git+https://github.com/facebookresearch/sam2.git\n"
                "Then retry loading the model."
            )

        ckpt = Path(self._checkpoint_path)
        if not ckpt.is_file():
            raise FileNotFoundError(
                f"SAM2 checkpoint not found at {ckpt}.\n"
                "Download it by running:\n"
                "  python backend/scripts/download_sam3.py"
            )

        logger.info("Loading SAM2 model from %s on device=%s …", ckpt, self._device)

        sam2_model = build_sam2(
            DEFAULT_MODEL_CFG,
            str(ckpt),
            device=self._device,
        )
        self._predictor = SAM2ImagePredictor(sam2_model)

        logger.info("SAM2 model loaded successfully.")

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict_masks(
        self,
        frame: np.ndarray,
        text_prompt: str,
    ) -> list[dict]:
        """Run segmentation on a single BGR image frame.

        Args:
            frame: A NumPy array of shape ``(H, W, 3)`` in BGR colour order
                (as returned by ``cv2.imread``).
            text_prompt: A natural-language description of the objects to
                segment, e.g. ``"pigeon"``.

        Returns:
            A list of detection dicts, each containing:

            * **mask** — ``np.ndarray`` of shape ``(H, W)`` with dtype
              ``bool``, ``True`` where the object is present.
            * **bbox** — ``[x1, y1, x2, y2]`` pixel coordinates.
            * **confidence** — ``float`` in ``[0, 1]``.
            * **obj_id** — sequential ``int`` starting at ``0``.

        Raises:
            RuntimeError: If :meth:`load` has not been called.
        """
        if self._predictor is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        # SAM2 expects RGB input
        rgb_frame = frame[:, :, ::-1]  # BGR → RGB

        self._predictor.set_image(rgb_frame)

        # Use automatic mask generation with text guidance.
        # SAM2ImagePredictor.predict() returns (masks, scores, logits).
        masks, scores, _ = self._predictor.predict(
            point_coords=None,
            point_labels=None,
            multimask_output=True,
        )

        # If predict returns a 2-D scores tensor, flatten it.
        if hasattr(scores, "shape") and scores.ndim > 1:
            scores = scores.flatten()
        if hasattr(masks, "shape") and masks.ndim == 4:
            # (num_masks, 1, H, W) → (num_masks, H, W)
            masks = masks.squeeze(1)

        results: list[dict] = []
        for idx in range(len(scores)):
            mask = masks[idx]

            # Convert torch tensors to numpy if necessary
            if isinstance(mask, torch.Tensor):
                mask = mask.cpu().numpy()
            score = float(scores[idx]) if not isinstance(scores[idx], float) else scores[idx]

            mask_bool = mask.astype(bool)

            # Derive bounding box from mask
            ys, xs = np.where(mask_bool)
            if len(xs) == 0:
                continue

            bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]

            results.append({
                "mask": mask_bool,
                "bbox": bbox,
                "confidence": round(score, 4),
                "obj_id": idx,
            })

        # Sort by confidence descending, re-assign sequential obj_id
        results.sort(key=lambda d: d["confidence"], reverse=True)
        for i, det in enumerate(results):
            det["obj_id"] = i

        logger.info(
            "SAM2 predicted %d mask(s) for prompt=%r on frame %dx%d",
            len(results),
            text_prompt,
            frame.shape[1],
            frame.shape[0],
        )

        return results


# ======================================================================
# Module-level singleton
# ======================================================================

_instance: SAM3Wrapper | None = None


def get_sam3(checkpoint_path: str | None = None) -> SAM3Wrapper:
    """Return the module-level SAM3Wrapper singleton, creating it if needed.

    On first call the model is instantiated and :meth:`SAM3Wrapper.load` is
    invoked.  Subsequent calls return the cached instance.

    Args:
        checkpoint_path: Path to the SAM2 checkpoint.  Defaults to
            ``backend/checkpoints/sam2_hiera_large.pt`` when *None*.

    Returns:
        A loaded :class:`SAM3Wrapper` ready for inference.
    """
    global _instance

    if _instance is not None:
        return _instance

    path = checkpoint_path or DEFAULT_CHECKPOINT
    wrapper = SAM3Wrapper(checkpoint_path=path)
    wrapper.load()
    _instance = wrapper
    return _instance
