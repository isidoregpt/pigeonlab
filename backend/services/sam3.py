"""SAM 3 / SAM 3.1 integration for PigeonLab.

The app prefers the official ``facebookresearch/sam3`` package for SAM 3.1,
because the SAM 3.1 checkpoint uses the Object Multiplex video predictor and
does not currently have Hugging Face Transformers integration. For the older
``facebook/sam3`` Transformers path, this wrapper keeps a fallback so existing
installations still work.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
import importlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image

try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore[assignment]
    TORCH_AVAILABLE = False

# ---------------------------------------------------------------------------
# SAM 3 imports - native package first, Transformers fallback for SAM 3 only.
# ---------------------------------------------------------------------------

SAM3_NATIVE_AVAILABLE = False
try:
    from sam3.model_builder import build_sam3_image_model  # type: ignore[import-untyped]
    from sam3.model_builder import build_sam3_video_predictor  # type: ignore[import-untyped]
    from sam3.model.sam3_image_processor import Sam3Processor as NativeSam3Processor  # type: ignore[import-untyped]

    try:
        from sam3.model_builder import build_sam3_predictor  # type: ignore[import-untyped]
    except ImportError:
        build_sam3_predictor = None  # type: ignore[assignment]

    SAM3_NATIVE_AVAILABLE = True
except ImportError:
    build_sam3_image_model = None  # type: ignore[assignment,misc]
    build_sam3_video_predictor = None  # type: ignore[assignment,misc]
    build_sam3_predictor = None  # type: ignore[assignment,misc]
    NativeSam3Processor = None  # type: ignore[assignment,misc]

SAM3_TRANSFORMERS_AVAILABLE = False
try:
    from transformers import Sam3Model  # type: ignore[import-untyped]
    from transformers import Sam3Processor as HFSam3Processor  # type: ignore[import-untyped]
    from transformers import Sam3VideoModel  # type: ignore[import-untyped]
    from transformers import Sam3VideoProcessor as HFSam3VideoProcessor  # type: ignore[import-untyped]

    SAM3_TRANSFORMERS_AVAILABLE = True
except ImportError:
    Sam3Model = None  # type: ignore[assignment,misc]
    HFSam3Processor = None  # type: ignore[assignment,misc]
    Sam3VideoModel = None  # type: ignore[assignment,misc]
    HFSam3VideoProcessor = None  # type: ignore[assignment,misc]

SAM3_AVAILABLE: bool = SAM3_NATIVE_AVAILABLE or SAM3_TRANSFORMERS_AVAILABLE

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_ROOT = PROJECT_ROOT / "data" / "models"
_SAM3_RUNTIME_PATCHES_APPLIED = False
_SAM3_RUNTIME_PATCHES: dict[str, bool] = {
    "init_state_offload_state_to_cpu": False,
    "windows_sdpa_fallback": False,
    "load_video_frames_offload_video_to_cpu_default": False,
}


def _mark_patch(name: str, message: str) -> None:
    _SAM3_RUNTIME_PATCHES[name] = True
    logger.info(message)


def get_sam3_runtime_patches() -> dict[str, bool]:
    """Return the SAM3 runtime patch state for diagnostics."""
    return dict(_SAM3_RUNTIME_PATCHES)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _cuda_supports_bfloat16() -> bool:
    if not TORCH_AVAILABLE or not torch.cuda.is_available():
        return False
    try:
        return bool(torch.cuda.is_bf16_supported())
    except Exception:
        major, _minor = torch.cuda.get_device_capability(0)
        return major >= 8


def _cuda_dtype():
    if not TORCH_AVAILABLE:
        return None
    requested = os.getenv("PIGEONLAB_TORCH_DTYPE", "auto").strip().lower()
    if requested in {"float16", "fp16", "half"}:
        return torch.float16
    if requested in {"bfloat16", "bf16"}:
        return torch.bfloat16
    if requested in {"float32", "fp32"}:
        return torch.float32
    return torch.bfloat16 if _cuda_supports_bfloat16() else torch.float16


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _as_backend_list(backends: Any) -> list[Any]:
    if isinstance(backends, Iterable) and not isinstance(backends, (str, bytes)):
        return list(backends)
    return [backends]


def _apply_sam3_runtime_patches() -> None:
    """Apply narrow compatibility patches for the native SAM3.1 Windows stack.

    The official SAM3.1 code path has two Windows-specific rough edges observed
    on RTX workstation installs:
    - the base predictor forwards ``offload_state_to_cpu`` to the multiplex
      tracker even though that tracker's ``init_state`` does not accept it.
    - parts of the model request FlashAttention-only SDPA. Windows PyTorch
      wheels commonly lack FlashAttention, so we append safe fallback kernels.
    """

    global _SAM3_RUNTIME_PATCHES_APPLIED
    if _SAM3_RUNTIME_PATCHES_APPLIED:
        return

    patches_enabled = _env_bool("PIGEONLAB_SAM3_ENABLE_WINDOWS_PATCHES", _is_windows())
    if not patches_enabled or not TORCH_AVAILABLE:
        _SAM3_RUNTIME_PATCHES_APPLIED = True
        return

    try:
        from sam3.model.sam3_multiplex_tracking import (  # type: ignore[import-untyped]
            Sam3MultiplexTrackingWithInteractivity,
        )

        original_init_state = Sam3MultiplexTrackingWithInteractivity.init_state
        if not getattr(original_init_state, "_pigeonlab_compat_patch", False):

            def patched_init_state(self, *args, **kwargs):
                kwargs.pop("offload_state_to_cpu", None)
                return original_init_state(self, *args, **kwargs)

            patched_init_state._pigeonlab_compat_patch = True  # type: ignore[attr-defined]
            Sam3MultiplexTrackingWithInteractivity.init_state = patched_init_state
            _mark_patch(
                "init_state_offload_state_to_cpu",
                "Applied SAM3.1 init_state offload_state_to_cpu compatibility patch",
            )
        else:
            _SAM3_RUNTIME_PATCHES["init_state_offload_state_to_cpu"] = True
    except Exception:
        logger.debug("SAM3.1 init_state compatibility patch skipped", exc_info=True)

    try:
        from sam3.model import io_utils  # type: ignore[import-untyped]

        original_loader = io_utils.load_video_frames_from_video_file_using_cv2
        if not getattr(original_loader, "_pigeonlab_offload_video_patch", False):

            def patched_loader(*args, **kwargs):
                kwargs.setdefault("offload_video_to_cpu", True)
                return original_loader(*args, **kwargs)

            patched_loader._pigeonlab_offload_video_patch = True  # type: ignore[attr-defined]
            io_utils.load_video_frames_from_video_file_using_cv2 = patched_loader
            for module_name in ("sam3.model.sam3_base_predictor", "sam3.model.sam3_video_predictor"):
                try:
                    module = importlib.import_module(module_name)
                    if getattr(module, "load_video_frames_from_video_file_using_cv2", None) is original_loader:
                        setattr(module, "load_video_frames_from_video_file_using_cv2", patched_loader)
                except Exception:
                    logger.debug(
                        "Could not patch %s.load_video_frames_from_video_file_using_cv2",
                        module_name,
                        exc_info=True,
                    )
            _mark_patch(
                "load_video_frames_offload_video_to_cpu_default",
                "Applied SAM3.1 load_video_frames offload_video_to_cpu default patch",
            )
        else:
            _SAM3_RUNTIME_PATCHES["load_video_frames_offload_video_to_cpu_default"] = True
    except Exception:
        logger.debug("SAM3.1 load_video_frames offload_video_to_cpu patch skipped", exc_info=True)

    if _is_windows():
        try:
            import importlib
            import torch.nn.attention as torch_attention
            from torch.nn.attention import SDPBackend

            original_sdpa_kernel = torch_attention.sdpa_kernel
            if not getattr(original_sdpa_kernel, "_pigeonlab_compat_patch", False):
                fallback_backends = []
                for name in ("EFFICIENT_ATTENTION", "CUDNN_ATTENTION", "MATH"):
                    backend = getattr(SDPBackend, name, None)
                    if backend is not None:
                        fallback_backends.append(backend)

                def patched_sdpa_kernel(backends, *args, **kwargs):
                    requested = _as_backend_list(backends)
                    for backend in fallback_backends:
                        if backend not in requested:
                            requested.append(backend)
                    return original_sdpa_kernel(requested, *args, **kwargs)

                patched_sdpa_kernel._pigeonlab_compat_patch = True  # type: ignore[attr-defined]
                torch_attention.sdpa_kernel = patched_sdpa_kernel

                for module_name in ("sam3.model.decoder", "sam3.model.vl_combiner"):
                    try:
                        module = importlib.import_module(module_name)
                        if getattr(module, "sdpa_kernel", None) is original_sdpa_kernel:
                            setattr(module, "sdpa_kernel", patched_sdpa_kernel)
                    except Exception:
                        logger.debug("Could not patch %s.sdpa_kernel", module_name, exc_info=True)

                _mark_patch(
                    "windows_sdpa_fallback",
                    "Applied SAM3.1 Windows SDPA fallback compatibility patch",
                )
            else:
                _SAM3_RUNTIME_PATCHES["windows_sdpa_fallback"] = True
        except Exception:
            logger.debug("SAM3.1 SDPA compatibility patch skipped", exc_info=True)

    _SAM3_RUNTIME_PATCHES_APPLIED = True


def get_sam3_version() -> str:
    return os.getenv("PIGEONLAB_SAM3_VERSION", "sam3.1").strip() or "sam3.1"


def get_sam3_model_id(version: str | None = None) -> str:
    version = version or get_sam3_version()
    return os.getenv(
        "PIGEONLAB_SAM3_MODEL_ID",
        "facebook/sam3.1" if version == "sam3.1" else "facebook/sam3",
    )


def get_sam3_model_dir(version: str | None = None) -> Path:
    version = version or get_sam3_version()
    configured = os.getenv("PIGEONLAB_SAM3_MODEL_DIR")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else PROJECT_ROOT / path
    return MODEL_ROOT / version


def _read_config(model_dir: Path) -> dict[str, Any] | None:
    config_path = model_dir / "config.json"
    if not config_path.is_file():
        return None
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def find_sam3_checkpoint(version: str | None = None, model_dir: Path | None = None) -> Path | None:
    """Return the preferred local native checkpoint path, if one exists."""
    configured = os.getenv("PIGEONLAB_SAM3_CHECKPOINT")
    if configured:
        path = Path(configured)
        path = path if path.is_absolute() else PROJECT_ROOT / path
        return path if path.is_file() else None

    version = version or get_sam3_version()
    model_dir = model_dir or get_sam3_model_dir(version)
    names = (
        ["sam3.1_multiplex.pt", "sam3_1_multiplex.pt", "sam3.1.pt", "sam3.pt"]
        if version == "sam3.1"
        else ["sam3.pt"]
    )
    for name in names:
        candidate = model_dir / name
        if candidate.is_file():
            return candidate
    matches = sorted(model_dir.glob("*.pt")) if model_dir.is_dir() else []
    return matches[0] if matches else None


def _model_ref_for_transformers(version: str) -> str:
    model_dir = get_sam3_model_dir(version)
    if (model_dir / "config.json").is_file():
        return str(model_dir)
    return get_sam3_model_id(version)


def _torch_version_ok(minimum: tuple[int, int] = (2, 7)) -> bool:
    if not TORCH_AVAILABLE:
        return False
    parts = torch.__version__.split(".")  # type: ignore[union-attr]
    try:
        major = int(parts[0])
        minor = int(parts[1].split("+")[0].split("a")[0].split("b")[0].split("rc")[0])
    except (IndexError, ValueError):
        return False
    return (major, minor) >= minimum


def get_sam3_status(load_model: bool = False) -> dict[str, Any]:
    """Return a lightweight readiness report for settings/health checks."""
    version = get_sam3_version()
    model_dir = get_sam3_model_dir(version)
    checkpoint = find_sam3_checkpoint(version, model_dir)
    config = _read_config(model_dir)
    allow_hf = _env_bool("PIGEONLAB_ALLOW_HF_DOWNLOAD", False)

    errors: list[str] = []
    warnings: list[str] = []

    if not TORCH_AVAILABLE:
        errors.append("PyTorch is not installed.")
    elif not _torch_version_ok():
        errors.append(f"PyTorch 2.7+ is required for SAM3. Found {torch.__version__}.")

    cuda_available = bool(TORCH_AVAILABLE and torch.cuda.is_available())
    cuda_version = torch.version.cuda if TORCH_AVAILABLE else None
    gpu_name = torch.cuda.get_device_name(0) if cuda_available else None

    if version == "sam3.1":
        if sys.version_info < (3, 12):
            errors.append("SAM3.1 requires Python 3.12 or newer.")
        if not SAM3_NATIVE_AVAILABLE:
            errors.append("SAM3.1 requires the latest facebookresearch/sam3 package.")
        if checkpoint is None and not allow_hf:
            errors.append(
                "SAM3.1 checkpoint not found. Run backend/scripts/download_sam3.py "
                "or set PIGEONLAB_SAM3_CHECKPOINT."
            )
        if not cuda_available:
            errors.append("CUDA GPU not detected. SAM3.1 video inference requires a CUDA-capable GPU.")
        elif cuda_version and tuple(int(p) for p in cuda_version.split(".")[:2]) < (12, 6):
            warnings.append(f"SAM3.1 officially expects CUDA 12.6+. Found CUDA {cuda_version}.")
        if SAM3_NATIVE_AVAILABLE and TORCH_AVAILABLE:
            _apply_sam3_runtime_patches()
    else:
        if not SAM3_NATIVE_AVAILABLE and not SAM3_TRANSFORMERS_AVAILABLE:
            errors.append("Install either facebookresearch/sam3 or Transformers with SAM3 support.")
        if checkpoint is None and not allow_hf and not (model_dir / "config.json").is_file():
            warnings.append(
                "No local SAM3 model files found. Set PIGEONLAB_ALLOW_HF_DOWNLOAD=1 "
                "to permit runtime Hugging Face downloads."
            )

    backend = None
    if version == "sam3.1" and SAM3_NATIVE_AVAILABLE:
        backend = "native-sam3.1"
    elif SAM3_NATIVE_AVAILABLE:
        backend = "native-sam3"
    elif SAM3_TRANSFORMERS_AVAILABLE:
        backend = "transformers"

    load_error = None
    if load_model and not errors:
        try:
            wrapper = get_sam3()
            loaded = wrapper.is_loaded
        except Exception as exc:  # pragma: no cover - hardware/model dependent
            loaded = False
            load_error = str(exc)
            errors.append(f"SAM3 model failed to load: {exc}")
    else:
        loaded = _instance.is_loaded if _instance is not None else False

    return {
        "ready": len(errors) == 0,
        "loaded": loaded,
        "version": version,
        "backend": backend,
        "native_available": SAM3_NATIVE_AVAILABLE,
        "transformers_available": SAM3_TRANSFORMERS_AVAILABLE,
        "torch_available": TORCH_AVAILABLE,
        "torch_version": torch.__version__ if TORCH_AVAILABLE else None,
        "cuda_available": cuda_available,
        "cuda_version": cuda_version,
        "gpu_name": gpu_name,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "recommended_dtype": str(_cuda_dtype()).replace("torch.", "") if cuda_available else "float32",
        "model_id": get_sam3_model_id(version),
        "model_dir": str(model_dir),
        "checkpoint_path": str(checkpoint) if checkpoint else None,
        "config_path": str(model_dir / "config.json") if (model_dir / "config.json").is_file() else None,
        "config_model_type": config.get("model_type") if config else None,
        "config_architectures": config.get("architectures") if config else None,
        "allow_hf_download": allow_hf,
        "errors": errors,
        "warnings": warnings,
        "load_error": load_error,
        "runtime_patches": get_sam3_runtime_patches(),
    }


class SAM3Wrapper:
    """Wrapper around SAM3 image/video APIs with SAM3.1 support."""

    def __init__(
        self,
        model_id: str | None = None,
        checkpoint_path: str | None = None,
        version: str | None = None,
        device: str | None = None,
    ) -> None:
        self._version = version or get_sam3_version()
        self._model_id = model_id or get_sam3_model_id(self._version)
        found_checkpoint = find_sam3_checkpoint(self._version)
        self._checkpoint_path = checkpoint_path or (str(found_checkpoint) if found_checkpoint else None)

        if not TORCH_AVAILABLE:
            self._device = device or "cpu"
        elif device is None:
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
        self._video_sessions: dict[str, object] = {}

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def device(self) -> str:
        return self._device

    @property
    def using_native(self) -> bool:
        return self._using_native

    @property
    def version(self) -> str:
        return self._version

    def load(self) -> None:
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for SAM3.")

        if self._version == "sam3.1":
            self._load_native_sam31()
        elif SAM3_NATIVE_AVAILABLE:
            self._load_native_sam3()
        elif SAM3_TRANSFORMERS_AVAILABLE:
            self._load_transformers_sam3()
        else:
            raise ImportError(
                "SAM3 is not available. Install facebookresearch/sam3, or install "
                "Transformers with SAM3 support for the older facebook/sam3 model."
            )

        self._loaded = True

    def _load_native_sam31(self) -> None:
        if not SAM3_NATIVE_AVAILABLE:
            raise ImportError(
                "SAM3.1 requires the latest facebookresearch/sam3 package. "
                "Clone https://github.com/facebookresearch/sam3 and run pip install -e ."
            )
        if build_sam3_predictor is None:
            raise ImportError(
                "The installed sam3 package is too old for SAM3.1. Pull the latest "
                "facebookresearch/sam3 code and reinstall it."
            )

        _apply_sam3_runtime_patches()

        kwargs = {
            "version": "sam3.1",
            "checkpoint_path": self._checkpoint_path,
            "compile": _env_bool("PIGEONLAB_SAM3_COMPILE", False),
            "warm_up": _env_bool("PIGEONLAB_SAM3_WARM_UP", False),
            "max_num_objects": int(os.getenv("PIGEONLAB_SAM3_MAX_OBJECTS", "16")),
            "multiplex_count": int(os.getenv("PIGEONLAB_SAM3_MULTIPLEX_COUNT", "16")),
            "use_fa3": _env_bool("PIGEONLAB_SAM3_USE_FA3", False),
            "use_rope_real": _env_bool("PIGEONLAB_SAM3_USE_ROPE_REAL", True),
            "async_loading_frames": _env_bool("PIGEONLAB_SAM3_ASYNC_LOADING", True),
        }
        logger.info("Loading SAM3.1 native video predictor on %s", self._device)
        self._video_predictor = build_sam3_predictor(**kwargs)
        self._using_native = True

    def _load_native_sam3(self) -> None:
        if not SAM3_NATIVE_AVAILABLE:
            raise ImportError("Native sam3 package is not installed.")

        kwargs = {
            "checkpoint_path": self._checkpoint_path,
            "load_from_HF": self._checkpoint_path is None and _env_bool("PIGEONLAB_ALLOW_HF_DOWNLOAD", False),
            "device": self._device,
            "compile": _env_bool("PIGEONLAB_SAM3_COMPILE", False),
        }
        logger.info("Loading SAM3 native video predictor on %s", self._device)
        try:
            self._video_predictor = build_sam3_video_predictor(**kwargs)
        except TypeError:
            self._video_predictor = build_sam3_video_predictor()
        self._using_native = True

    def _load_transformers_sam3(self) -> None:
        if not SAM3_TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers SAM3 classes are not installed.")
        model_ref = _model_ref_for_transformers(self._version)
        dtype = _cuda_dtype() if self._device.startswith("cuda") else torch.float32

        logger.info("Loading SAM3 Transformers video model from %s on %s", model_ref, self._device)
        self._video_model = Sam3VideoModel.from_pretrained(model_ref).to(self._device, dtype=dtype)
        self._video_processor = HFSam3VideoProcessor.from_pretrained(model_ref)
        self._using_native = False

    def _ensure_image_model(self) -> None:
        if self._image_model is not None and self._image_processor is not None:
            return

        if self._using_native:
            kwargs = {
                "checkpoint_path": self._checkpoint_path,
                "load_from_HF": self._checkpoint_path is None and _env_bool("PIGEONLAB_ALLOW_HF_DOWNLOAD", False),
                "device": self._device,
            }
            self._image_model = build_sam3_image_model(**kwargs)
            self._image_processor = NativeSam3Processor(self._image_model)
            return

        if not SAM3_TRANSFORMERS_AVAILABLE:
            raise RuntimeError("No SAM3 image model backend is available.")

        model_ref = _model_ref_for_transformers(self._version)
        self._image_model = Sam3Model.from_pretrained(model_ref).to(self._device)
        self._image_processor = HFSam3Processor.from_pretrained(model_ref)

    def predict_frame(
        self,
        frame_bgr: np.ndarray,
        text_prompt: str,
        confidence_threshold: float = 0.5,
    ) -> list[dict]:
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        self._ensure_image_model()
        rgb = frame_bgr[:, :, ::-1]
        image = Image.fromarray(rgb)

        if self._using_native:
            inference_state = self._image_processor.set_image(image)
            output = self._image_processor.set_text_prompt(
                state=inference_state,
                prompt=text_prompt,
            )
            return self._parse_detection_container(output, confidence_threshold)

        inputs = self._image_processor(images=image, text=text_prompt, return_tensors="pt").to(self._device)
        with torch.no_grad():
            outputs = self._image_model(**inputs)
        results = self._image_processor.post_process_instance_segmentation(
            outputs,
            threshold=confidence_threshold,
            mask_threshold=0.5,
            target_sizes=inputs.get("original_sizes").tolist(),
        )[0]
        return self._parse_detection_container(results, confidence_threshold)

    def start_video_session(self, video_path: str) -> str:
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        if self._using_native:
            offload_video_to_cpu = _env_bool("PIGEONLAB_SAM3_OFFLOAD_VIDEO_TO_CPU", True)
            response = self._video_predictor.handle_request(
                request={
                    "type": "start_session",
                    "resource_path": video_path,
                    "offload_video_to_cpu": offload_video_to_cpu,
                },
            )
            return str(response["session_id"])

        from transformers.video_utils import load_video  # type: ignore[import-untyped]

        video_frames, _ = load_video(video_path)
        dtype = _cuda_dtype() if self._device.startswith("cuda") else torch.float32
        inference_session = self._video_processor.init_video_session(
            video=video_frames,
            inference_device=self._device,
            processing_device="cpu",
            video_storage_device="cpu",
            dtype=dtype,
        )
        session_id = str(uuid.uuid4())
        self._video_sessions[session_id] = inference_session
        return session_id

    def predict_video_frame(self, session_id: str, frame_index: int, text_prompt: str) -> list[dict]:
        detections = self.propagate_video(session_id, text_prompt, max_frames=frame_index + 1)
        return detections.get(frame_index, [])

    def propagate_video(
        self,
        session_id: str,
        text_prompt: str,
        max_frames: int = 10000,
        cancel_check: Callable[[], None] | None = None,
    ) -> dict[int, list[dict]]:
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        if self._using_native:
            return self._propagate_native(session_id, text_prompt, max_frames, cancel_check)
        return self._propagate_transformers(session_id, text_prompt, max_frames, cancel_check)

    def _propagate_native(
        self,
        session_id: str,
        text_prompt: str,
        max_frames: int,
        cancel_check: Callable[[], None] | None = None,
    ) -> dict[int, list[dict]]:
        if cancel_check is not None:
            cancel_check()
        response = self._video_predictor.handle_request(
            request={
                "type": "add_prompt",
                "session_id": session_id,
                "frame_index": 0,
                "text": text_prompt,
            },
        )

        results: dict[int, list[dict]] = {}
        initial = self._parse_native_response(response)
        if initial:
            results[0] = initial

        if hasattr(self._video_predictor, "handle_stream_request"):
            # Do not pass a bounded max-frame argument into native SAM3.1 here.
            # Some Windows workstation runs hit an upstream multiplex edge case
            # at the bounded propagation finalization step. Streaming unbounded
            # and stopping client-side avoids that path while keeping inference
            # results identical for the frames we consume.
            stream = self._video_predictor.handle_stream_request(
                request={"type": "propagate_in_video", "session_id": session_id},
            )
            for packet in stream:
                if cancel_check is not None:
                    cancel_check()
                frame_idx = self._extract_frame_idx(packet, len(results))
                if frame_idx >= max_frames:
                    break
                results[frame_idx] = self._parse_native_response(packet)
            return results

        for frame_idx in range(max_frames):
            if cancel_check is not None:
                cancel_check()
            response = self._video_predictor.handle_request(
                request={
                    "type": "get_frame",
                    "session_id": session_id,
                    "frame_index": frame_idx,
                },
            )
            if response.get("done"):
                break
            results[frame_idx] = self._parse_native_response(response)
        return results

    def _propagate_transformers(
        self,
        session_id: str,
        text_prompt: str,
        max_frames: int,
        cancel_check: Callable[[], None] | None = None,
    ) -> dict[int, list[dict]]:
        session = self._video_sessions[session_id]
        if cancel_check is not None:
            cancel_check()
        session = self._video_processor.add_text_prompt(
            inference_session=session,
            text=text_prompt,
        )
        self._video_sessions[session_id] = session

        results: dict[int, list[dict]] = {}
        for model_outputs in self._video_model.propagate_in_video_iterator(
            inference_session=session,
            max_frame_num_to_track=max_frames,
        ):
            if cancel_check is not None:
                cancel_check()
            processed = self._video_processor.postprocess_outputs(session, model_outputs)
            frame_idx = int(model_outputs.frame_idx)
            results[frame_idx] = self._parse_detection_container(processed)
        return results

    def close_video_session(self, session_id: str) -> None:
        try:
            if self._using_native and self._video_predictor is not None:
                try:
                    self._video_predictor.handle_request(
                        request={"type": "close_session", "session_id": session_id},
                    )
                except Exception:
                    logger.debug("SAM3 native close_session ignored for %s", session_id, exc_info=True)
                return
            self._video_sessions.pop(session_id, None)
        finally:
            self._empty_cuda_cache(f"after close_video_session session_id={session_id}")

    def _empty_cuda_cache(self, reason: str) -> None:
        if not TORCH_AVAILABLE or torch is None:
            return
        cuda = getattr(torch, "cuda", None)
        if cuda is None or not cuda.is_available():
            return
        before_allocated = cuda.memory_allocated()
        before_reserved = cuda.memory_reserved()
        cuda.empty_cache()
        after_allocated = cuda.memory_allocated()
        after_reserved = cuda.memory_reserved()
        logger.info(
            "SAM3 CUDA cleanup %s allocated_gb %.2f -> %.2f reserved_gb %.2f -> %.2f",
            reason,
            before_allocated / (1024 ** 3),
            after_allocated / (1024 ** 3),
            before_reserved / (1024 ** 3),
            after_reserved / (1024 ** 3),
        )

    @staticmethod
    def _extract_frame_idx(packet: dict, fallback: int) -> int:
        for key in ("frame_idx", "frame_index", "ann_frame_idx", "output_frame_idx"):
            if key in packet:
                try:
                    return int(packet[key])
                except (TypeError, ValueError):
                    pass
        return fallback

    def _parse_native_response(self, response: Any) -> list[dict]:
        if response is None:
            return []
        if isinstance(response, dict):
            if "outputs" in response:
                return self._parse_detection_container(response["outputs"])
            return self._parse_detection_container(response)
        return self._parse_detection_container(response)

    @classmethod
    def _parse_detection_container(
        cls,
        container: Any,
        confidence_threshold: float = 0.0,
    ) -> list[dict]:
        if container is None:
            return []

        if isinstance(container, list):
            detections = [cls._parse_single_detection(item, idx) for idx, item in enumerate(container)]
            return cls._finalize_detections(detections, confidence_threshold)

        if isinstance(container, dict):
            masks = container.get("masks", container.get("out_binary_masks", []))
            boxes = container.get("boxes", container.get("bboxes", []))
            scores = container.get("scores", container.get("object_scores", []))
            object_ids = container.get("object_ids", container.get("obj_ids", []))

            masks_np = cls._as_numpy(masks)
            boxes_np = cls._as_numpy(boxes)
            scores_np = cls._as_numpy(scores)
            object_ids_np = cls._as_numpy(object_ids)

            count = cls._container_count(masks_np, boxes_np, scores_np, object_ids_np)
            detections = []
            for idx in range(count):
                mask = cls._index_or_none(masks_np, idx)
                if mask is not None and mask.ndim == 3 and mask.shape[0] == 1:
                    mask = mask[0]
                bbox = cls._index_or_none(boxes_np, idx)
                if bbox is None and mask is not None:
                    bbox = cls._bbox_from_mask(mask)
                score = cls._scalar_at(scores_np, idx, default=1.0)
                obj_id = int(cls._scalar_at(object_ids_np, idx, default=idx))
                detections.append({
                    "mask": mask.astype(bool) if mask is not None else None,
                    "bbox": cls._normalize_bbox(bbox),
                    "confidence": round(float(score), 4),
                    "obj_id": obj_id,
                })
            return cls._finalize_detections(detections, confidence_threshold)

        return []

    @classmethod
    def _parse_single_detection(cls, item: Any, idx: int) -> dict:
        if not isinstance(item, dict):
            return {"mask": None, "bbox": [0, 0, 0, 0], "confidence": 1.0, "obj_id": idx}
        mask = cls._as_numpy(item.get("mask", item.get("masks")))
        if mask is not None and mask.ndim == 3 and mask.shape[0] == 1:
            mask = mask[0]
        bbox = item.get("box", item.get("bbox", item.get("boxes")))
        if bbox is None and mask is not None:
            bbox = cls._bbox_from_mask(mask)
        return {
            "mask": mask.astype(bool) if mask is not None else None,
            "bbox": cls._normalize_bbox(cls._as_numpy(bbox)),
            "confidence": round(float(item.get("score", item.get("confidence", 1.0))), 4),
            "obj_id": int(item.get("object_id", item.get("obj_id", idx))),
        }

    @staticmethod
    def _as_numpy(value: Any) -> np.ndarray | None:
        if value is None:
            return None
        if TORCH_AVAILABLE and isinstance(value, torch.Tensor):
            tensor = value.detach()
            # NumPy cannot represent bfloat16, and downstream review/overlay code
            # only needs CPU arrays. Promote half-precision outputs before export.
            if tensor.dtype in (torch.bfloat16, torch.float16):
                tensor = tensor.float()
            return tensor.cpu().numpy()
        if isinstance(value, np.ndarray):
            return value
        if isinstance(value, (list, tuple)) and len(value) == 0:
            return np.array([])
        try:
            return np.asarray(value)
        except Exception:
            return None

    @staticmethod
    def _container_count(*arrays: np.ndarray | None) -> int:
        for arr in arrays:
            if arr is not None and arr.ndim > 0 and arr.shape[0] > 0:
                return int(arr.shape[0])
        return 0

    @staticmethod
    def _index_or_none(arr: np.ndarray | None, idx: int) -> np.ndarray | None:
        if arr is None or arr.size == 0 or arr.ndim == 0 or idx >= arr.shape[0]:
            return None
        return arr[idx]

    @staticmethod
    def _scalar_at(arr: np.ndarray | None, idx: int, default: float) -> float:
        if arr is None or arr.size == 0:
            return default
        try:
            return float(arr.reshape(-1)[idx])
        except (IndexError, TypeError, ValueError):
            return default

    @staticmethod
    def _bbox_from_mask(mask: np.ndarray) -> list[int]:
        if mask is None or mask.size == 0:
            return [0, 0, 0, 0]
        ys, xs = np.where(mask.astype(bool))
        if len(xs) == 0 or len(ys) == 0:
            return [0, 0, 0, 0]
        return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]

    @staticmethod
    def _normalize_bbox(bbox: Any) -> list[int]:
        arr = np.asarray(bbox if bbox is not None else [0, 0, 0, 0]).reshape(-1)
        if arr.size < 4:
            return [0, 0, 0, 0]
        return [int(arr[0]), int(arr[1]), int(arr[2]), int(arr[3])]

    @staticmethod
    def _finalize_detections(detections: list[dict], confidence_threshold: float) -> list[dict]:
        kept = [
            d for d in detections
            if d["confidence"] >= confidence_threshold and d["bbox"] != [0, 0, 0, 0]
        ]
        kept.sort(key=lambda d: d["confidence"], reverse=True)
        return kept


_instance: SAM3Wrapper | None = None


def get_sam3(
    model_id: str | None = None,
    checkpoint_path: str | None = None,
    version: str | None = None,
) -> SAM3Wrapper:
    """Return the module-level SAM3 wrapper, loading it on first use."""
    global _instance

    if _instance is not None:
        return _instance

    wrapper = SAM3Wrapper(
        model_id=model_id,
        checkpoint_path=checkpoint_path,
        version=version,
    )
    wrapper.load()
    _instance = wrapper
    return _instance


def reset_sam3() -> None:
    """Reset the module-level singleton, allowing a fresh load."""
    global _instance
    _instance = None
