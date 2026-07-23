from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from runtime_stage_cache import toolchain_fingerprint  # noqa: E402


def valid_manifest(tmp_path: Path) -> dict:
    source = tmp_path / "input.json"
    source.write_text("{}", encoding="utf-8")
    return {
        "manifest_version": "1.0", "case_id": "case", "case_kind": "synthetic_test", "source": {"source_pptx": None, "template_pptx": None},
        "inputs": {"blueprint": str(source), "design_intent": str(source), "route": str(source), "evc": str(source), "asset_registry": None, "asset_plan": None, "assets_dir": str(tmp_path)},
        "output": {"root": str(tmp_path / "out"), "allow_overwrite": False},
        "stages": {"assemble": True, "package_inspection": True, "no_shadow_scan": True, "preview": True, "layout_intelligence_advisory": False},
        "runtime_options": {"resume": True, "fail_on_unsupported_required_field": True, "preview_dpi": 120},
    }


def test_runtime_case_manifest_accepts_valid_shape_and_rejects_missing_required_field(tmp_path: Path) -> None:
    schema = json.loads((SCRIPTS.parent / "schemas" / "runtime_case_manifest.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    payload = valid_manifest(tmp_path)
    assert list(validator.iter_errors(payload)) == []
    invalid = copy.deepcopy(payload)
    invalid["inputs"].pop("evc")
    assert list(validator.iter_errors(invalid))


def test_toolchain_fingerprint_changes_when_tracked_content_changes(tmp_path: Path) -> None:
    first = toolchain_fingerprint(SCRIPTS.parent, [tmp_path / "extra.py"])["fingerprint"]
    (tmp_path / "extra.py").write_text("first", encoding="utf-8")
    second = toolchain_fingerprint(SCRIPTS.parent, [tmp_path / "extra.py"])["fingerprint"]
    (tmp_path / "extra.py").write_text("second", encoding="utf-8")
    third = toolchain_fingerprint(SCRIPTS.parent, [tmp_path / "extra.py"])["fingerprint"]
    assert first != second != third
