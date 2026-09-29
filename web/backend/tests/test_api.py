import io
import json
import time
import zipfile
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
    "/demo/..%2f..%2fetc%2fpasswd",
    "/gallery-files/..%2f..%2fetc%2fpasswd",
    "/ldraw-id/..%2f..%2f..%2fetc%2fpasswd",
])
def test_file_routes_refuse_traversal(client, url):
    assert client.get(url).status_code == 404


def test_ldraw_library_routes(client):
    r = client.get("/ldraw/parts/3001.dat")
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
    assert client.get("/ldraw/PARTS/S/3001S01.DAT").status_code == 200       # case-insensitive
    stud = client.get("/ldraw-id/stud4.dat")
    assert stud.text.startswith("0 ") and stud.headers["x-ldraw-folder"] == "p"   # found under p/
    subpart = client.get("/ldraw-id/s/3001s01.dat")
    assert subpart.status_code == 200 and subpart.headers["x-ldraw-folder"] == "parts"
    assert client.get("/ldraw-id/nope-nope.dat").status_code == 404


def test_viewer_and_player_offer_the_camera_modes(client):
    viewer = client.get("/viewer/viewer.html").text
    assert 'data-mode="high" aria-pressed="true"' in viewer                  # High by default
    assert 'data-mode="poly"' in viewer
    for page in (viewer, client.get("/viewer/player.html").text):
        assert 'data-camera="inspect"' in page and 'data-camera="walk"' in page


@pytest.mark.skipif(not settings.XR_DIR.is_dir(), reason="the mixed-reality viewer is built into the image")
def test_mixed_reality_viewer_is_served(client):
    page = client.get("/xr/?model=/gallery-files/copper-bean.mpd")
    assert page.status_code == 200 and 'id="enter"' in page.text
    script = next(p for p in page.text.split('"') if p.startswith("/xr/assets/") and p.endswith(".js"))
    assert client.get(script).status_code == 200
    assert "Real size" in client.get("/xr/ui/menu.uikitml").text
    assert client.get("/xr/nope.js").status_code == 404                    # not the SPA's index.html


@pytest.mark.skipif(not settings.PLAYER_VENDOR_DIR.is_dir(), reason="ldraw-player is unpacked at image build")
def test_player_page_and_webassembly_are_served(client):
    page = client.get("/viewer/player.html")
    assert page.status_code == 200 and "player-vendor/ldraw_player.js" in page.text
    assert "Player" in client.get("/viewer/player-vendor/ldraw_player.js").text
    wasm = client.get("/viewer/player-vendor/ldraw_player_bg.wasm")
    # the MIME type WebAssembly.instantiateStreaming insists on
    assert wasm.status_code == 200 and wasm.headers["content-type"] == "application/wasm"
    assert wasm.content[:4] == b"\0asm"
    # same URLs in every version: browsers must revalidate, or they run a stale player
    assert page.headers["cache-control"] == wasm.headers["cache-control"] == "no-cache"
    again = client.get("/viewer/player-vendor/ldraw_player_bg.wasm", headers={"If-None-Match": wasm.headers["etag"]})
    assert again.status_code == 304


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


def test_output_folder_is_never_served(client, data_dir: Path):
    (data_dir / "output" / "some-chat").mkdir(parents=True, exist_ok=True)
    (data_dir / "output" / "some-chat" / "NOTES.md").write_text("private")
    (data_dir / "generated").mkdir(parents=True, exist_ok=True)
    for url in ("/files/output/some-chat/NOTES.md", "/files/generated/..%2Foutput%2Fsome-chat%2FNOTES.md",
                "/files/chats/..%2Foutput%2Fsome-chat%2FNOTES.md", "/api/outputs"):
        assert client.get(url).status_code == 404, url


