from pathlib import Path

from leocad_render import DATA_DIR, OUTPUT_DIR, output_path_for
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


def test_output_path_for_mirrors_data_layout():
    model = DATA_DIR / "generated" / "abc" / "car-v2.mpd"
    assert output_path_for(model) == OUTPUT_DIR / "generated" / "abc" / "car-v2.png"
