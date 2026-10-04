"""Quantity/geometry preservation and real Nova publication, not mocked rendering."""

import asyncio
import json
import os
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import inventory_fit as fitter
import owned_parts
import settings
import tools
from main import app
from store import get_store

PROFILES = {
    "3001": {
        "description": "Brick 2 x 4",
        "x_studs": 4,
        "z_studs": 2,
        "height": 24,
        "studs": True,
    },
    "3003": {
        "description": "Brick 2 x 2",
        "x_studs": 2,
        "z_studs": 2,
        "height": 24,
        "studs": True,
    },
    "3004": {
        "description": "Brick 1 x 2",
        "x_studs": 2,
        "z_studs": 1,
        "height": 24,
        "studs": True,
    },
    "3022": {
        "description": "Plate 2 x 2",
        "x_studs": 2,
        "z_studs": 2,
        "height": 8,
        "studs": True,
    },
    "tile": {
        "description": "Tile 2 x 2",
        "x_studs": 2,
        "z_studs": 2,
        "height": 24,
        "studs": False,
    },
}
RGB = {4: [255, 0, 0], 1: [0, 0, 255], 14: [255, 255, 0], 15: [255, 255, 255]}


def p(part="3001", color=4):
    return {"part": part, "color": color}


def lot(part, color, quantity):
    return {**p(part, color), "quantity": quantity}


def test_exact_matches_reserved_before_color_changes():
    fitted, report = fitter.fit(
        [p(color=14), p(color=4)], [lot("3001", 4, 1), lot("3001", 1, 1)], PROFILES, RGB
    )
    assert [r["color"] for r in fitted] == [1, 4]
    assert report["matched_parts"] == 2 and report["color_changes"] == 1


def test_no_quantity_reuse_and_missing_placements_remain():
    fitted, report = fitter.fit([p(), p(), p()], [lot("3001", 4, 1)], PROFILES, RGB)
    assert (
        len(fitted) == 3
        and report["matched_parts"] == 1
        and report["missing_parts"] == 2
    )
    assert report["missing"] == [{"part": "3001", "color": 4, "quantity": 2}]


def test_split_preserves_exact_footprint_and_available_color():
    fitted, report = fitter.fit([p()], [lot("3003", 1, 2)], PROFILES, RGB)
    assert len(fitted) == 2 and report["splits"] == 1 and report["missing_parts"] == 0
    assert [r["offset"] for r in fitted] == [[-20, 0, 0], [20, 0, 0]]
    assert Counter((r["part"], r["color"]) for r in fitted) == Counter({("3003", 1): 2})


def test_failed_cover_rolls_back_stock_for_next_piece():
    fitted, report = fitter.fit(
        [p(), p("3004")], [lot("3003", 1, 1), lot("3004", 1, 1)], PROFILES, RGB
    )
    assert report["missing_parts"] == 1 and report["color_changes"] == 1
    assert fitted[0] == p() and fitted[1] == p("3004", 1)


@pytest.mark.parametrize("part", ["3022", "tile", "unknown"])
def test_incompatible_heights_tiles_and_unknown_shapes_cannot_replace_bricks(part):
    _, report = fitter.fit([p()], [lot(part, 4, 10)], PROFILES, RGB)
    assert report["splits"] == 0 and report["missing_parts"] == 1


def test_rotated_placements_cover_cells_without_overlaps():
    source = {
        **p("3001"),
        "matrix": [[0, 0, 1], [0, 1, 0], [-1, 0, 0]],
        "position": [10, 0, 20],
    }
    fitted, report = fitter.fit([source], [lot("3004", 4, 4)], PROFILES, RGB)
    cells = []
    for placement in fitted:
        width, depth = (1, 2) if placement["rotated"] else (2, 1)
        x = int((placement["offset"][0] + 40 - width * 10) / 20)
        z = int((placement["offset"][2] + 20 - depth * 10) / 20)
        cells.extend((x + dx, z + dz) for dx in range(width) for dz in range(depth))
        assert (
            placement["matrix"] == source["matrix"]
            and placement["position"] == source["position"]
        )
    assert len(cells) == len(set(cells)) == 8
    assert report["missing_parts"] == 0


