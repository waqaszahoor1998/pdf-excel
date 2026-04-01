"""
Windows: OmniDocBench image paths can exceed the default MAX_PATH when cached under
%USERPROFILE%\\.cache\\huggingface\\... Hugging Face's symlink fallback can then
fail with FileNotFoundError when copying. Use a short HF_HOME and single-threaded
downloads before importing datasets / huggingface_hub.
"""

from __future__ import annotations

import os
from pathlib import Path


def apply_short_hf_home() -> Path | None:
    """
    On Windows, set HF_HOME to a short writable directory if not already set.
    Returns the HF_HOME path used, or None if unchanged (non-Windows or skip).
    """
    if os.name != "nt":
        return None
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"])

    candidates = [
        Path(r"C:\hf_cache"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "hf_cache",
    ]
    for base in candidates:
        if not base.parts:
            continue
        try:
            base.mkdir(parents=True, exist_ok=True)
            probe = base / ".hf_write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError:
            continue
        os.environ["HF_HOME"] = str(base.resolve())
        # Prefer plain copies on Windows when symlinks are unavailable (avoids half-broken cache states).
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
        return base.resolve()
    return None
