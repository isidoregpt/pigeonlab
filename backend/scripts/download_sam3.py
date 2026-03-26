"""Download the SAM 3 model checkpoint and config from Hugging Face.

Prerequisites:
    1. Request access at https://huggingface.co/facebook/sam3
    2. Run ``hf auth login`` to authenticate with your Hugging Face token.
    3. Then run this script::

        python backend/scripts/download_sam3.py

The checkpoint and config file are saved to ``data/models/sam3/``
in the project root. An active internet connection is required.
"""

import shutil
from pathlib import Path

REPO_ID = "facebook/sam3"

# Placeholder filenames — verify the exact names at https://huggingface.co/facebook/sam3
SAM3_CHECKPOINT_FILENAME = "sam3_hiera_large.pt"
SAM3_CONFIG_FILENAME = "sam3_hiera_l.yaml"

# Resolve paths relative to the project root (two levels up from this script)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "data" / "models" / "sam3"


def download() -> None:
    """Download the SAM 3 large checkpoint and config to *MODEL_DIR*."""
    print(
        "=== PigeonLab — SAM 3 Checkpoint Downloader ===\n"
        f"Repository : {REPO_ID}\n"
        f"Destination: {MODEL_DIR}\n"
    )

    try:
        from huggingface_hub import hf_hub_download  # noqa: F811
    except ImportError:
        print(
            "\nError: the 'huggingface_hub' package is not installed.\n"
            "Install it with:\n\n"
            "  pip install huggingface_hub>=0.20.0\n"
        )
        raise SystemExit(1)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # ── Checkpoint ──────────────────────────────────────────
    checkpoint_dest = MODEL_DIR / SAM3_CHECKPOINT_FILENAME
    if checkpoint_dest.exists():
        print(f"Checkpoint already exists at {checkpoint_dest}")
    else:
        print(
            "Downloading SAM 3 model checkpoint "
            "(this may be ~900 MB, please be patient)..."
        )
        cached_path = hf_hub_download(
            repo_id=REPO_ID,
            filename=SAM3_CHECKPOINT_FILENAME,
        )
        shutil.copy2(cached_path, checkpoint_dest)
        print(f"Checkpoint saved to {checkpoint_dest}")

    # ── Config ──────────────────────────────────────────────
    config_dest = MODEL_DIR / SAM3_CONFIG_FILENAME
    if config_dest.exists():
        print(f"Config already exists at {config_dest}")
    else:
        print("Downloading SAM 3 model config...")
        cached_path = hf_hub_download(
            repo_id=REPO_ID,
            filename=SAM3_CONFIG_FILENAME,
        )
        shutil.copy2(cached_path, config_dest)
        print(f"Config saved to {config_dest}")

    # ── Done ────────────────────────────────────────────────
    print(
        f"\nAll files saved to:\n  {MODEL_DIR}\n\n"
        "SAM 3 checkpoint ready. You can now start PigeonLab."
    )


if __name__ == "__main__":
    try:
        download()
    except KeyboardInterrupt:
        print("\n\nDownload cancelled.")
    except (EnvironmentError, PermissionError) as exc:
        print(
            f"\nAccess error: {exc}\n\n"
            "This usually means you need to:\n"
            f"  1. Request access at https://huggingface.co/{REPO_ID}\n"
            "  2. Run: hf auth login\n"
            "Then retry this script."
        )
        raise SystemExit(1)
    except Exception as exc:
        print(
            f"\nDownload failed: {exc}\n\n"
            "Please check your internet connection and try again.\n"
            "If the problem persists, you can download the files manually from:\n"
            f"  https://huggingface.co/{REPO_ID}"
        )
        raise SystemExit(1)
