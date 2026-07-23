"""Small real-runtime fixture builder used by Phase 5X-R tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from test_assembly_integration import prepare_project, runtime_blueprint


def create_runtime_case(tmp_path: Path, *, case_id: str = "trusted_case", preview: bool = False, advisory: bool = False) -> tuple[Path, Path]:
    project, blueprint_path = prepare_project(tmp_path)
    blueprint = runtime_blueprint()
    slide = blueprint["slides"][0]
    evc = slide.pop("editable_visual_composition")
    slide["editable_visual_composition_ref"] = "evc.json"
    blueprint_path.write_text(json.dumps(blueprint, ensure_ascii=False), encoding="utf-8")
    intent_path = project / "design_intent.json"
    intent_path.write_text(json.dumps(slide["design_intent"], ensure_ascii=False), encoding="utf-8")
    route_path = project / "route.json"
    route_path.write_text(json.dumps({"page_production_route": slide["page_production_route"]}, ensure_ascii=False), encoding="utf-8")
    evc_path = project / "evc.json"
    evc_path.write_text(json.dumps(evc, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "manifest_version": "1.0",
        "case_id": case_id,
        "case_kind": "synthetic_test",
        "source": {"source_pptx": None, "template_pptx": None},
        "inputs": {
            "blueprint": str(blueprint_path), "design_intent": str(intent_path), "route": str(route_path), "evc": str(evc_path),
            "asset_registry": str(project / "assets" / "asset_slots.json"), "asset_plan": None, "assets_dir": str(project / "assets"),
        },
        "output": {"root": str(project / "runtime_case"), "allow_overwrite": False},
        "stages": {"assemble": True, "package_inspection": True, "no_shadow_scan": True, "preview": preview, "layout_intelligence_advisory": advisory},
        "runtime_options": {"resume": True, "fail_on_unsupported_required_field": True, "preview_dpi": 96},
    }
    manifest_path = project / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return project, manifest_path
