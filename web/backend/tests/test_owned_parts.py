"""Owned quantities, public-source boundaries, and atomic local catalog imports."""

import gzip
import hashlib
import json
import socket

import httpx
import pytest
from fastapi.testclient import TestClient

import agent
import owned_parts as owned
import parts_api
import parts_catalog as catalog
from main import app
from store import get_store


@pytest.fixture(autouse=True)
def private_inventory(tmp_path, monkeypatch):
    root = tmp_path / "parts"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(owned, "directory", lambda: root)
    monkeypatch.setattr(
        parts_api,
        "_state",
        {"building": False, "stage": "Not downloaded", "error": None},
    )
    return root


def row(part="3001", color="4", quantity=2):
    return {"part": part, "color": color, "quantity": quantity}


@pytest.mark.parametrize("quantity", [0, -1, True, "1.5", "", "2e2", 1000001])
def test_invalid_quantities_rejected(quantity):
    with pytest.raises(ValueError):
        owned.normalize([row(quantity=quantity)], "ldraw")


def test_csv_and_bricklink_ids_are_explicitly_mapped():
    assert (
        owned.parse_upload(b"part_id,color_code,quantity\n3001,4,2\n", "bricklink")[0][
            "color"
        ]
        == 4
    )
    xml = b"<INVENTORY><ITEM><ITEMTYPE>P</ITEMTYPE><ITEMID>3001</ITEMID><COLOR>5</COLOR><MINQTY>3</MINQTY></ITEM></INVENTORY>"
    result = owned.parse_upload(xml, "ldraw")
    assert result[0]["color"] == 4  # BrickLink red 5 is LDraw red 4, not LDraw tan 5.
    assert result[0]["quantity"] == 3
    assert (
        owned.parse_upload(b"ItemID,ColorID,Qty\n3001,7,2\n", "bricklink")[0]["color"]
        == 1
    )


def test_unknown_parts_and_colors_remain_visible_but_are_not_spendable():
    stock = owned.add(
        owned.normalize([row(), row("unknown-printed", "99999", 5)], "ldraw"), "My set"
    )
    assert (stock["total"], stock["usable"], stock["unmapped"]) == (7, 2, 1)
    lot = next(r for r in stock["lots"] if r["part"] is None)
    assert lot["raw_part"] == "unknown-printed" and lot["raw_color"] == "99999"
    assert owned.snapshot()["lots"] == [{"part": "3001", "color": 4, "quantity": 2}]
    stock = owned.edit(lot["id"], "3003.dat", 14, 5)
    assert stock["usable"] == 7 and stock["unmapped"] == 0


@pytest.mark.parametrize(
    "raw",
    [
        b'<!DOCTYPE INVENTORY [<!ENTITY x SYSTEM "file:///etc/passwd">]><INVENTORY/>',
        b"<INVENTORY><ITEM><ITEMTYPE>S</ITEMTYPE></ITEM></INVENTORY>",
        b"<INVENTORY>",
        b"part,qty\n3001,1",
        b"",
    ],
)
def test_unsafe_or_incomplete_exports_are_rejected(raw):
    with pytest.raises(ValueError):
        owned.parse_upload(raw, "bricklink")


@pytest.mark.parametrize(
    "part", ["../3001", "/3001", "s/3001s01", "3001;echo", "x" * 81]
)
def test_part_numbers_cannot_be_paths(part):
    with pytest.raises(ValueError):
        owned.normalize([row(part)], "ldraw")


def test_limits_and_append_are_transactional():
    owned.add(owned.normalize([row(quantity=999999)], "ldraw"), "First")
    before = owned.snapshot()
    with pytest.raises(ValueError):
        owned.add(owned.normalize([row(quantity=2)], "ldraw"), "Too many")
    assert owned.snapshot() == before
    with pytest.raises(ValueError):
        owned.parse_upload(b"a" * (owned.MAX_UPLOAD + 1), "ldraw")
    with pytest.raises(ValueError):
        owned.add(owned.normalize([row()], "ldraw"), "bad\nlabel")


