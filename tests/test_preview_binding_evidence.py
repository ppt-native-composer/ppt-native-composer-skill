from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_preview_binding_evidence import build_evidence  # noqa: E402


def test_preview_binding_evidence_never_auto_approves_visual_binding() -> None:
    text = {"objects": [{"object_type": "editable_text", "source_object_id": "claim", "pptx_shape_name": "claim", "editable": True, "applied_geometry": {"x": 1}}]}
    runtime = {"slides": [{"slide_number": 2, "objects": text["objects"]}]}
    evc = {"editable_objects": [{"source_id": "claim", "visual_behavior": "focal_label", "relationship_to_asset": {"asset_id": "node"}}]}
    evidence = build_evidence(text, runtime, evc, "preview.png", "case", {})
    record = evidence["records"][0]
    assert record["mechanical_evidence_status"] == "pass"
    assert record["human_review_status"] == "manual_required"
    assert record["binding_status"] == "manual_required"
    assert evidence["enforcement"] is False