def test_search_and_input_budgets(monkeypatch):
    monkeypatch.setattr(fitter, "MAX_TOTAL_SEARCH", 1)
    _, report = fitter.fit([p(), p()], [lot("3003", 1, 4)], PROFILES, RGB)
    assert report["missing_parts"] == 2
    with pytest.raises(ValueError):
        fitter.fit([p()] * (fitter.MAX_PARTS + 1), [], PROFILES, RGB)
    with pytest.raises(ValueError):
        fitter.fit([p()], [lot("../3001", 4, 1)], PROFILES, RGB)


@pytest.fixture
def stock(tmp_path, monkeypatch):
    os.chmod(settings.DATA_DIR.parent, 0o755)
    root = tmp_path / "parts"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(owned_parts, "directory", lambda: root)
    owned_parts.add(
        owned_parts.normalize(
            [lot("3003", 1, 2), lot("3003", 14, 1), lot("3004", 1, 1)], "ldraw"
        ),
        "Test inventory",
    )
    return owned_parts.snapshot()


SOURCE = """0 FILE test.ldr
0 Inventory tower
0 Name: test.ldr
0 Author: Test author
0 !LDRAW_ORG Model
0 !LICENSE Licensed under CC BY-SA 4.0 : see CAreadme.txt
1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
0 STEP
1 14 0 -24 0 1 0 0 0 1 0 0 0 1 3003.dat
1 4 0 -48 0 1 0 0 0 1 0 0 0 1 3004.dat
"""


def test_fit_api_rejects_stale_sources_and_paths(stock):
    settings.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    model = settings.GENERATED_DIR / "inventory-stale-test.mpd"
    model.write_text(SOURCE)
    with TestClient(app) as client:
        before = client.get(
            "/api/my-parts/revision", params={"file": model.name}
        ).json()["revision"]
        model.write_text(SOURCE + "0 Changed\n")
        assert (
            client.post(
                "/api/my-parts/fit", json={"file": model.name, "revision": before}
            ).status_code
            == 409
        )
        assert (
            client.get(
                "/api/my-parts/revision", params={"file": "../private.mpd"}
            ).status_code
            == 404
        )
        assert (
            client.get("/api/my-parts/revision", params={"file": "a" * 200}).status_code
            == 422
        )
    model.unlink()


def test_real_fit_uses_canonical_budget_preserves_source_and_renders(stock):
    store = get_store()
    chat = store.create_chat()
    store.update_chat(chat["id"], options={"use_my_parts": True})
    ctx = tools.ToolContext(chat["id"], store, lambda *_: None)
    owned_parts.capture(store, chat["id"])
    # Agent-readable hints are deliberately editable; they never authorize extra stock.
    (ctx.work_dir / "owned-parts.json").write_text(
        json.dumps({"lots": [lot("3001", 4, 999)]})
    )
    model = ctx.work_dir / "tower.mpd"
    model.write_text(SOURCE)
    original = model.read_bytes()
    published = asyncio.run(
        tools.t_publish_model(ctx, "output/tower.mpd", "Owned inventory test")
    )
    assert published.models, published.content
    result = json.loads(published.content)
    report = result["inventory"]
    assert (
        report["total_parts"],
        report["matched_parts"],
        report["missing_parts"],
        report["splits"],
        report["color_changes"],
    ) == (4, 4, 0, 1, 1)
    assert report["inventory_revision"] == stock["revision"]
    assert result["checks_passed"]
    fitted = store.resolve(chat["id"], published.models[0]["model"])
    assert model.read_bytes() == original and fitted.read_bytes() != original
    text = fitted.read_text()
    assert "Test author" in text and "CC BY-SA 4.0" in text and "0 STEP" in text
    assert fitted.with_suffix(".png").stat().st_size > 1000
    assert fitted.with_suffix(".csv").stat().st_size > 50
    assert owned_parts.saved_report(fitted)["matched_parts"] == 4
    assert owned_parts.snapshot() == stock  # Planning never consumes inventory.
    compared = asyncio.run(
        tools.t_run_toolkit(
            ctx,
            [
                "compare-bom",
                str(fitted),
                "--csv",
                str(fitted.with_suffix(".csv")),
                "--report",
                "output/compared.json",
            ],
        )
    )
    assert "exit code 0" in compared.content, compared.content
    with TestClient(app) as client:
        assert client.get(result["download_url"]).status_code == 200
        saved = client.get("/api/chats/" + chat["id"]).json()["models"][
            published.models[0]["id"]
        ]
        assert saved["inventory_report"]["matched_parts"] == 4 and saved["parts"] == 4