def test_models_page_lists_generated_and_renders_missing_snapshots(client, data_dir: Path):
    generated = data_dir / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    (generated / "hand-made.mpd").write_text(
        "0 FILE hand-made.ldr\n0 A hand-made test wall\n0 Name: hand-made.ldr\n"
        "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n1 1 20 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n")
    (generated / "single.ldr").write_text("0 Single-file model\n1 14 0 0 0 1 0 0 0 1 0 0 0 1 3003.dat\n")
    (generated / "broken.dat").write_bytes(b"\x00\x01 not ldraw")
    (generated / "nested").mkdir(exist_ok=True)
    (generated / "nested" / "ignored.mpd").write_text("0 FILE x\n")

    deadline = time.time() + 180
    while True:
        listing = client.get("/api/models").json()
        by_file = {m["file"]: m for m in listing["models"]}
        if listing["pending"] == 0 or time.time() > deadline:
            break
        time.sleep(0.5)

    assert "ignored.mpd" not in by_file                                         # flat: subfolders don't count
    wall = by_file["hand-made.mpd"]
    assert wall["description"] == "A hand-made test wall"                      # line 2 of the .mpd
    assert wall["status"] == "ready" and wall["image_url"].startswith("/files/generated/hand-made.png?v=")
    assert (generated / "hand-made.png").stat().st_size > 1000                  # rendered, home view
    assert wall["bom_status"] == "ready" and wall["parts"] == 2                 # from LeoCAD's CSV BOM
    assert wall["bom_url"].startswith("/files/generated/hand-made.csv?v=")
    bom = client.get(wall["bom_url"].split("?")[0], params={"download": 1})
    assert bom.status_code == 200 and bom.headers["content-type"].startswith("text/csv")
    assert "attachment" in bom.headers["content-disposition"] and "3001.dat" in bom.text
    assert by_file["single.ldr"]["parts"] == 1
    assert by_file["single.ldr"]["description"] == "Single-file model"
    assert by_file["single.ldr"]["status"] == "ready"
    assert by_file["broken.dat"]["status"] in ("failed", "ready")               # LeoCAD may render it empty
    assert by_file["broken.dat"]["bom_status"] == "ready" and by_file["broken.dat"]["parts"] == 0
    assert client.get(wall["model_url"]).status_code == 200
    z = client.get("/api/models/zip")
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"


def test_gallery_and_generated_models_are_independent(client, data_dir: Path, gallery_dir: Path):
    from main import model_from_url
    generated = data_dir / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    for folder, filenames in ((gallery_dir, ("gallery-only.mpd", "clash.mpd", "shared.mpd")),
                              (generated, ("clash.ldr", "shared.mpd"))):
        for filename in filenames:
            model = folder / filename
            model.write_text(f"0 FILE {model.stem}.ldr\n0 {folder.name} {model.stem}\n"
                             "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n")
            model.with_suffix(".png").write_bytes(b"\x89PNG\r\n\x1a\n")
            model.with_suffix(".csv").write_text("Part Name,Color,Quantity,Part ID,Color Code\nBrick 2 x 4,Red,1,3001,4\n")
            if folder == gallery_dir:
                model.with_suffix(".md").write_text(f"# Notes\n\n## {model.stem}\n\n**Prompt:** build it\n\n## Later heading")

    gallery_listing = client.get("/api/gallery").json()
    assert gallery_listing["pending"] == 0
    gallery_models = {m["file"]: m for m in gallery_listing["models"]}
    mine = {m["file"]: m for m in client.get("/api/models").json()["models"]}
    assert set(gallery_models) == {"gallery-only.mpd", "clash.mpd", "shared.mpd"}
    assert "gallery-only.mpd" not in mine and "clash.mpd" not in mine
    assert mine["clash.ldr"]["gallery"] is False and mine["clash.ldr"]["info_url"] is None
    assert mine["clash.ldr"]["info_heading"] is None  # never inherit gallery siblings
    assert mine["shared.mpd"]["model_url"] == "/files/generated/shared.mpd"
    assert gallery_models["shared.mpd"]["model_url"] == "/gallery-files/shared.mpd"
    assert gallery_models["shared.mpd"]["description"] != mine["shared.mpd"]["description"]

    bundled = gallery_models["gallery-only.mpd"]
    assert bundled["gallery"] is True and bundled["model_url"] == "/gallery-files/gallery-only.mpd"
    assert bundled["status"] == "ready" and bundled["image_url"].startswith("/gallery-files/gallery-only.png?v=")
    assert bundled["bom_status"] == "ready" and bundled["parts"] == 1
    assert bundled["info_url"].startswith("/gallery-files/gallery-only.md?v=")
    assert bundled["info_heading"] == "gallery-only"
    info = client.get(bundled["info_url"])
    assert info.status_code == 200 and info.headers["content-type"].startswith("text/markdown")
    assert "**Prompt:** build it" in info.text and "## Later heading" in info.text
    for url in (bundled["model_url"], "/demo/gallery-only.mpd"):
        assert client.get(url).status_code == 200
        assert model_from_url(url) == gallery_dir / "gallery-only.mpd"
    download = client.get(bundled["model_url"], params={"download": 1})
    assert "attachment" in download.headers["content-disposition"]
    assert client.get(bundled["bom_url"]).status_code == 200
    assert client.get("/gallery-files/missing.mpd").status_code == 404

    (generated / "clash.md").write_text("Notes on my model\n\n## My own heading\n\n## Another")
    updated = next(m for m in client.get("/api/models").json()["models"] if m["file"] == "clash.ldr")
    assert updated["info_url"].startswith("/files/generated/clash.md?v=")
    assert updated["info_heading"] == "My own heading"

    for endpoint, source, absent, filename in (("models", generated, "gallery-only.mpd", "generated.zip"),
                                              ("gallery", gallery_dir, "clash.ldr", "gallery.zip")):
        z = client.get(f"/api/{endpoint}/zip")
        assert z.status_code == 200 and filename in z.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
            assert absent not in zf.namelist()
            assert {"shared.mpd", "shared.png", "shared.csv", "clash.md"} <= set(zf.namelist())
            assert zf.read("shared.mpd") == (source / "shared.mpd").read_bytes()
            assert zf.read("clash.md") == (source / "clash.md").read_bytes()


