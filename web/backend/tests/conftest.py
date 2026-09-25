"""Tests run inside the container (they use the baked LDraw library, indexes and
LeoCAD):

    docker compose exec leocad-app bash -c \
        "pip install -q --break-system-packages -r /app/web/backend/requirements-dev.txt && cd /app/web/backend && pytest -q"

/data and /config are redirected to temp folders before any app module is imported.
"""
import os
import sys
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="leocad-web-tests-"))
os.environ["LEOCAD_DATA_DIR"] = str(_tmp / "data")
os.environ["LEOCAD_WEB_CONFIG_DIR"] = str(_tmp / "config")
(_tmp / "data" / "output").mkdir(parents=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # web/backend
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))          # repo root: leocad_render

import pytest  # noqa: E402


@pytest.fixture
def data_dir() -> Path:
    return _tmp / "data"
