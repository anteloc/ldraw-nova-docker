from fastapi.testclient import TestClient
import pytest

import gallery
import glb
import main
import render


@pytest.fixture
def collection(tmp_path, monkeypatch):
    root = tmp_path / "generated"
    root.mkdir()
    monkeypatch.setattr(main.settings, "GENERATED_DIR", root)
    monkeypatch.setattr(glb, "CACHE_DIR", tmp_path / "cache")
    glb.CACHE_DIR.mkdir()
    monkeypatch.setattr(gallery, "_queue", [])
    monkeypatch.setattr(gallery, "_failed", {})
    model = root / "car.mpd"
    model.write_text("0 FILE car.ldr\n0 Car\n")
    return root, model, TestClient(main.app)


def test_delete_model_and_only_its_artifacts(collection, tmp_path):
    root, model, client = collection
    for suffix in (".png", ".csv", ".md", ".glb", ".inventory.json", ".json"):
        model.with_suffix(suffix).write_text("artifact")
    other = root / "car-other.mpd"
    other.write_text("0 Other")
    original = tmp_path / "original.mpd"
    original.write_text(model.read_text())
    cache = glb._cached_path(model)
    cache.write_bytes(b"GLB")
    gallery._queue.append(model)
    result = client.delete("/api/models/car.mpd")
    assert result.status_code == 200
    assert not model.exists() and not cache.exists() and model not in gallery._queue
    assert all(not model.with_suffix(s).exists() for s in (".png", ".csv", ".md", ".glb", ".inventory.json"))
    assert other.exists() and original.exists() and model.with_suffix(".json").exists()
    assert client.delete("/api/models/car.mpd").status_code == 404


def test_delete_confines_paths_and_does_not_follow_links(collection, tmp_path):
    root, model, client = collection
    outside = tmp_path / "outside.mpd"
    outside.write_text("0 Outside")
    (root / "linked.mpd").symlink_to(outside)
    model.with_suffix(".md").symlink_to(outside)
    assert client.delete("/api/models/linked.mpd").status_code == 404
    assert client.delete("/api/models/..%2Foutside.mpd").status_code in (404, 405)
    assert client.delete("/api/models/car.md").status_code == 404
    assert client.delete("/api/gallery/car.mpd").status_code in (404, 405)
    assert client.delete("/api/models/car.mpd", headers={"Origin": "https://other.example"}).status_code == 403
    assert client.delete("/api/models/car.mpd").status_code == 200
    assert outside.read_text() == "0 Outside"


def test_shared_artifacts_are_kept_for_other_model(collection):
    root, model, client = collection
    (root / "car.ldr").write_text("0 Another model")
    model.with_suffix(".png").write_text("shared preview")
    assert client.delete("/api/models/car.mpd").status_code == 200
    assert model.with_suffix(".png").exists()


@pytest.mark.parametrize("busy", ["preview", "publication", "glb"])
def test_processing_model_cannot_be_deleted_mid_write(collection, monkeypatch, busy):
    _, model, client = collection
    if busy == "preview":
        monkeypatch.setattr(render, "is_busy", lambda p: p == model)
    elif busy == "publication":
        monkeypatch.setattr(gallery, "publishing", {model})
    else:
        monkeypatch.setattr(glb, "is_converting", lambda p: p == model)
    assert client.delete("/api/models/car.mpd").status_code == 409
    assert model.exists()
