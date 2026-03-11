#!/usr/bin/env python3
"""
Download Qwen2.5-VL-7B-Instruct GGUF model and mmproj (vision encoder) from Hugging Face.

Usage:
  python scripts/download_qwen2vl.py [--dir MODELS_DIR]

Default dir: ./models/qwen2.5-vl-7b (or set QWEN2VL_MODEL_DIR in .env).
Files: Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf (~4.7 GB), mmproj-Qwen2.5-VL-7B-Instruct-f16.gguf (~1.35 GB).
"""

import argparse
import os
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPO_ID = "ggml-org/Qwen2.5-VL-7B-Instruct-GGUF"
MODEL_FILENAME = "Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf"
MMPROJ_FILENAME = "mmproj-Qwen2.5-VL-7B-Instruct-f16.gguf"


def _default_dir() -> Path:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    env_dir = os.environ.get("QWEN2VL_MODEL_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return (ROOT / "models" / "qwen2.5-vl-7b").resolve()


def download():
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("Install huggingface_hub: pip install huggingface_hub", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Download Qwen2.5-VL-7B GGUF and mmproj")
    parser.add_argument("--dir", type=Path, default=None, help="Directory to save model files")
    args = parser.parse_args()

    out_dir = args.dir or _default_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading to {out_dir}")

    for filename in (MODEL_FILENAME, MMPROJ_FILENAME):
        dest = out_dir / filename
        if dest.exists():
            print(f"  {filename} already exists, skip")
            continue
        print(f"  Downloading {filename} ...")
        path = hf_hub_download(
            repo_id=REPO_ID,
            filename=filename,
            local_dir=str(out_dir),
            local_dir_use_symlinks=False,
        )
        print(f"  -> {path}")

    print("Done. Set in .env:")
    print(f"  QWEN2VL_MODEL_DIR={out_dir}")
    print("  QWEN2VL_MMPROJ_PATH=")  # optional; if not set we use same dir + mmproj filename


if __name__ == "__main__":
    download()
