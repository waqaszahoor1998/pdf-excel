"""
Load extraction and app config from environment and optional config file.

No hardcoded defaults for business logic: limits, paths, and modes come from
environment variables or from a JSON config file. Fallbacks only for
sensible defaults so the app runs without a config file.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Optional config file path (env overrides)
CONFIG_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config" / "extract.json"


def _env_int(key: str, default: int | None = None) -> int | None:
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    v = os.environ.get(key, "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return default


def _env_str(key: str, default: str | None = None) -> str | None:
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    return v.strip()


def load_config(config_path: str | Path | None = None) -> dict:
    """
    Load config from optional JSON file and override with environment variables.

    Config file keys (all optional): max_pdf_bytes, max_pages, query_max_length,
    extraction_mode, system_prompt_path, prompts_dir, use_structured_output,
    structured_schema_path, long_pdf_enabled, long_pdf_chunk_pages, default_model.

    Environment variables override file (e.g. EXTRACTION_MODE, MAX_PDF_BYTES).
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    data = {}
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}

    def get(key: str, env_key: str | None = None, default=None):
        env_key = env_key or key.upper()
        env_val = os.environ.get(env_key)
        if env_val is not None and env_val != "":
            if isinstance(default, bool):
                return env_val.strip().lower() in ("1", "true", "yes", "on")
            if isinstance(default, int):
                try:
                    return int(env_val)
                except ValueError:
                    return default
            return env_val.strip()
        return data.get(key, default)

    return {
        "max_pdf_bytes": get("max_pdf_bytes", "MAX_PDF_BYTES", 32 * 1024 * 1024),
        "max_pages": get("max_pages", "MAX_PAGES", 100),
        "query_max_length": get("query_max_length", "QUERY_MAX_LENGTH", 8000),
        "extraction_mode": get("extraction_mode", "EXTRACTION_MODE", "single"),
        "system_prompt_path": get("system_prompt_path", "SYSTEM_PROMPT_PATH"),
        "prompts_dir": get("prompts_dir", "PROMPTS_DIR", str(CONFIG_DIR / "prompts")),
        "use_structured_output": get("use_structured_output", "USE_STRUCTURED_OUTPUT", False),
        "structured_schema_path": get("structured_schema_path", "STRUCTURED_SCHEMA_PATH"),
        "long_pdf_enabled": get("long_pdf_enabled", "LONG_PDF_ENABLED", False),
        "long_pdf_chunk_pages": get("long_pdf_chunk_pages", "LONG_PDF_CHUNK_PAGES", 25),
        "default_model": get("default_model", "ANTHROPIC_MODEL"),
    }


def get_system_prompt_path(config: dict, mode: str | None = None) -> Path | None:
    """Resolve path to system prompt file. Prefer explicit path, else prompts_dir + mode."""
    explicit = config.get("system_prompt_path")
    if explicit:
        p = Path(explicit)
        if p.is_absolute():
            return p if p.exists() else None
        candidate = CONFIG_DIR / explicit
        return candidate if candidate.exists() else p
    mode = mode or config.get("extraction_mode", "single")
    raw = config.get("prompts_dir") or ""
    prompts_dir = Path(raw) if raw else CONFIG_DIR / "prompts"
    if not prompts_dir.is_absolute():
        prompts_dir = CONFIG_DIR / prompts_dir
    for name in (f"extraction_{mode}.txt", "extraction_single.txt", "extraction.txt"):
        candidate = prompts_dir / name
        if candidate.exists():
            return candidate
    return None
