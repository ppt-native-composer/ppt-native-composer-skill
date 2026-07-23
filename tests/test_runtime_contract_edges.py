from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pptx import Presentation

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from artifact_integrity import validate_artifact
from assembly_pipeline import AssemblyPipelineError, _read_object, resolve_presentation_source, resolve_route_input, validate_design_intent_lifecycle, validate_saved_presentation
from runtime_stage_cache import StageCache, file_digest, paths_digest, toolchain_fingerprint


def test_artifact_integrity_error_contracts(tmp_path: Path) -> None:
    assert not validate_artifact(tmp_path / "missing.pptx", "pptx")["valid"]
    malformed = tmp_path / "malformed.json"; malformed.write_text("{", encoding="utf-8")
    assert not validate_artifact(malformed, "json")["valid"]
    array = tmp_path / "array.json"; array.write_text("[]", encoding="utf-8")
    assert not validate_artifact(array, "json")["valid"]
    assert not validate_artifact(tmp_path / "missing.png", "image")["valid"]
    empty = tmp_path / "empty.txt"; empty.write_text("", encoding="utf-8")
    assert not validate_artifact(empty, "text")["valid"]
    assert file_digest(tmp_path / "none") is None
    assert paths_digest([tmp_path / "none"])[str(tmp_path / "none")] is None


def test_stage_cache_rejects_bad_records(tmp_path: Path) -> None:
    cache = StageCache(tmp_path / "cache.json", {"case": "edge"})
    for record in (
        {"stage_id": "bad", "status": "failed", "input_fingerprint": "x"},
        {"stage_id": "missing", "status": "executed", "input_fingerprint": "x", "artifacts": []},
        {"stage_id": "malformed", "status": "executed", "input_fingerprint": "x", "artifacts": [{}]},
    ):
        cache.record(record)
    assert not cache.cached("bad", "x")[0]
    assert not cache.cached("missing", "x")[0]
    assert not cache.cached("malformed", "x")[0]
    marker = tmp_path / "marker"; marker.write_text("x", encoding="utf-8")
    assert toolchain_fingerprint(SCRIPTS.parent, [marker])["fingerprint"]


def test_stage_cache_rejects_hash_and_metadata_drift(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"; artifact.write_text("trusted", encoding="utf-8")
    cache = StageCache(tmp_path / "cache.json", {})
    base = {"stage_id": "x", "status": "executed", "input_fingerprint": "same", "dependency_fingerprints": {}, "artifacts": [{"path": str(artifact), "artifact_type": "text", "required_keys": [], "sha256": "wrong", "metadata": {}}]}
    cache.record(base)
    assert "hash changed" in cache.cached("x", "same", {})[1]
    from artifact_integrity import validate_artifact
    base["artifacts"][0]["sha256"] = validate_artifact(artifact, "text")["sha256"]
    base["artifacts"][0]["metadata"] = {"unexpected": True}
    cache.record(base)
    assert "metadata changed" in cache.cached("x", "same", {})[1]


def test_pipeline_rejects_ambiguous_contract_inputs(tmp_path: Path) -> None:
    with pytest.raises(AssemblyPipelineError):
        resolve_presentation_source(tmp_path / "a.pptx", tmp_path / "b.pptx", None, None)
    array = tmp_path / "array.json"; array.write_text("[]", encoding="utf-8")
    with pytest.raises(AssemblyPipelineError):
        _read_object(array, "edge")
    blueprint = {"slides": [{"page_production_route": {"selected_route": "element_asset_hybrid"}}]}
    with pytest.raises(AssemblyPipelineError):
        resolve_route_input(blueprint, {"page_production_route": {}})
    intent = {"slides": [{"design_intent": {}} , {"design_intent": {}}]}
    with pytest.raises(AssemblyPipelineError):
        validate_design_intent_lifecycle({"slides": [{}]}, intent, "element_asset_hybrid")


def test_pipeline_source_and_route_edge_paths(tmp_path: Path) -> None:
    with pytest.raises(AssemblyPipelineError):
        resolve_presentation_source(tmp_path / "missing.pptx", None, None, None)
    invalid = tmp_path / "invalid.pptx"; invalid.write_text("bad", encoding="utf-8")
    with pytest.raises(AssemblyPipelineError):
        resolve_presentation_source(invalid, None, None, None)
    valid = tmp_path / "valid.pptx"; Presentation().save(valid)
    _, _, provenance = resolve_presentation_source(valid, None, None, None)
    assert provenance and provenance["source_kind"] == "source_pptx"
    blank, _, none = resolve_presentation_source(None, None, None, None)
    assert none is None and blank.slide_width > 0
    with pytest.raises(AssemblyPipelineError):
        validate_saved_presentation(invalid)
    blueprint = {"slides": ["not a slide"]}
    route = resolve_route_input(blueprint, {"page_production_route": {"selected_route": "element_asset_hybrid"}})
    assert route["canonical_route"] == "element_asset_hybrid"
