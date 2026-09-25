import ldraw


def test_find_parts_prefers_the_plain_part():
    assert ldraw.find_parts("brick 2x4")[0]["id"] == "3001.dat"
    assert ldraw.find_parts("Plate 1 x 2")[0]["id"].startswith("3023")
    assert ldraw.find_parts("3001")[0]["id"] == "3001.dat"
    assert ldraw.find_parts("zzzz-no-such-thing") == []


def test_search_reference_models():
    hits = ldraw.search_reference_models("fire truck")
    assert hits and all("file" in h and "submodels" in h for h in hits)


def test_read_reference_model_submodel():
    text = ldraw.read_reference_model("8303-1.mpd", "8303 - Demon Destroyer.ldr", max_lines=5)
    assert text.startswith("0 FILE 8303 - Demon Destroyer.ldr")
    assert "truncated" in text


def test_validate_good_model_adds_file_header():
    v = ldraw.validate_model("1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n", main_name="car.ldr")
    assert v.content.startswith("0 FILE car.ldr\n")
    assert v.part_count == 1
    assert v.warnings == []


def test_validate_reports_unknown_parts_and_colours():
    content = "\n".join([
        "0 FILE main.ldr",
        "1 999 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat",
        "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 notapart.dat",
        "1 4 0 -48 0 1 0 0 0 1 0 0 0 1 sub model.ldr",       # defined below: fine
        "1 4 0 0 0 1 0 0 0 1 0 0 0 1 S\\3001S01.DAT",           # backslash + case: fine
        "0 FILE sub model.ldr",
        "1 0x2FF0000 0 0 0 1 0 0 0 1 0 0 0 1 3003.dat",         # direct colour: fine
    ])
    v = ldraw.validate_model(content, main_name="main.ldr")
    joined = "\n".join(v.warnings)
    assert "999" in joined
    assert "notapart.dat" in joined
    assert "sub model.ldr" not in joined and "3001s01" not in joined
    assert v.submodels == ["main.ldr", "sub model.ldr"]


def test_validate_malformed_lines():
    v = ldraw.validate_model("1 4 0 0 0 1 0 0\n1 4 a b c 1 0 0 0 1 0 0 0 1 3001.dat\n", main_name="m.ldr")
    joined = "\n".join(v.warnings)
    assert "needs 15 fields" in joined and "non-numeric" in joined
