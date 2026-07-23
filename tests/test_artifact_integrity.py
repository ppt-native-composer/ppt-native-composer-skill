from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from artifact_integrity import validate_artifact


def test_corrupted_pptx_is_not_valid(tmp_path: Path) -> None:
    broken = tmp_path / "broken.pptx"
    broken.write_bytes(b"not a zip")
    outcome = validate_artifact(broken, "pptx")
    assert outcome["valid"] is False
    assert outcome["errors"]


def test_json_requires_contract_keys(tmp_path: Path) -> None:
    payload = tmp_path / "evidence.json"
    payload.write_text('{"ok": true}', encoding="utf-8")
    assert not validate_artifact(payload, "json", ["run_id"])["valid"]
