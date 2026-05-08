"""Small .env loader used before optional dependencies are imported."""

from __future__ import annotations

import os
from pathlib import Path


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
    return loaded
