import pytest

from gallery import info_heading_of


@pytest.mark.parametrize(("notes", "expected"), [
    ("## Copper Bean, by Opus\n\n## Second heading", "Copper Bean, by Opus"),
    ("# Title\n\nIntro\n### Detail\n\n## The subtitle\n", "The subtitle"),
    ("## Heading with closing hashes ###\n", "Heading with closing hashes"),
    ("\ufeff  ## A Unicode café 🚀\n", "A Unicode café 🚀"),
    ("##No space\n    ## Indented code\n> ## Quoted\n## Actual H2", "Actual H2"),
    ("```md\n## Code\n```\n~~~\n## More code\n~~~\n## Real heading", "Real heading"),
    ("````md\n## Code\n```\n## Still code\n````\n## Real heading", "Real heading"),
    ("Notes without an H2\n### Only an H3", None),
    ("##\n## Second heading", None),
    (None, None),
])
def test_first_h2_from_model_notes(tmp_path, notes, expected):
    model = tmp_path / "model.mpd"
    if notes is not None:
        model.with_suffix(".md").write_text(notes, encoding="utf-8")
    assert info_heading_of(model) == expected
