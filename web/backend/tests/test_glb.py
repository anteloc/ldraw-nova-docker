from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import glb
from main import app


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(glb, "CACHE_DIR", tmp_path / "cache")


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("collection", ["generated", "gallery", "demo"])
@pytest.mark.parametrize("folder", ["", "nested/"])
def test_sibling_is_canonical_even_over_cached_conversion(client, data_dir, gallery_dir, monkeypatch, collection, folder):
    root = data_dir / "generated" if collection == "generated" else gallery_dir
    root = root / folder
    root.mkdir(exist_ok=True, parents=True)
    model = root / "alternate model.mpd"
    model.write_text("0 Original LDraw model\n")
    sibling = model.with_suffix(".glb")
    sibling.write_bytes(b"glTF-authored-with-animations")
    cached = glb._cached_path(model)
    cached.parent.mkdir(exist_ok=True)
    cached.write_bytes(b"glTF-old-conversion")
    convert = AsyncMock(side_effect=AssertionError("must not convert an authored GLB"))
    monkeypatch.setattr(glb, "_convert", convert)
    prefix = {"generated": "/files/generated/", "gallery": "/gallery-files/", "demo": "/demo/"}[collection]
    url = prefix + folder + "alternate%20model.mpd"

    for existing_only in (True, False):
        response = client.get("/api/glb", params={"url": url, "existing_only": existing_only})
        assert response.status_code == 200
        assert response.content == sibling.read_bytes()
        assert response.headers["content-type"] == "model/gltf-binary"
        assert response.headers["cache-control"] == "no-cache"

    sibling.write_bytes(b"glTF-updated-alternate")
    assert client.get("/api/glb", params={"url": url}).content == sibling.read_bytes()
    # MPD URLs remain MPD for the player and the original-source download.
    assert client.get(url).text == model.read_text()
    sibling.unlink()
    assert client.get("/api/glb", params={"url": url, "existing_only": True}).status_code == 404
    assert client.get("/api/glb", params={"url": url}).content == cached.read_bytes()
    convert.assert_not_called()


def test_viewer_probe_does_not_generate_or_use_the_other_collection(client, data_dir, gallery_dir, monkeypatch):
    generated = data_dir / "generated"
    generated.mkdir(exist_ok=True)
    model = generated / "only-in-gallery.mpd"
    model.write_text("0 No generated alternate\n")
    (gallery_dir / model.with_suffix(".glb").name).write_bytes(b"glTF-gallery-only")
    convert = AsyncMock(side_effect=AssertionError("existence checks must not convert"))
    monkeypatch.setattr(glb, "_convert", convert)
    response = client.get("/api/glb", params={"url": "/files/generated/only-in-gallery.mpd", "existing_only": True})
    assert response.status_code == 404
    convert.assert_not_called()


def test_sibling_must_stay_in_the_models_directory(tmp_path: Path):
    root = tmp_path / "models"
    root.mkdir()
    model = root / "safe.mpd"
    model.write_text("0 Model\n")
    outside = tmp_path / "private.glb"
    outside.write_bytes(b"not public")
    sibling = model.with_suffix(".glb")
    sibling.symlink_to(outside)
    assert glb.sibling_glb(model) is None
    sibling.unlink()
    sibling.mkdir()
    assert glb.sibling_glb(model) is None


def test_export_without_sibling_still_converts_and_caches(client, data_dir, monkeypatch):
    root = data_dir / "generated"
    root.mkdir(exist_ok=True)
    model = root / "needs-export.mpd"
    model.write_text("0 LDraw source\n")

    async def convert(source, out):
        assert source == model
        out.parent.mkdir(exist_ok=True)
        out.write_bytes(b"glTF-new-conversion")
        return out

    converter = AsyncMock(side_effect=convert)
    monkeypatch.setattr(glb, "_convert", converter)
    url = "/files/generated/needs-export.mpd"
    for _ in range(2):
        response = client.get("/api/glb", params={"url": url})
        assert response.status_code == 200
        assert response.content == b"glTF-new-conversion"
    converter.assert_awaited_once()