def test_failed_fitted_geometry_does_not_publish(stock, monkeypatch):
    store = get_store()
    chat = store.create_chat()
    store.update_chat(chat["id"], options={"use_my_parts": True})
    ctx = tools.ToolContext(chat["id"], store, lambda *_: None)
    owned_parts.capture(store, chat["id"])
    model = ctx.work_dir / "invalid.mpd"
    model.write_text(SOURCE)
    original = tools.run_command

    async def command(ctx, argv, timeout):
        if "validate" in argv:
            from sandbox import RunResult

            Path(argv[argv.index("--report") + 1]).write_text("{}")
            return RunResult(1, "", "geometry failed", False, 0)
        result = await original(ctx, argv, timeout)
        assert result.exit_code == 0, result.as_text()
        return result

    monkeypatch.setattr(tools, "run_command", command)
    result = asyncio.run(
        tools.t_publish_model(ctx, "output/invalid.mpd", "Should not publish")
    )
    assert not result.models and "geometry validation" in result.content
    assert store.models(chat["id"]) == []


def test_real_worker_expands_repeated_submodels_in_world_space(stock):
    store = get_store()
    chat = store.create_chat()
    ctx = tools.ToolContext(chat["id"], store, lambda *_: None)
    owned_parts.capture(store, chat["id"])
    model = ctx.work_dir / "nested.mpd"
    model.write_text("""0 FILE root.ldr
0 Repeated inherited colors
0 Name: root.ldr
0 Author: Test
0 !LDRAW_ORG Model
0 !LICENSE Licensed under CC BY-SA 4.0 : see CAreadme.txt
1 1 10 0 20 0 0 1 0 1 0 -1 0 0 child.ldr
0 STEP
1 14 0 -24 0 1 0 0 0 1 0 0 0 1 child.ldr
0 FILE child.ldr
0 Child
0 Name: child.ldr
0 Author: Test
0 !LDRAW_ORG Model
0 !LICENSE Licensed under CC BY-SA 4.0 : see CAreadme.txt
1 16 0 0 0 1 0 0 0 1 0 0 0 1 3003.dat
""")
    worker = Path(fitter.__file__)
    output = ctx.work_dir / "fitted.mpd"
    report = ctx.work_dir / "report.json"
    launcher = (
        "import runpy; runpy.run_path(" + repr(str(worker)) + ', run_name="__main__")'
    )
    result = asyncio.run(
        tools.run_command(
            ctx,
            [
                "python3",
                "-c",
                launcher,
                str(model),
                str(ctx.chat_dir / "owned-parts.snapshot.json"),
                str(output),
                str(report),
                str(settings.LDRAW_DIR),
            ],
            120,
        )
    )
    assert result.exit_code == 0, result.as_text()
    assert json.loads(report.read_text())["matched_parts"] == 2
    lines = output.read_text().splitlines()
    assert "1 1 10 0 20 0 0 1 0 1 0 -1 0 0 3003.dat" in lines
    assert "1 14 0 -24 0 1 0 0 0 1 0 0 0 1 3003.dat" in lines
    assert lines.count("0 STEP") == 1
