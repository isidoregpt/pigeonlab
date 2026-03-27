"""SAM 3 model wrapper for pigeon detection and segmentation.

Wraps both the SAM 3 image API (per-frame mask prediction) and the
video API (full video session tracking with temporal consistency).
Provides a module-level singleton via :func:`get_sam3`.

Supports two installation paths:
  - **Native**: ``git clone https://github.com/facebookresearch/sam3.git && pip install -e .``
  - **Transformers**: ``pip install transformers accelerate``
"""

from __future__ import annotations

import logging
import uuid

import numpy as np
import torch
from PIL import Image

# ---------------------------------------------------------------------------
# SAM 3 imports — try native package first, then HuggingFace transformers
# ---------------------------------------------------------------------------

# PATH 1: Native sam3 package (from git clone facebookresearch/sam3)
SAM3_NATIVE_AVAILABLE = False
try:
    from sam3.model_builder import build_sam3_image_model  # type: ignore[import-untyped]
    from sam3.model.sam3_image_processor import Sam3Processor as NativeSam3Processor  # type: ignore[import-untyped]
    from sam3.model_builder import build_sam3_video_predictor  # type: ignore[import-untyped]

    SAM3_NATIVE_AVAILABLE = True
except ImportError:
    build_sam3_image_model = None  # type: ignore[assignment,misc]
    NativeSam3Processor = None  # type: ignore[assignment,misc]
    build_sam3_video_predictor = None  # type: ignore[assignment,misc]

# PATH 2: HuggingFace transformers (pip install transformers)
SAM3_TRANSFORMERS_AVAILABLE = False
try:
    from transformers import Sam3Processor as HFSam3Processor  # type: ignore[import-untyped]
    from transformers import Sam3Model  # type: ignore[import-untyped]
    from transformers import Sam3VideoModel  # type: ignore[import-untyped]
    from transformers import Sam3VideoProcessor as HFSam3VideoProcessor  # type: ignore[import-untyped]

    SAM3_TRANSFORMERS_AVAILABLE = True
except ImportError:
    HFSam3Processor = None  # type: ignore[assignment,misc]
    Sam3Model = None  # type: ignore[assignment,misc]
    Sam3VideoModel = None  # type: ignore[assignment,misc]
    HFSam3VideoProcessor = None  # type: ignore[assignment,misc]

SAM3_AVAILABLE: bool = SAM3_NATIVE_AVAILABLE or SAM3_TRANSFORMERS_AVAILABLE

logger = logging.getLogger(__name__)