def test_snapshot_aggregates_lots_and_work_copy_cannot_change_budget():
    owned.add(owned.normalize([row(), row(quantity=3)], "ldraw"), "Owned")
    store = get_store()
    chat = store.create_chat()
    stock = owned.capture(store, chat["id"])
    canonical = store.chat_dir(chat["id"]) / "owned-parts.snapshot.json"
    (store.work_dir(chat["id"]) / "owned-parts.json").write_text('{"lots":[]}')
    assert json.loads(canonical.read_text()) == stock
    assert stock["lots"][0]["quantity"] == 5
    store.update_chat(chat["id"], options={"use_my_parts": True})
    prompt = agent.system_prompt(store, chat["id"])
    assert "owned-parts-report.json" in prompt and "up to three attempts" in prompt
    assert "not consumed" in prompt


@pytest.mark.parametrize(
    "value,number",
    [
        ("10696", "10696-1"),
        ("10497-1", "10497-1"),
        (
            "https://www.lego.com/en-us/product/lego-medium-creative-brick-box-10696",
            "10696-1",
        ),
        ("https://www.lego.com/en-us/service/buildinginstructions/10497", "10497-1"),
        ("https://www.lego.com/en-us/service/building-instructions/10497", "10497-1"),
        ("https://www.bricklink.com/v2/catalog/catalogitem.page?S=10497-1", "10497-1"),
        ("https://v2.bricklink.com/en-us/catalog/set/10497-1", "10497-1"),
        ("https://raw.githubusercontent.com/owner/repo/master/parts.csv", None),
    ],
)
def test_set_numbers_are_recognized(value, number):
    assert catalog.set_number(value) == number


@pytest.mark.parametrize(
    "url",
    [
        "http://www.lego.com/10696",
        "https://127.0.0.1/private",
        "https://localhost/",
        "https://user:password@www.lego.com/",
        "https://www.lego.com:8000/",
        "https://www.lego.com.evil.test/",
        "https://raw.githubusercontent.com/a#fragment",
    ],
)
def test_import_sources_are_bounded_and_credential_free(url):
    with pytest.raises(ValueError):
        catalog.safe_url(url)


def test_download_rejects_private_dns_before_request(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ],
    )
    with pytest.raises(ValueError, match="public catalog"):
        catalog.download("https://www.lego.com/", 10)


def test_redirect_and_response_budgets(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    )
    original = httpx.Client

    def response(request):
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    monkeypatch.setattr(
        catalog.httpx,
        "Client",
        lambda **kw: original(transport=httpx.MockTransport(response), **kw),
    )
    with pytest.raises(ValueError):
        catalog.download("https://www.lego.com/", 10)
    monkeypatch.setattr(
        catalog.httpx,
        "Client",
        lambda **kw: original(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=b"a" * 11)
            ),
            **kw,
        ),
    )
    with pytest.raises(ValueError, match="size limit"):
        catalog.download("https://www.lego.com/", 10)


@pytest.fixture
def indexed(monkeypatch):
    files = {
        "sets": "set_num,name,year,num_parts\n10696-1,Creative Brick Box,2015,5\n10497-1,Galaxy Explorer,2022,4\n",
        "parts": "part_num,name\n3001,Brick\n3003,Brick\n",
        "colors": "id,name\n5,Red\n1,Blue\n",
        "inventories": "id,version,set_num\n1,1,10696-1\n2,2,10696-1\n3,1,10497-1\n4,1,fig-demo\n",
        "inventory_parts": "inventory_id,part_num,color_id,quantity,is_spare\n1,3001,5,99,False\n2,3001,5,2,False\n2,3001,5,10,True\n3,3003,1,1,False\n4,3001,5,1,False\n",
        "inventory_sets": "inventory_id,set_num,quantity\n2,10497-1,2\n",
        "inventory_minifigs": "inventory_id,fig_num,quantity\n2,fig-demo,1\n",
    }

    def download(url, limit):
        if "color-guide" in url:
            return b"<table><tr><td></td><td>Red 5</td></tr><tr><td></td><td>Blue 7</td></tr></table>"
        return gzip.compress(files[url.rsplit("/", 1)[1].split(".")[0]].encode())

    monkeypatch.setattr(catalog, "download", download)
    catalog.build()
    return files


def test_catalog_search_latest_nested_inventory_and_spares(indexed):
    assert catalog.status()["sets"] == 2
    assert catalog.search("Galaxy Explorer")[0]["num"] == "10497-1"
    assert catalog.search("%") == [] and catalog.search("' OR 1=1 --") == []
    result = catalog.inventory("10696-1", 2)
    quantities = {(r["part"], r["color"]): r["quantity"] for r in result}
    assert quantities == {("3001", 4): 6, ("3003", 1): 4}
    assert catalog.color_map("bricklink")["5"] == 4


