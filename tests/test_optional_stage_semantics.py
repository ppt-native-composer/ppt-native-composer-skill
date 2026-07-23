from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_runtime_case import RuntimeCaseRunner
from runtime_test_support import create_runtime_case


def test_preview_unavailable_is_partial_not_success_or_crash(tmp_path, monkeypatch) -> None:
    _, manifest = create_runtime_case(tmp_path, preview=True)
    runner = RuntimeCaseRunner(manifest)
    monkeypatch.setattr(runner, "preview", lambda: (_ for _ in ()).throw(SystemExit("preview unavailable")))
    summary = runner.run()
    assert summary["overall_status"] == "partial"
    assert "preview_render" in summary["unavailable_stages"]
    assert not summary["failed_stages"]
