"""Download the SAM3 (SAM2.1) model checkpoint and config from Hugging Face.

Run this script once before starting PigeonLab for the first time::

    python backend/scripts/download_sam3.py

The checkpoint (~900 MB) and config file are saved to ``data/models/sam3/``
in the project root. An active internet connection is required.
"""

import shutil
from pathlib import Path

REPO_ID = "facebook/sam2.1-hiera-large"
CHECKPOINT_FILENAME = "sam2.1_hiera_large.pt"
CONFIG_FILENAME = "sam2.1_hiera_l.yaml"

# Resolve paths relative to the project root (two levels up from this script)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "data" / "models" / "sam3"


def download() -> None:
    """Download the SAM2.1 large checkpoint and config to *MODEL_DIR*."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print(
            "\nError: the 'huggingface_hub' package is not installed.\n"
            "Install it with:\n\n"
            "  pip install huggingface_hub>=0.20.0\n"
        )
        raise SystemExit(1)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # ── Checkpoint ──────────────────────────────────────────
    checkpoint_dest = MODEL_DIR / CHECKPOINT_FILENAME
    if checkpoint_dest.exists():
        print(f"Checkpoint already exists at {checkpoint_dest}")
    else:
        print(
            "Downloading SAM3 model checkpoint "
            "(this is about 900 MB, please be patient)..."
        )
        cached_path = hf_hub_download(
            repo_id=REPO_ID,
            filename=CHECKPOINT_FILENAME,
        )
        shutil.copy2(cached_path, checkpoint_dest)
        print(f"Checkpoint saved to {checkpoint_dest}")

    # ── Config ──────────────────────────────────────────────
    config_dest = MODEL_DIR / CONFIG_FILENAME
    if config_dest.exists():
        print(f"Config already exists at {config_dest}")
    else:
        print("Downloading SAM3 model config...")
        cached_path = hf_hub_download(
            repo_id=REPO_ID,
            filename=CONFIG_FILENAME,
        )
        shutil.copy2(cached_path, config_dest)
        print(f"Config saved to {config_dest}")

    # ── Done ────────────────────────────────────────────────
    print(
        "\nAll done! SAM3 model files are ready at:\n"
        f"  {MODEL_DIR}\n\n"
        "You can now start PigeonLab."
    )


if __name__ == "__main__":
    try:
        download()
    except KeyboardInterrupt:
        print("\n\nDownload cancelled.")
    except Exception as exc:
        print(
            f"\nDownload failed: {exc}\n\n"
            "Please check your internet connection and try again.\n"
            "If the problem persists, you can download the files manually from:\n"
            f"  https://huggingface.co/{REPO_ID}"
        )
        raise SystemExit(1)
