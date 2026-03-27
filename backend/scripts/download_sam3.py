"""Download the SAM 3 model files from Hugging Face.

Prerequisites:
    1. Request access at https://huggingface.co/facebook/sam3
    2. Run ``hf auth login`` to authenticate with your Hugging Face token.
    3. Then run this script::

        python backend/scripts/download_sam3.py

The model files are saved to ``data/models/sam3/`` in the project root.
An active internet connection is required.
"""

from pathlib import Path

SAM3_REPO_ID = "facebook/sam3"

# Resolve paths relative to the project root (two levels up from this script)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "data" / "models" / "sam3"

# Import GatedRepoError if available for specific access-denied handling
try:
    from huggingface_hub.errors import GatedRepoError

    HF_GATED_ERROR = GatedRepoError
except ImportError:
    HF_GATED_ERROR = Exception


def download() -> None:
    """Download the SAM 3 model files to *MODEL_DIR*."""
    print(
        "=== PigeonLab — SAM 3 Model Downloader ===\n"
        f"Repository : {SAM3_REPO_ID}\n"
        f"Destination: {MODEL_DIR}\n"
    )

    try:
        from huggingface_hub import snapshot_download  # noqa: F811
    except ImportError:
        print(
            "\nError: the 'huggingface_hub' package is not installed.\n"
            "Install it with:\n\n"
            "  pip install huggingface_hub>=0.20.0\n"
        )
        raise SystemExit(1)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    print(
        "Downloading SAM 3 model files from Hugging Face (facebook/sam3).\n"
        "This is approximately 3-4 GB total including all model weights.\n"
        "Please be patient..."
    )

    snapshot_download(
        repo_id=SAM3_REPO_ID,
        local_dir=str(MODEL_DIR),
        ignore_patterns=["*.md", "*.txt", "assets/*"],
    )

    print(
        f"\nSAM 3 downloaded to {MODEL_DIR}.\n"
        "You can now start PigeonLab."
    )


if __name__ == "__main__":
    try:
        download()
    except KeyboardInterrupt:
        print("\n\nDownload cancelled.")
    except HF_GATED_ERROR:
        print(
            "\nAccess denied. You need to:\n"
            "  1. Go to https://huggingface.co/facebook/sam3\n"
            "  2. Click 'Request access' and wait for approval email\n"
            "  3. Run: hf auth login\n"
            "  4. Then run this script again"
        )
        raise SystemExit(1)
    except Exception as exc:
        print(
            f"\nDownload failed: {exc}\n\n"
            "Please check your internet connection and try again.\n"
            "If the problem persists, you can download the files manually from:\n"
            f"  https://huggingface.co/{SAM3_REPO_ID}"
        )
        raise SystemExit(1)
