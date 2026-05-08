"""Download SAM 3 / SAM 3.1 model files from Hugging Face.

Prerequisites:
    1. Request access on the relevant Hugging Face model page.
    2. Run ``hf auth login`` to authenticate with your Hugging Face token.
    3. Run, for SAM3.1::

        python backend/scripts/download_sam3.py --version sam3.1

The model files are saved to ``data/models/{version}/`` in the project root.
An active internet connection is required.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

REPOS = {
    "sam3": "facebook/sam3",
    "sam3.1": "facebook/sam3.1",
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

try:
    from huggingface_hub.errors import GatedRepoError

    HF_GATED_ERROR = GatedRepoError
except ImportError:
    HF_GATED_ERROR = Exception


def download(version: str = "sam3.1") -> None:
    """Download the selected SAM model files to data/models/{version}."""
    repo_id = REPOS[version]
    model_dir = PROJECT_ROOT / "data" / "models" / version

    print(
        "=== PigeonLab - SAM Model Downloader ===\n"
        f"Version    : {version}\n"
        f"Repository : {repo_id}\n"
        f"Destination: {model_dir}\n"
    )

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print(
            "\nError: the 'huggingface_hub' package is not installed.\n"
            "Install it with:\n\n"
            "  pip install huggingface_hub>=0.20.0\n"
        )
        raise SystemExit(1)

    model_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"Downloading {version} model files from Hugging Face.\n"
        "This may be several GB including model weights.\n"
        "Please be patient..."
    )

    snapshot_download(
        repo_id=repo_id,
        local_dir=str(model_dir),
        ignore_patterns=["*.md", "*.txt", "assets/*"],
    )

    if version == "sam3.1":
        candidates = sorted(model_dir.glob("*.pt"))
        target = model_dir / "sam3.1_multiplex.pt"
        if candidates and not target.exists():
            try:
                os.replace(candidates[0], target)
            except OSError:
                pass

    print(f"\n{version} downloaded to {model_dir}.\nYou can now start PigeonLab.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download SAM model files for PigeonLab")
    parser.add_argument("--version", choices=sorted(REPOS), default="sam3.1")
    args = parser.parse_args()

    try:
        download(args.version)
    except KeyboardInterrupt:
        print("\n\nDownload cancelled.")
    except HF_GATED_ERROR:
        print(
            "\nAccess denied. You need to:\n"
            f"  1. Go to https://huggingface.co/{REPOS[args.version]}\n"
            "  2. Click 'Request access' and wait for approval\n"
            "  3. Run: hf auth login\n"
            "  4. Then run this script again"
        )
        raise SystemExit(1)
    except Exception as exc:
        print(
            f"\nDownload failed: {exc}\n\n"
            "Please check your internet connection and try again.\n"
            "If the problem persists, download the files manually from:\n"
            f"  https://huggingface.co/{REPOS[args.version]}"
        )
        raise SystemExit(1)
