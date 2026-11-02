"""
Configuration manager for Type 1 File Upload Knowledge Assistant.
Safely loads environment variables without printing secret values.
"""

import os
from pathlib import Path
from typing import Set, Optional


def load_env_file(filepath: Optional[str] = None) -> None:
    """Safely loads key-value pairs from .env into os.environ if not already set."""
    env_path = filepath or os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception:
            pass


# Automatically load .env on module import
load_env_file()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Storage Paths
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(PROJECT_ROOT / "uploads")))
DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# File Upload Constraints
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "25"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

_allowed_raw = os.getenv("ALLOWED_EXTENSIONS", "pdf,docx,xlsx,csv,txt")
ALLOWED_EXTENSIONS: Set[str] = {ext.strip().lower().lstrip(".") for ext in _allowed_raw.split(",")}

# Chunking & Retrieval Parameters
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "5"))

# AI Configuration
AI_PROVIDER = os.getenv("AI_PROVIDER", "").strip().lower()
AI_MODEL_NAME = os.getenv("AI_MODEL_NAME", "gemini-2.5-flash")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()


def get_active_provider_name() -> str:
    """Detects active AI provider or returns empty if none configured."""
    if AI_PROVIDER in ("gemini", "openai", "mock"):
        return AI_PROVIDER
    if GEMINI_API_KEY:
        return "gemini"
    if OPENAI_API_KEY:
        return "openai"
    return "none"


def get_config_summary() -> dict:
    """Returns safe configuration summary with no secret values exposed."""
    return {
        "max_file_size_mb": MAX_FILE_SIZE_MB,
        "allowed_extensions": sorted(list(ALLOWED_EXTENSIONS)),
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "top_k_retrieval": TOP_K_RETRIEVAL,
        "configured_provider": get_active_provider_name(),
        "gemini_configured": bool(GEMINI_API_KEY),
        "openai_configured": bool(OPENAI_API_KEY),
    }
