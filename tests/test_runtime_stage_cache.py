from __future__ import annotations

from pathlib import Path

import pytest

import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from runtime_stage_cache import StageCache  # noqa: E402
from artifact_integrity import validate_artifact  # noqa: E402


def stage(stage_id: str, fingerprint: str, output: Path) -> dict:
    output.write_text("ok", encoding="utf-8")
    validation = validate_artifact(output, "text")
    return {
        "stage_id": stage_id,
        "status": "executed",
        "input_fingerprint": fingerprint,
        "dependency_fingerprints": {},
        "outputs": [str(output)],
        "artifacts": [{"path": str(output), "artifact_type": "text", "required_keys": [], "sha256": validation["sha256"], "metadata": validation["metadata"]}],
        "warnings": [],
        "errors": [],
    }


@pytest.mark.parametrize("mutation", ["evc", "route", "design_intent", "source", "template", "asset_registry", "asset_file", "runtime_script", "schema", "runtime_option"])
def test_stage_cache_invalidates_on_each_content_addressed_change(tmp_path: Path, mutation: str) -> None:
    cache = StageCache(tmp_path / "run_state.json", {"run_id": "one"})
    output = tmp_path / "output.json"
    cache.record(stage("assemble_pptx", "baseline", output))
    assert cache.cached("assemble_pptx", "baseline")[0]
    assert not cache.cached("assemble_pptx", f"baseline-{mutation}")[0]


def test_stage_cache_rejects_missing_outputs_and_failed_previous_stage(tmp_path: Path) -> None:
    cache = StageCache(tmp_path / "state.json", {"run_id": "one"})
    output = tmp_path / "output.json"
    cache.record(stage("assemble_pptx", "same", output))
    output.unlink()
    assert not cache.cached("assemble_pptx", "same")[0]
    cache.record({"stage_id": "assemble_pptx", "status": "failed", "input_fingerprint": "same", "outputs": [], "warnings": [], "errors": ["boom"]})
    assert not cache.cached("assemble_pptx", "same")[0]
