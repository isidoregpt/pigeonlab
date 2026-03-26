"""PigeonLab pre-flight environment check.

Run this script to verify that all required components are installed
and configured before starting PigeonLab::

    python backend/scripts/setup_check.py

Each check prints a pass/fail indicator and a short status message.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

passes = 0
failures = 0
failed_items: list[str] = []


def check(label: str, passed: bool, msg: str, fix: str = "") -> None:
    """Print a single check result and update counters."""
    global passes, failures
    if passed:
        print(f"  \u2705 {label}: {msg}")
        passes += 1
    else:
        print(f"  \u274c {label}: {msg}")
        failures += 1
        failed_items.append(f"{label}: {fix}" if fix else f"{label}: {msg}")


def run_checks() -> None:
    """Run all environment checks."""
    print("=" * 60)
    print("  PigeonLab Environment Check")
    print("=" * 60)
    print()

    # 1. Python >= 3.10
    v = sys.version_info
    check(
        "Python >= 3.10",
        v >= (3, 10),
        f"Python {v.major}.{v.minor}.{v.micro}",
        "Install Python 3.10 or later from python.org",
    )

    # 2. PyTorch installed
    try:
        import torch
        check("PyTorch installed", True, f"torch {torch.__version__}")
    except ImportError:
        check("PyTorch installed", False, "Not installed",
              "pip install torch torchvision")

    # 3. CUDA available
    try:
        import torch
        cuda = torch.cuda.is_available()
        check("CUDA available", cuda,
              "Yes" if cuda else "No (CPU-only mode)")
    except ImportError:
        check("CUDA available", False, "PyTorch not installed")

    # 4. GPU name
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            check("GPU detected", True, name)
        else:
            check("GPU detected", False, "No GPU found",
                  "Install CUDA-compatible GPU drivers")
    except ImportError:
        check("GPU detected", False, "PyTorch not installed")

    # 5. PyTorch version >= 2.7
    try:
        import torch
        parts = torch.__version__.split(".")
        major = int(parts[0])
        minor = int(parts[1].split("+")[0].split("a")[0].split("b")[0].split("rc")[0])
        ok = (major, minor) >= (2, 7)
        check("PyTorch >= 2.7", ok, f"torch {torch.__version__}",
              "pip install --upgrade torch torchvision")
    except ImportError:
        check("PyTorch >= 2.7", False, "Not installed",
              "pip install torch torchvision")

    # 6. SAM 3 installed
    try:
        from sam3.model_builder import build_sam3_image_model  # noqa: F401
        check("SAM 3 installed", True, "sam3 package found")
    except ImportError:
        check("SAM 3 installed", False, "Not installed",
              "git clone https://github.com/facebookresearch/sam3.git && "
              "cd sam3 && pip install -e . && cd ..")

    # 7. SAM 3 checkpoint exists
    ckpt = PROJECT_ROOT / "data" / "models" / "sam3" / "sam3_hiera_large.pt"
    check(
        "SAM 3 checkpoint",
        ckpt.exists(),
        str(ckpt) if ckpt.exists() else "Not found",
        "python backend/scripts/download_sam3.py "
        "(filename may vary — check huggingface.co/facebook/sam3)",
    )

    # 8. aiosqlite installed
    try:
        import aiosqlite  # noqa: F401
        check("aiosqlite installed", True, "OK")
    except ImportError:
        check("aiosqlite installed", False, "Not installed",
              "pip install aiosqlite>=0.19.0")

    # 9. opencv-python installed
    try:
        import cv2
        check("opencv-python installed", True, f"cv2 {cv2.__version__}")
    except ImportError:
        check("opencv-python installed", False, "Not installed",
              "pip install opencv-python>=4.8.0")

    # 10. huggingface_hub installed
    try:
        import huggingface_hub  # noqa: F401
        check("huggingface_hub installed", True, "OK")
    except ImportError:
        check("huggingface_hub installed", False, "Not installed",
              "pip install huggingface_hub>=0.20.0")

    # 11. Node.js available
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            check("Node.js available", True, result.stdout.strip())
        else:
            check("Node.js available", False, "node command failed",
                  "Install Node.js from nodejs.org")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        check("Node.js available", False, "Not found",
              "Install Node.js from nodejs.org")

    # 12. frontend/node_modules exists
    nm = PROJECT_ROOT / "frontend" / "node_modules"
    check(
        "frontend/node_modules",
        nm.exists(),
        "OK" if nm.exists() else "Not found",
        "cd frontend && npm install",
    )

    # 13. data/models/sam3/ directory exists
    model_dir = PROJECT_ROOT / "data" / "models" / "sam3"
    check(
        "data/models/sam3/ exists",
        model_dir.exists(),
        "OK" if model_dir.exists() else "Not found",
        "mkdir -p data/models/sam3 && python backend/scripts/download_sam3.py",
    )

    # 14. Database exists
    db = PROJECT_ROOT / "data" / "pigeonlab.db"
    check(
        "Database (pigeonlab.db)",
        db.exists(),
        "OK" if db.exists() else "Not found",
        "Run the backend once to auto-create the database",
    )

    # Summary
    print()
    print("-" * 60)
    total = passes + failures
    print(f"  Results: {passes}/{total} checks passed")
    print()

    if failures == 0:
        print("  \U0001f389 PigeonLab is fully ready! Run start.bat to launch.")
    else:
        print(f"  \u26a0\ufe0f  {failures} item(s) need attention before PigeonLab will work.")
        print()
        print("  NEXT STEPS:")
        for item in failed_items:
            print(f"    \u2022 {item}")

    print()


if __name__ == "__main__":
    run_checks()
