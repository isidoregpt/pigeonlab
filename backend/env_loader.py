"""Small .env loader used before optional dependencies are imported."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _strip_windows_unsupported_cuda_alloc_conf() -> None:
    """Remove CUDA allocator options that PyTorch parses but ignores on Windows."""
    if not sys.platform.startswith("win"):
        return
    raw = os.environ.get("PYTORCH_CUDA_ALLOC_CONF")
    if not raw or "expandable_segments" not in raw:
        return

    kept_tokens = [
        token
        for token in raw.split(",")
        if not token.strip().lower().startswith("expandable_segments")
    ]
    next_value = ",".join(token for token in kept_tokens if token.strip())
    os.environ["PIGEONLAB_STRIPPED_CUDA_ALLOC_CONF"] = "expandable_segments"
    os.environ["PIGEONLAB_ORIGINAL_CUDA_ALLOC_CONF"] = raw
    if next_value:
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = next_value
    else:
        os.environ.pop("PYTORCH_CUDA_ALLOC_CONF", None)


def load_env_file(path: str | Path | None = None, override: bool = False) -> dict[str, str]:
    """Load KEY=VALUE pairs from a .env file without adding a dependency."""
    env_path = Path(path) if path else Path(__file__).resolve().parent.parent / ".env"
    loaded: dict[str, str] = {}
    if not env_path.is_file():
        return loaded

    for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
        loaded[key] = value
    _strip_windows_unsupported_cuda_alloc_conf()
    return loaded