def test_gallery_never_generates_missing_artifacts(client, gallery_dir: Path, monkeypatch):
    import gallery
    def unexpected_render(_models):
        pytest.fail("Gallery must not queue renders")
    monkeypatch.setattr(gallery, "ensure_artifacts", unexpected_render)
    model = gallery_dir / "without-artifacts.mpd"
    model.write_text("0 FILE without-artifacts.ldr\n0 No artifacts\n")
    try:
        listing = client.get("/api/gallery").json()
        item = next(m for m in listing["models"] if m["file"] == model.name)
        assert listing["pending"] == 0
        assert item["image_url"] is None and item["bom_url"] is None
        assert item["info_heading"] is None and item["info_url"] is None
        assert item["status"] == item["bom_status"] == "failed"
    finally:
        model.unlink()


def test_absent_gallery_is_empty(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "GALLERY_MODELS_DIR", tmp_path / "absent")
    assert client.get("/api/gallery").json() == {"models": [], "pending": 0}
    with zipfile.ZipFile(io.BytesIO(client.get("/api/gallery/zip").content)) as zf:
        assert zf.namelist() == []


def test_chat_api_resolves_model_references(client, data_dir: Path):
    import settings as s
    from store import ChatStore
    store = ChatStore(s.CHATS_DIR, s.OUTPUT_DIR)
    chat = store.create_chat()
    model = s.GENERATED_DIR / "referenced.mpd"
    model.write_text("0 FILE referenced.ldr\n0 Referenced from a chat\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n")
    model.with_suffix(".md").write_text("## A model built in chat\n\nThe full notes.")
    ref = store.add_model(chat["id"], "Referenced", model, warnings=["w"])
    store.add_message(chat["id"], {"role": "tool", "tool_call_id": "x", "content": "ok",
                                   "_models": [ref["id"]], "_images": ["../../generated/referenced.png"]})
    detail = client.get(f"/api/chats/{chat['id']}").json()
    m = detail["models"][ref["id"]]
    assert m["model_url"] == "/files/generated/referenced.mpd" and m["description"] == "Referenced from a chat"
    assert m["warnings"] == ["w"]
    assert m["info_heading"] == "A model built in chat" and m["gallery"] is False
    listing = client.get("/api/models").json()
    assert {"id": chat["id"], "title": "New chat"} in next(x for x in listing["models"] if x["file"] == "referenced.mpd")["chats"]
    assert client.delete(f"/api/chats/{chat['id']}").status_code == 200
    assert model.exists()                                                       # models outlive their chat
    assert client.get("/api/chats/..%2F..%2Fetc").status_code == 404


def test_glb_export_with_mpd2glb(client, data_dir: Path):
    import glb
    generated = data_dir / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    model = generated / "glb-test.mpd"
    model.write_text("0 FILE glb-test.ldr\n0 A tiny model for the glb test\n"
                     "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n1 15 0 -24 0 1 0 0 0 1 0 0 0 1 3003.dat\n")
    url = "/files/generated/glb-test.mpd"

    r = client.get("/api/glb", params={"url": url})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "model/gltf-binary"
    assert 'filename="glb-test.glb"' in r.headers["content-disposition"]
    assert r.content[:4] == b"glTF"
    header = json.loads(r.content[20:20 + int.from_bytes(r.content[12:16], "little")])
    assert not header.get("extensionsUsed")                                    # uncompressed: no draco/meshopt
    assert any(n.get("extras", {}).get("description") == "Brick  2 x  4" for n in header["nodes"])
    cached = list(glb.CACHE_DIR.glob("*.glb"))
    assert len(cached) == 1

    t0 = time.time()
    assert client.get("/api/glb", params={"url": url}).content == r.content     # served from the cache
    assert time.time() - t0 < 2

    model.write_text(model.read_text() + "1 1 0 -48 0 1 0 0 0 1 0 0 0 1 3001.dat\n")   # new version
    r2 = client.get("/api/glb", params={"url": url})
    assert r2.status_code == 200 and r2.content != r.content
    assert len(list(glb.CACHE_DIR.glob("*.glb"))) == 1                          # the old version was dropped

    for bad in ("/files/generated/..%2F..%2Fetc%2Fpasswd", "/files/generated/nope.mpd", "/files/chats/a/b.mpd",
                "/files/output/x/y.mpd", "/files/generated/glb-test.png", "https://example.com/x.mpd"):
        assert client.get("/api/glb", params={"url": bad}).status_code == 404, bad
