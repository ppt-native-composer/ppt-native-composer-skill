from __future__ import annotations

from test_assembly_integration import prepare_project

import json

from assemble_pptx import assemble


def test_requested_and_applied_values_are_present(tmp_path) -> None:
    project, blueprint = prepare_project(tmp_path)
    assemble(blueprint, project / "map.pptx", project)
    payload = json.loads((project / "editability_map_v2.json").read_text(encoding="utf-8"))
    text = next(item for item in payload["objects"] if item.get("object_type") == "editable_text")
    assert text["requested_geometry"]
    assert text["applied_geometry"]
    assert text["requested_typography"]
    assert text["applied_typography"]
    assert "deviations" in text
    assert "unsupported_fields" in text
