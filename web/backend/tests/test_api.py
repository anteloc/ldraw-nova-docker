import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import settings
from main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("url", [
    "/files/%2e%2e/%2e%2e/etc/passwd",
    "/files/..%2f..%2fetc%2fpasswd",
    "/ldraw/..%2f..%2f..%2fetc%2fpasswd",
    "/ref/..%2f..%2fetc%2fpasswd",
    "/ldraw-id/..%2f..%2f..%2fetc%2fpasswd",
])
def test_file_routes_refuse_traversal(client, url):
    assert client.get(url).status_code == 404


def test_ldraw_library_routes(client):
    r = client.get("/ldraw/parts/3001.dat")
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
    assert client.get("/ldraw/PARTS/S/3001S01.DAT").status_code == 200       # case-insensitive
    assert client.get("/ldraw-id/stud4.dat").text.startswith("0 ")            # found under p/
    assert client.get("/ldraw-id/s/3001s01.dat").status_code == 200
    assert client.get("/ldraw-id/nope-nope.dat").status_code == 404


def test_api_404s_are_json_not_the_spa(client):
    assert client.get("/api/nope").status_code == 404
    assert client.get("/some/client/route").status_code in (200, 404)          # SPA fallback when built


def test_llm_keys_are_masked_and_kept(client):
    created = client.post("/api/llm-models", json={
        "model_name": "t", "litellm_params": {"model": "anthropic/claude-sonnet-5", "api_key": "sk-ant-secret-1234"}}).json()
    assert created["litellm_params"]["api_key"] == "••••1234"
    updated = client.put(f"/api/llm-models/{created['id']}", json={
        "model_name": "renamed", "litellm_params": {"model": "anthropic/claude-sonnet-5", "api_key": "••••1234"}}).json()
    assert updated["model_name"] == "renamed"
    stored = json.loads((settings.CONFIG_DIR / "models.json").read_text())
    assert next(m for m in stored["models"] if m["id"] == created["id"])["litellm_params"]["api_key"] == "sk-ant-secret-1234"
    assert (settings.CONFIG_DIR / "models.json").stat().st_mode & 0o077 == 0     # 0600
    assert "sk-ant-secret" not in client.get("/api/llm-models/export").text


def test_outputs_listing_links_renders_to_sources(client, data_dir: Path):
    (data_dir / "sets").mkdir(parents=True, exist_ok=True)
    (data_dir / "sets" / "my car.mpd").write_text("0 FILE x\n")
    (data_dir / "output" / "sets").mkdir(parents=True, exist_ok=True)
    (data_dir / "output" / "sets" / "my car.png").write_bytes(b"png")
    listing = client.get("/api/outputs", params={"dir": "sets"}).json()
    [f] = listing["files"]
    assert f["source"] == {"url": "/files/sets/my%20car.mpd", "name": "my car.mpd"}
    assert client.get(f["url"]).status_code == 200
    z = client.get("/api/outputs/zip", params={"dir": "sets"})
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    assert client.get("/api/outputs", params={"dir": "../.."}).status_code == 404
