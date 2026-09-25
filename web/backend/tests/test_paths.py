from pathlib import Path

from leocad_render import bom_part_count, bom_path_for, list_models, snapshot_path_for
from paths import safe_join


def test_safe_join_stays_inside(tmp_path: Path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b.txt").write_text("x")
    assert safe_join(tmp_path, "a/b.txt") == (tmp_path / "a" / "b.txt").resolve()
    assert safe_join(tmp_path, "/a/b.txt") == (tmp_path / "a" / "b.txt").resolve()   # leading slash is relative
    for bad in ("../x", "a/../../x", "../../etc/passwd", "a\\..\\..\\x"):
        assert safe_join(tmp_path, bad) is None, bad


def test_safe_join_rejects_symlink_escape(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "link").symlink_to(outside)
    assert safe_join(root, "link/anything") is None


def test_safe_join_case_insensitive(tmp_path: Path):
    (tmp_path / "Parts" / "S").mkdir(parents=True)
    (tmp_path / "Parts" / "S" / "3001S01.DAT").write_text("x")
    found = safe_join(tmp_path, "parts/s/3001s01.dat", case_insensitive=True)
    assert found is not None and found.is_file()
    assert safe_join(tmp_path, "parts/s/3001s01.dat").exists() is False


def test_snapshot_and_bom_are_same_named_siblings():
    assert snapshot_path_for(Path("/data/generated/red-car-v2.mpd")) == Path("/data/generated/red-car-v2.png")
    assert bom_path_for(Path("/data/generated/red-car-v2.mpd")) == Path("/data/generated/red-car-v2.csv")


def test_bom_part_count(tmp_path: Path):
    bom = tmp_path / "x.csv"
    bom.write_text('Part Name,Color,Quantity,Part ID,Color Code\n"Brick  2 x  4","Red",3,3001.dat,4\n'
                   '"Plate  1 x  1","White",12,3024.dat,15\n')
    assert bom_part_count(bom) == 15
    bom.write_text("not a bom\n")
    assert bom_part_count(bom) is None
    assert bom_part_count(tmp_path / "missing.csv") is None


def test_list_models_is_flat_and_takes_all_ldraw_suffixes(tmp_path: Path):
    for name in ("a.mpd", "b.LDR", "c.dat", "d.png", "notes.txt"):
        (tmp_path / name).write_text("0 x\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "e.mpd").write_text("0 x\n")
    assert [p.name for p in list_models(tmp_path)] == ["a.mpd", "b.LDR", "c.dat"]


def test_part_less_models_get_an_empty_bom_without_leocad(tmp_path: Path):
    # LeoCAD's CSV export never returns for these, so export_bom() must not call it.
    from leocad_render import _has_parts, export_bom
    cases = {
        "empty.mpd": ("0 FILE x.ldr\n0 empty\n", False),
        "garbage.dat": ("\x00\x01 not ldraw", False),
        "only-empty-sub.mpd": ("0 FILE s.ldr\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 sub.ldr\n0 FILE sub.ldr\n0 empty\n", False),
        "loop.mpd": ("0 FILE a.ldr\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 b.ldr\n0 FILE b.ldr\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 a.ldr\n", False),
        "nested.mpd": ("0 FILE s.ldr\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 Sub Model.ldr\n"
                       "0 FILE sub model.ldr\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 S\\3001s01.dat\n", True),
        "unknown-part.mpd": ("0 FILE u.ldr\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 notarealpart.dat\n", True),
        "single.ldr": ("0 single\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n", True),
    }
    for name, (text, has_parts) in cases.items():
        model = tmp_path / name
        model.write_text(text)
        assert _has_parts(model) is has_parts, name
        if not has_parts:
            assert bom_part_count(export_bom(model)) == 0, name
