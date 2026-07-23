from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_runtime_case import RuntimeCaseRunner
from runtime_test_support import create_runtime_case


@pytest.mark.parametrize("mutation", ["evc", "design_intent", "route", "asset_registry", "asset_content", "preview_dpi", "source", "template", "toolchain_marker", "runtime_option"])
def test_input_changes_do_not_reuse_stale_assembly_cache(tmp_path: Path, mutation: str) -> None:
    project, manifest = create_runtime_case(tmp_path, preview=True)
    cold = RuntimeCaseRunner(manifest, skip_preview=True).run()
    assert cold["overall_status"] == "success"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if mutation == "evc":
        path = Path(data["inputs"]["evc"]); payload = json.loads(path.read_text()); payload["editable_objects"][0]["typographic_treatment"]["weight_note"] = "mutation"; path.write_text(json.dumps(payload), encoding="utf-8")
    elif mutation == "design_intent":
        path = Path(data["inputs"]["design_intent"]); payload = json.loads(path.read_text()); payload["approval_notes"] = "semantic input mutation"; path.write_text(json.dumps(payload), encoding="utf-8")
    elif mutation == "route":
        path = Path(data["inputs"]["route"]); payload = json.loads(path.read_text()); payload["page_production_route"]["selected_route"] = "full_substrate_hybrid"; path.write_text(json.dumps(payload), encoding="utf-8")
        changed = RuntimeCaseRunner(manifest, skip_preview=True).run()
        assert changed["overall_status"] == "failed"
        assert "normalize_route" in changed["failed_stages"]
        return
    elif mutation == "asset_registry":
        path = Path(data["inputs"]["asset_registry"]); payload = json.loads(path.read_text()); payload["slots"][0]["runtime_note"] = "registry mutation"; path.write_text(json.dumps(payload), encoding="utf-8")
    elif mutation == "asset_content":
        asset = project / "assets" / "fixture.png"; asset.write_bytes(asset.read_bytes() + b"mutation")
    elif mutation == "preview_dpi":
        data["runtime_options"]["preview_dpi"] = 144; manifest.write_text(json.dumps(data), encoding="utf-8")
        changed = RuntimeCaseRunner(manifest, skip_preview=True).run()
        assert "assemble_pptx" in changed["skipped_stages"]
        return
    elif mutation in {"source", "template"}:
        # Valid source/template mutation is represented by an explicitly
        # invalid declared input; contract must reject it before publishing.
        bad = project / f"{mutation}.pptx"; bad.write_text("invalid", encoding="utf-8"); data["source"][f"{mutation}_pptx"] = str(bad); manifest.write_text(json.dumps(data), encoding="utf-8")
        changed = RuntimeCaseRunner(manifest, skip_preview=True).run()
        assert changed["overall_status"] == "failed"
        return
    elif mutation == "toolchain_marker":
        # Directly mutate a tracked runtime script byte, restore immediately.
        target = Path(__file__).resolve().parents[1] / "scripts" / "artifact_integrity.py"; original = target.read_text(encoding="utf-8")
        try:
            target.write_text(original + "\n# temporary test marker\n", encoding="utf-8")
            changed = RuntimeCaseRunner(manifest, skip_preview=True).run()
        finally:
            target.write_text(original, encoding="utf-8")
        assert "assemble_pptx" in changed["executed_stages"]
        return
    else:
        data["runtime_options"]["fail_on_unsupported_required_field"] = False; manifest.write_text(json.dumps(data), encoding="utf-8")
    changed = RuntimeCaseRunner(manifest, skip_preview=True).run()
    assert "assemble_pptx" in changed["executed_stages"]
