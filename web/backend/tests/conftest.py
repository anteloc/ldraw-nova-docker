"""Tests run inside the container (they use the baked LDraw library, indexes and
LeoCAD):

    docker compose exec ldraw-nova-app bash -c \
        "pip install -q --break-system-packages -r /app/web/backend/requirements-dev.txt && cd /app/web/backend && pytest -q"

/data and /config are redirected to temp folders before any app module is imported.
"""
import os
import sys
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="ldraw-nova-web-tests-"))
os.environ["LDRAW_NOVA_DATA_DIR"] = str(_tmp / "data")
os.environ["LDRAW_NOVA_WEB_CONFIG_DIR"] = str(_tmp / "config")
os.environ["LDRAW_NOVA_GLB_CACHE_DIR"] = str(_tmp / "glb-cache")
os.environ["LDRAW_NOVA_GALLERY_MODELS_DIR"] = str(_tmp / "models-gallery")     # not the image's gallery models
(_tmp / "data" / "output").mkdir(parents=True)
(_tmp / "models-gallery").mkdir()

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # web/backend
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))          # repo root: leocad_render

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def offline_model_details(monkeypatch):
    """Unit tests never depend on live catalogues or send provider credentials."""
    import model_discovery
    async def unavailable(*args, **kwargs):
        raise RuntimeError("Catalogue offline in tests")
    monkeypatch.setattr(model_discovery, "_fetch_json", unavailable)


@pytest.fixture
def data_dir() -> Path:
    return _tmp / "data"


@pytest.fixture
def gallery_dir() -> Path:
    return _tmp / "models-gallery"