def test_failed_catalog_refresh_preserves_previous_and_cycles_fail(
    indexed, monkeypatch
):
    before = catalog.path().read_bytes()
    monkeypatch.setattr(
        catalog, "download", lambda *a: (_ for _ in ()).throw(ValueError("Offline"))
    )
    with pytest.raises(ValueError):
        catalog.build()
    assert catalog.path().read_bytes() == before
    import sqlite3

    with sqlite3.connect(catalog.path()) as db:
        db.execute('INSERT INTO children VALUES (3, "10696-1", 1)')
    with pytest.raises(ValueError, match="cycle"):
        catalog.inventory("10696-1")


def test_upload_import_mapping_and_cross_origin_api(indexed):
    with TestClient(app) as client:
        result = client.post(
            "/api/my-parts/upload?system=bricklink&label=Owned",
            content=b"ItemID,ColorID,Qty\n3001,5,2\n",
        )
        assert result.status_code == 200 and result.json()["usable"] == 2
        result = client.post(
            "/api/my-parts/import-url",
            json={
                "url": "https://www.lego.com/en-us/product/creative-box-10696",
                "copies": 2,
            },
        )
        assert result.status_code == 200 and result.json()["total"] == 12
        assert (
            client.get("/api/my-parts/sets?query=Galaxy").json()["sets"][0]["num"]
            == "10497-1"
        )
        assert (
            client.post(
                "/api/my-parts/lots",
                json={"part": "3001", "color": 4, "quantity": True},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/my-parts/lots",
                json={"part": "3001", "color": 4, "quantity": 1},
                headers={"Origin": "https://evil.example"},
            ).status_code
            == 403
        )
        assert client.post("/api/my-parts/upload", content=b"\xff").status_code == 422
        assert (
            client.post(
                "/api/my-parts/upload", content=b"x" * (owned.MAX_UPLOAD + 1)
            ).status_code
            == 413
        )
        assert client.get("/files/parts/owned.sqlite").status_code == 404


def test_saved_report_is_revision_bound(tmp_path):
    model = tmp_path / "model.mpd"
    model.write_text("0 Model\n")
    report = {
        "total_parts": 2,
        "matched_parts": 1,
        "missing_parts": 1,
        "color_changes": 0,
        "splits": 0,
        "missing": [{"part": "3001", "color": 4, "quantity": 1}],
        "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
    }
    sidecar = model.with_suffix(".inventory.json")
    sidecar.write_text(json.dumps(report))
    assert owned.saved_report(model)["missing_parts"] == 1
    model.write_text("0 Edited\n")
    assert owned.saved_report(model) is None
    sidecar.write_text("garbage")
    assert owned.saved_report(model) is None


def test_mode_is_strict_and_empty_inventory_cannot_start_fitting():
    import model_catalog

    entry = {"litellm_params": {"model": "openai/gpt-6-sol"}}
    assert (
        model_catalog.validate_options(entry, {"use_my_parts": True})["use_my_parts"]
        is True
    )
    for value in ("true", 1, [], None):
        with pytest.raises(ValueError, match="checkbox"):
            model_catalog.validate_options(entry, {"use_my_parts": value})
    store = get_store()
    chat = store.create_chat()
    with pytest.raises(ValueError, match="Add usable"):
        owned.capture(store, chat["id"])


def test_catalog_guide_failure_keeps_basic_mapping_and_warns(indexed, monkeypatch):
    original = catalog.download

    def missing(url, limit):
        if "color-guide" in url:
            raise httpx.ConnectError("Unavailable")
        return original(url, limit)

    monkeypatch.setattr(catalog, "download", missing)
    catalog.build()
    assert catalog.status()["warning"] and catalog.color_map("bricklink")["7"] == 1


def test_exact_set_number_sorts_before_newer_substring_matches(indexed):
    import sqlite3

    with sqlite3.connect(catalog.path()) as db:
        db.execute('INSERT INTO sets VALUES ("5010696-1", "Retro Logo", 2026, 0)')
    assert catalog.search("10696")[0]["num"] == "10696-1"


def test_login_only_export_gives_browser_upload_guidance(monkeypatch):
    monkeypatch.setattr(
        catalog, "download", lambda *_: b"<!doctype html><html>Sign in</html>"
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/my-parts/import-url",
            json={"url": "https://www.bricklink.com/catalogDownload.asp"},
        )
    assert (
        response.status_code == 422 and "requires sign-in" in response.json()["detail"]
    )