class SAM3Wrapper:
    """Wrapper around Meta's SAM 3 for pigeon detection and segmentation.

    Exposes both the image API (single-frame masks) and the video API
    (session-based tracking across frames).  Supports two backends:

    - **Native** (``sam3`` package installed from source)
    - **Transformers** (``transformers`` pip package)

    Usage::

        wrapper = SAM3Wrapper()
        wrapper.load()
        detections = wrapper.predict_frame(frame_bgr, "pigeon")
    """

    def __init__(
        self,
        model_id: str = "facebook/sam3",
        device: str | None = None,
    ) -> None:
        """Initialise the wrapper.

        Args:
            model_id: HuggingFace model ID used when loading via
                the transformers backend.
            device: PyTorch device string.  When ``None``, auto-detects
                CUDA availability and falls back to ``"cpu"``.
        """
        self._model_id = model_id

        if device is None:
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self._device = device

        self._image_model = None
        self._image_processor = None
        self._video_model = None
        self._video_processor = None
        self._video_predictor = None
        self._loaded = False
        self._using_native = False

        # Stores transformers-based video inference sessions keyed by UUID.
        self._video_sessions: dict[str, object] = {}

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

    @property
    def using_native(self) -> bool:
        """Return ``True`` if using the native SAM 3 package backend."""
        return self._using_native

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load SAM 3 image and video models.

        Prefers the native ``sam3`` package when available; otherwise
        falls back to the HuggingFace ``transformers`` backend.

        Raises:
            ImportError: If neither the ``sam3`` package nor
                ``transformers`` with SAM 3 support is installed.
        """
        if not SAM3_AVAILABLE:
            raise ImportError(
                "SAM 3 not found. Install with either:\n"
                "  Option A (native): git clone https://github.com/facebookresearch/sam3.git "
                "&& cd sam3 && pip install -e .\n"
                "  Option B (transformers): pip install transformers accelerate"
            )

        if SAM3_NATIVE_AVAILABLE:
            logger.info("Loading SAM 3 image model via native package on %s …", self._device)
            self._image_model = build_sam3_image_model()
            self._image_model.to(self._device)
            self._image_processor = NativeSam3Processor(self._image_model)
            self._video_predictor = build_sam3_video_predictor()
            self._using_native = True
            logger.info("SAM 3 loaded via native package on %s", self._device)
        else:
            logger.info("Loading SAM 3 via transformers on %s …", self._device)
            self._image_model = Sam3Model.from_pretrained(self._model_id).to(self._device)
            self._image_processor = HFSam3Processor.from_pretrained(self._model_id)
            self._video_model = Sam3VideoModel.from_pretrained(self._model_id).to(
                self._device, dtype=torch.bfloat16,
            )
            self._video_processor = HFSam3VideoProcessor.from_pretrained(self._model_id)
            self._using_native = False
            logger.info("SAM 3 loaded via transformers on %s", self._device)

        self._loaded = True

    # ------------------------------------------------------------------
    # Image API — single-frame prediction
    # ------------------------------------------------------------------

    def predict_frame(
        self,
        frame_bgr: np.ndarray,
        text_prompt: str,
        confidence_threshold: float = 0.5,
    ) -> list[dict]:
        """Run segmentation on a single BGR image frame.

        Args:
            frame_bgr: NumPy array ``(H, W, 3)`` in BGR colour order.
            text_prompt: Natural-language description of objects to segment,
                e.g. ``"pigeon"``.
            confidence_threshold: Minimum confidence score to keep a
                detection.  Detections below this value are filtered out.

        Returns:
            List of detection dicts with keys ``mask`` (bool ``HxW``),
            ``bbox`` (``[x1, y1, x2, y2]``), ``confidence`` (float),
            ``obj_id`` (sequential int).  Empty list when nothing is found.

        Raises:
            RuntimeError: If :meth:`load` has not been called.
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        # Convert BGR numpy to RGB PIL Image
        rgb = frame_bgr[:, :, ::-1]
        image = Image.fromarray(rgb)

        if self._using_native:
            processor = NativeSam3Processor(self._image_model)
            inference_state = processor.set_image(image)
            output = processor.set_text_prompt(
                state=inference_state,
                prompt=text_prompt,
            )
            masks = output["masks"]
            boxes = output["boxes"]
            scores = output["scores"]
        else:
            inputs = self._image_processor(
                images=image, text=text_prompt, return_tensors="pt",
            ).to(self._device)
            with torch.no_grad():
                outputs = self._image_model(**inputs)
            results = self._image_processor.post_process_instance_segmentation(
                outputs,
                threshold=confidence_threshold,
                mask_threshold=0.5,
                target_sizes=inputs.get("original_sizes").tolist(),
            )[0]
            masks = results["masks"]
            boxes = results["boxes"]
            scores = results["scores"]

        detections: list[dict] = []
        for idx in range(len(scores)):
            score = float(scores[idx])
            if score < confidence_threshold:
                continue

            mask = masks[idx]
            if isinstance(mask, torch.Tensor):
                mask = mask.cpu().numpy()
            mask_bool: np.ndarray = mask.astype(bool)

            box = boxes[idx]
            if isinstance(box, torch.Tensor):
                box = box.cpu().tolist()
            bbox = [int(box[0]), int(box[1]), int(box[2]), int(box[3])]

            detections.append({
                "mask": mask_bool,
                "bbox": bbox,
                "confidence": round(score, 4),
                "obj_id": idx,
            })

        # Sort by confidence descending, re-assign sequential obj_id
        detections.sort(key=lambda d: d["confidence"], reverse=True)
        for i, det in enumerate(detections):
            det["obj_id"] = i

        logger.debug(
            "SAM 3 predict_frame: %d detection(s) for prompt=%r on %dx%d frame",
            len(detections), text_prompt, frame_bgr.shape[1], frame_bgr.shape[0],
        )
        return detections

    # ------------------------------------------------------------------
    # Video API — session-based tracking
    # ------------------------------------------------------------------

    def start_video_session(self, video_path: str) -> str:
        """Start a SAM 3 video tracking session.

        Args:
            video_path: Path to the video file.

        Returns:
            A session ID string for use with :meth:`predict_video_frame`,
            :meth:`propagate_video`, and :meth:`close_video_session`.

        Raises:
            RuntimeError: If :meth:`load` has not been called.
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        if self._using_native:
            response = self._video_predictor.handle_request(
                request=dict(type="start_session", resource_path=video_path),
            )
            session_id: str = response["session_id"]
        else:
            from transformers.video_utils import load_video  # type: ignore[import-untyped]

            video_frames, _ = load_video(video_path)
            inference_session = self._video_processor.init_video_session(
                video=video_frames,
                inference_device=self._device,
                processing_device="cpu",
                video_storage_device="cpu",
                dtype=torch.bfloat16,
            )
            session_id = str(uuid.uuid4())
            self._video_sessions[session_id] = inference_session

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
            KeyError: If the *session_id* is unknown (transformers backend).
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        if self._using_native:
            response = self._video_predictor.handle_request(
                request=dict(
                    type="add_prompt",
                    session_id=session_id,
                    frame_index=frame_index,
                    text=text_prompt,
                ),
            )
            output = response["outputs"]
            return self._parse_video_outputs(output)
        else:
            session = self._video_sessions[session_id]
            session = self._video_processor.add_text_prompt(
                inference_session=session,
                text=text_prompt,
            )
            self._video_sessions[session_id] = session

            outputs_per_frame: dict[int, list[dict]] = {}
            for model_outputs in self._video_model.propagate_in_video_iterator(
                inference_session=session,
                max_frame_num_to_track=frame_index + 1,
            ):
                processed = self._video_processor.postprocess_outputs(
                    session, model_outputs,
                )
                fidx = model_outputs.frame_idx
                outputs_per_frame[fidx] = self._parse_processed_outputs(processed)

            result = outputs_per_frame.get(frame_index, [])
            logger.debug(
                "SAM 3 predict_video_frame: %d detection(s) at frame %d, session=%s",
                len(result), frame_index, session_id,
            )
            return result

    def propagate_video(
        self,
        session_id: str,
        text_prompt: str,
        max_frames: int = 10000,
    ) -> dict[int, list[dict]]:
        """Run full video propagation and return all frames at once.

        More efficient than calling :meth:`predict_video_frame` for
        every frame individually.

        Args:
            session_id: Session ID from :meth:`start_video_session`.
            text_prompt: Object description, e.g. ``"pigeon"``.
            max_frames: Maximum number of frames to propagate through.

        Returns:
            Dict mapping frame indices to lists of detection dicts.

        Raises:
            RuntimeError: If :meth:`load` has not been called.
            KeyError: If the *session_id* is unknown (transformers backend).
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        if self._using_native:
            # Add prompt first
            self._video_predictor.handle_request(
                request=dict(
                    type="add_prompt",
                    session_id=session_id,
                    frame_index=0,
                    text=text_prompt,
                ),
            )
            # Iterate all frames
            results: dict[int, list[dict]] = {}
            for frame_idx in range(max_frames):
                response = self._video_predictor.handle_request(
                    request=dict(
                        type="get_frame",
                        session_id=session_id,
                        frame_index=frame_idx,
                    ),
                )
                if response.get("done"):
                    break
                output = response.get("outputs", [])
                results[frame_idx] = self._parse_video_outputs(output)
            return results
        else:
            session = self._video_sessions[session_id]
            session = self._video_processor.add_text_prompt(
                inference_session=session,
                text=text_prompt,
            )
            self._video_sessions[session_id] = session

            results = {}
            for model_outputs in self._video_model.propagate_in_video_iterator(
                inference_session=session,
                max_frame_num_to_track=max_frames,
            ):
                processed = self._video_processor.postprocess_outputs(
                    session, model_outputs,
                )
                frame_idx = model_outputs.frame_idx
                results[frame_idx] = self._parse_processed_outputs(processed)

            logger.info(
                "SAM 3 propagate_video: %d frames processed, session=%s",
                len(results), session_id,
            )
            return results

    def close_video_session(self, session_id: str) -> None:
        """Close a video tracking session and free resources.

        Args:
            session_id: Session ID from :meth:`start_video_session`.
        """
        if not self._using_native:
            self._video_sessions.pop(session_id, None)
            logger.debug("Video session %s closed", session_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_video_outputs(outputs: list) -> list[dict]:
        """Parse native video API outputs into the standard detection format.

        Args:
            outputs: Raw output list from the native video predictor.

        Returns:
            List of detection dicts.
        """
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
        return results

    @staticmethod
    def _parse_processed_outputs(processed: dict) -> list[dict]:
        """Parse transformers postprocessed outputs into detection format.

        Args:
            processed: Output from ``Sam3VideoProcessor.postprocess_outputs``.

        Returns:
            List of detection dicts.
        """
        results: list[dict] = []
        masks = processed.get("masks", [])
        boxes = processed.get("boxes", [])
        scores = processed.get("scores", [])

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

        results.sort(key=lambda d: d["confidence"], reverse=True)
        for i, det in enumerate(results):
            det["obj_id"] = i
        return results


# ======================================================================
# Module-level singleton
# ======================================================================

_instance: SAM3Wrapper | None = None


def get_sam3(model_id: str = "facebook/sam3") -> SAM3Wrapper:
    """Return the module-level SAM3Wrapper singleton, creating if needed.

    On first call the model is instantiated and :meth:`SAM3Wrapper.load`
    is invoked.  Subsequent calls return the cached instance.

    Args:
        model_id: HuggingFace model ID for the SAM 3 model.

    Returns:
        A loaded :class:`SAM3Wrapper` ready for inference.
    """
    global _instance

    if _instance is not None:
        return _instance

    wrapper = SAM3Wrapper(model_id=model_id)
    wrapper.load()
    _instance = wrapper
    return _instance


def reset_sam3() -> None:
    """Reset the module-level singleton, allowing a fresh load."""
    global _instance
    _instance = None
