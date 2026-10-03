from pathlib import Path

import pytest

import leocad_render


@pytest.mark.parametrize("fail", [False, True])
def test_long_snapshot_preserves_source_and_relative_submodels(tmp_path, monkeypatch, fail):
    source = tmp_path / "long.mpd"
    placements = [f"1 14 {i * 80} 0 0 1 0 0 0 1 0 0 0 1 3001.dat" for i in range(300)]
    original = ("0 FILE main.ldr\r\n0 STEP comment retained\r\n" +
                "\r\n0 STEP\r\n".join(placements) +
                "\r\n0 ROTSTEP 0 90 0 REL\r\n0 NOFILE\r\n").encode()
    source.write_bytes(original)
    prepared = []

    def image(path, output, **kwargs):
        path = Path(path)
        prepared.append(path)
        assert path.parent == source.parent
        text = path.read_text()
        assert all(placement in text for placement in placements)
        assert "0 STEP comment retained" not in text  # STEP meta has optional trailing fields
        assert not any(line.split()[:2] in (["0", "STEP"], ["0", "ROTSTEP"]) for line in text.splitlines())
        assert output == source.with_suffix(".png")
        if fail:
            raise RuntimeError("renderer unavailable")
        output.write_bytes(b"complete scene")
        return output

    monkeypatch.setattr(leocad_render, "render_image", image)
    if fail:
        with pytest.raises(RuntimeError, match="unavailable"):
            leocad_render.render_snapshot(source)
    else:
        assert leocad_render.render_snapshot(source) == source.with_suffix(".png")
    assert source.read_bytes() == original
    assert prepared and not prepared[0].exists()
