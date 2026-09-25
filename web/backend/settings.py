"""Filesystem locations used by the web app.

Everything defaults to the container layout (see Dockerfile); the env vars
exist so tests and local development can point them elsewhere.
"""
from __future__ import annotations

import os
from pathlib import Path

from leocad_render import DATA_DIR, OUTPUT_DIR

__all__ = [
    "DATA_DIR", "OUTPUT_DIR", "GENERATED_DIR", "DB_PATH",
    "CONFIG_DIR", "LDRAW_DIR", "REF_MODELS_DIR", "INDEX_DIR", "STATIC_DIR",
    "VIEWER_DIR", "VIEWER_VENDOR_DIR", "PROMPTS_DIR",
]

# Shared with the host (bind mount).
GENERATED_DIR = DATA_DIR / "generated"          # agent models, one folder per chat

# LLM entries, API keys and chat history. A named volume, deliberately NOT
# under /data: agent code runs as another user and can write anywhere in
# /data (Docker Desktop bind mounts don't enforce ownership), but not here.
CONFIG_DIR = Path(os.environ.get("LEOCAD_WEB_CONFIG_DIR", "/config"))
DB_PATH = CONFIG_DIR / "chats.sqlite"

# Baked into the image.
LDRAW_DIR = Path(os.environ.get("LEOCAD_LIB", "/opt/ldraw/ldraw"))
REF_MODELS_DIR = Path(os.environ.get("LEOCAD_REF_MODELS_DIR", "/opt/models-annotated"))
INDEX_DIR = Path(os.environ.get("LEOCAD_INDEX_DIR", "/opt/index"))
STATIC_DIR = Path(os.environ.get("LEOCAD_WEB_STATIC_DIR", "/opt/web/static"))
VIEWER_DIR = Path(os.environ.get("LEOCAD_WEB_VIEWER_DIR", "/opt/web/viewer"))                   # viewer.html
VIEWER_VENDOR_DIR = Path(os.environ.get("LEOCAD_WEB_VIEWER_VENDOR_DIR", "/opt/web/viewer-vendor"))  # ldbi etc.

PROMPTS_DIR = Path(__file__).parent / "prompts"
