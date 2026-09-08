from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import render_preview


@pytest.mark.parametrize("kind", ["file_inside", "directory_inside", "output_is_file"])
def test_preview_refuses_existing_content_without_touching_it(tmp_path: Path, monkeypatch, kind: str) -> None:
    source = tmp_path / "source.pptx"
    source.write_bytes(b"preflight must run before rendering")
    output = tmp_path / "preview"
    if kind == "output_is_file":
        output.write_text("keep", encoding="utf-8")
        sentinel = output
    else:
        output.mkdir()
        if kind == "directory_inside":
            (output / "assets").mkdir()
            sentinel = output / "assets" / "keep.json"
        else:
            sentinel = output / "keep.json"
        sentinel.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["render_preview.py", str(source), "--outdir", str(output)])
    monkeypatch.setattr(render_preview, "run", lambda *_: pytest.fail("must not launch external tools"))
    with pytest.raises(SystemExit) as exc:
        render_preview.main()
    assert exc.value.code == 2
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert source.read_bytes() == b"preflight must run before rendering"


def test_missing_preview_tool_is_not_success(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.pptx"
    source.touch()
    output = tmp_path / "preview"
    monkeypatch.setattr(sys, "argv", ["render_preview.py", str(source), "--outdir", str(output)])
    monkeypatch.setattr(render_preview.shutil, "which", lambda *_: None)
    with pytest.raises(SystemExit, match="Missing soffice"):
        render_preview.main()
    assert not output.exists()


@pytest.mark.parametrize("option,value", [("--cols", "0"), ("--dpi", "-1")])
def test_invalid_preview_options_have_no_side_effects(tmp_path: Path, monkeypatch, option: str, value: str) -> None:
    output = tmp_path / "preview"
    monkeypatch.setattr(sys, "argv", ["render_preview.py", str(tmp_path / "missing.pptx"), "--outdir", str(output), option, value])
    with pytest.raises(SystemExit) as exc:
        render_preview.main()
    assert exc.value.code == 2
    assert not output.exists()
