"""Filesystem locations used by the web app.

Everything defaults to the container layout (see Dockerfile); the env vars
exist so tests and local development can point them elsewhere.
"""
from __future__ import annotations

import os
from pathlib import Path

from leocad_render import DATA_DIR, GENERATED_DIR, OUTPUT_DIR

__all__ = [
    "DATA_DIR", "GENERATED_DIR", "CHATS_DIR", "OUTPUT_DIR", "WEB_DIRS",
    "CONFIG_DIR", "LDRAW_DIR", "DEMO_MODELS_DIR", "INDEX_DIR", "STATIC_DIR",
    "VIEWER_DIR", "VIEWER_VENDOR_DIR", "PLAYER_VENDOR_DIR", "XR_DIR", "PROMPTS_DIR",
]

# Shared with the host (bind mount):
#   generated/          the model collection (flat): <name>.mpd|.ldr|.dat + <name>.png snapshot
#   chats/<chat-id>/    one folder per chat: chat.json, messages.jsonl, models.jsonl, renders/
#   output/<chat-id>/   each chat's agent work folder (notes, plans, scratch files) — never served
CHATS_DIR = DATA_DIR / "chats"

# Top-level folders of /data the web UI may serve. output/ is agent-only.
WEB_DIRS = ("generated", "chats")

# LLM entries + API keys. A named volume, deliberately NOT under /data: agent
# code runs as another user and could otherwise read them.
CONFIG_DIR = Path(os.environ.get("LDRAW_ASTRA_WEB_CONFIG_DIR", "/config"))

# Baked into the image.
LDRAW_DIR = Path(os.environ.get("LEOCAD_LIB", "/opt/ldraw/ldraw"))
# Demo models (models-demo/ in the repo), shown with the collection. Each ships
# with its snapshot (.png) and BOM (.csv): nothing is made or written there.
DEMO_MODELS_DIR = Path(os.environ.get("LDRAW_ASTRA_DEMO_MODELS_DIR", "/opt/models-demo"))
INDEX_DIR = Path(os.environ.get("LDRAW_ASTRA_INDEX_DIR", "/opt/index"))
STATIC_DIR = Path(os.environ.get("LDRAW_ASTRA_WEB_STATIC_DIR", "/opt/web/static"))
VIEWER_DIR = Path(os.environ.get("LDRAW_ASTRA_WEB_VIEWER_DIR", "/opt/web/viewer"))                   # viewer.html
VIEWER_VENDOR_DIR = Path(os.environ.get("LDRAW_ASTRA_WEB_VIEWER_VENDOR_DIR", "/opt/web/viewer-vendor"))  # ldbi etc.
PLAYER_VENDOR_DIR = Path(os.environ.get("LDRAW_ASTRA_WEB_PLAYER_VENDOR_DIR", "/opt/web/player-vendor"))  # ldraw-player
XR_DIR = Path(os.environ.get("LDRAW_ASTRA_WEB_XR_DIR", "/opt/web/xr"))                                # web/xr build

PROMPTS_DIR = Path(__file__).parent / "prompts"
