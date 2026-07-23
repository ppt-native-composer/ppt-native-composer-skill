from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from relational_typography import resolve_binding


def item(binding: dict) -> dict:
    return {"id": "label", "zone": {"x": 1.0, "y": 1.0, "w": 1.4, "h": 0.35}, "relational_binding": binding}


def test_title_to_visual_entry_resolves_path_start() -> None:
    result = resolve_binding(item({"binding_type": "composition_axis", "binding_target_id": "map_entry_axis", "attachment": "start", "orientation": "horizontal", "reading_sequence": 1, "collision_policy": "fail", "minimum_clearance": 0.12, "fallback_behavior": "fail"}), [{"id": "map_entry_axis", "type": "axis", "path_points": [{"x": 1, "y": 1.5}, {"x": 5, "y": 3}]}])
    assert result["evidence"]["resolved_target"]["id"] == "map_entry_axis"
    assert result["evidence"]["resolved_anchor"]["path_position"] == 0.0
    assert result["geometry"]["x"] == 1.0


def test_converging_path_statements_resolve_distinct_positions() -> None:
    target = [{"id": "curve_1", "type": "path", "path_points": [{"x": 1, "y": 2}, {"x": 8, "y": 3}]}]
    first = resolve_binding(item({"binding_type": "path", "binding_target_id": "curve_1", "attachment": "middle", "path_position": 0.2, "orientation": "horizontal", "reading_sequence": 1, "collision_policy": "avoid", "minimum_clearance": 0.15, "fallback_behavior": "fail"}), target)
    second = resolve_binding(item({"binding_type": "path", "binding_target_id": "curve_1", "attachment": "middle", "path_position": 0.8, "orientation": "horizontal", "reading_sequence": 2, "collision_policy": "avoid", "minimum_clearance": 0.15, "fallback_behavior": "fail"}), target)
    assert first["geometry"]["x"] < second["geometry"]["x"]


def test_beam_progression_labels_supports_tangent_orientation() -> None:
    result = resolve_binding(item({"binding_type": "path", "binding_target_id": "beam", "attachment": "middle", "path_position": 0.5, "orientation": "tangent", "reading_sequence": 2, "collision_policy": "warn", "minimum_clearance": 0.1, "fallback_behavior": "fail"}), [{"id": "beam", "type": "beam", "path_points": [{"x": 1, "y": 3}, {"x": 4, "y": 3.5}, {"x": 9, "y": 2.5}]}])
    assert result["rotation"] != 0


def test_evidence_admission_gate_binds_claim_to_node() -> None:
    result = resolve_binding(item({"binding_type": "node", "binding_target_id": "review_gate", "attachment": "outside", "preferred_side": "right", "orientation": "horizontal", "reading_sequence": 2, "collision_policy": "fail", "minimum_clearance": 0.2, "fallback_behavior": "fail"}), [{"id": "review_gate", "type": "threshold", "geometry": {"x": 6, "y": 2, "w": 0.2, "h": 2}}])
    assert result["evidence"]["resolved_target"]["type"] == "threshold"
    assert result["geometry"]["x"] > 6


def test_sequential_node_labels_bind_to_each_node() -> None:
    result = resolve_binding(item({"binding_type": "node", "binding_target_id": "node_3", "attachment": "after", "orientation": "horizontal", "reading_sequence": 3, "collision_policy": "avoid", "minimum_clearance": 0.12, "fallback_behavior": "fail"}), [{"id": "node_3", "type": "glowing_node", "center": {"x": 8, "y": 4}, "size": {"w": 0.2, "h": 0.2}}])
    assert result["evidence"]["resolved_anchor"]["x"] == 8


def test_target_geometry_mutation_moves_text_without_zone_edit() -> None:
    binding = {"binding_type": "node", "binding_target_id": "focus", "attachment": "outside", "preferred_side": "left", "orientation": "horizontal", "reading_sequence": 1, "collision_policy": "fail", "minimum_clearance": 0.2, "fallback_behavior": "fail"}
    first = resolve_binding(item(binding), [{"id": "focus", "type": "focus", "geometry": {"x": 8, "y": 2, "w": 1, "h": 1}}])
    second = resolve_binding(item(binding), [{"id": "focus", "type": "focus", "geometry": {"x": 10, "y": 2, "w": 1, "h": 1}}])
    assert second["geometry"]["x"] > first["geometry"]["x"]


def test_missing_target_requires_explicit_fallback() -> None:
    binding = {"binding_type": "node", "binding_target_id": "missing", "attachment": "outside", "orientation": "horizontal", "reading_sequence": 1, "collision_policy": "fail", "minimum_clearance": 0.1, "fallback_behavior": "fail"}
    with pytest.raises(ValueError, match="target not found"):
        resolve_binding(item(binding), [])
    binding["fallback_behavior"] = "use_declared_zone"
    result = resolve_binding(item(binding), [])
    assert result["evidence"]["fallback"] == "use_declared_zone"


def test_invalid_binding_does_not_silently_fallback() -> None:
    with pytest.raises(ValueError, match="unsupported relational binding_type"):
        resolve_binding(item({"binding_type": "random", "binding_target_id": "x", "attachment": "middle", "orientation": "horizontal", "reading_sequence": 1, "collision_policy": "fail", "minimum_clearance": 0.1, "fallback_behavior": "fail"}), [])


def test_legacy_free_geometry_and_free_binding_are_explicit() -> None:
    legacy = resolve_binding({"zone": {"x": 1, "y": 2, "w": 3, "h": 0.4}})
    assert legacy["evidence"]["warning"]
    free = resolve_binding(item({"binding_type": "free", "binding_target_id": "", "attachment": "middle", "orientation": "horizontal", "reading_sequence": 1, "collision_policy": "avoid", "minimum_clearance": 0.1, "fallback_behavior": "fail"}))
    assert free["evidence"]["requested_binding"]["binding_type"] == "free"


def test_invalid_attachment_orientation_and_point_data_fail() -> None:
    base = {"binding_type": "path", "binding_target_id": "p", "attachment": "bad", "orientation": "horizontal", "reading_sequence": 1, "collision_policy": "fail", "minimum_clearance": 0.1, "fallback_behavior": "fail"}
    with pytest.raises(ValueError, match="attachment"):
        resolve_binding(item(base), [{"id": "p", "path_points": [{"x": 1, "y": 1}, {"x": 2, "y": 2}]}])
    base["attachment"] = "middle"; base["orientation"] = "bad"
    with pytest.raises(ValueError, match="orientation"):
        resolve_binding(item(base), [{"id": "p", "path_points": [{"x": 1, "y": 1}, {"x": 2, "y": 2}]}])
    with pytest.raises(ValueError, match="x/y"):
        resolve_binding(item({"binding_type": "path", "binding_target_id": "p", "attachment": "middle", "orientation": "horizontal", "reading_sequence": 1, "collision_policy": "fail", "minimum_clearance": 0.1, "fallback_behavior": "fail"}), [{"id": "p", "path_points": [{"x": 1}, {"x": 2, "y": 2}]}])


def test_path_offsets_and_normal_attachments_are_resolved() -> None:
    target = [{"id": "p", "path_points": [{"x": 1, "y": 1}, {"x": 4, "y": 4}]}]
    for attachment in ("before", "after", "normal"):
        result = resolve_binding(item({"binding_type": "path", "binding_target_id": "p", "attachment": attachment, "orientation": "normal", "path_position": 0.5, "offset": {"x": 0.1, "y": 0.2}, "reading_sequence": 1, "collision_policy": "avoid", "minimum_clearance": 0.1, "fallback_behavior": "fail"}), target)
        assert result["rotation"] != 0


def test_node_side_variants_and_inside_attachment() -> None:
    target = [{"id": "n", "geometry": {"x": 5, "y": 5, "w": 1, "h": 1}}]
    for side in ("left", "above", "below", "right"):
        result = resolve_binding(item({"binding_type": "node", "binding_target_id": "n", "attachment": "outside", "preferred_side": side, "orientation": "horizontal", "reading_sequence": 1, "collision_policy": "avoid", "minimum_clearance": 0.1, "fallback_behavior": "fail"}), target)
        assert "x" in result["geometry"]
    inside = resolve_binding(item({"binding_type": "node", "binding_target_id": "n", "attachment": "inside", "orientation": "horizontal", "reading_sequence": 1, "collision_policy": "avoid", "minimum_clearance": 0.1, "fallback_behavior": "fail"}), target)
    assert inside["geometry"]["x"] < 6


def test_path_and_target_geometry_errors_are_explicit() -> None:
    with pytest.raises(ValueError, match="at least two"):
        resolve_binding(item({"binding_type": "path", "binding_target_id": "p", "attachment": "middle", "orientation": "horizontal", "reading_sequence": 1, "collision_policy": "fail", "minimum_clearance": 0.1, "fallback_behavior": "fail"}), [{"id": "p", "path_points": [{"x": 1, "y": 1}]}])
    with pytest.raises(ValueError, match="requires geometry"):
        resolve_binding(item({"binding_type": "node", "binding_target_id": "n", "attachment": "middle", "orientation": "horizontal", "reading_sequence": 1, "collision_policy": "fail", "minimum_clearance": 0.1, "fallback_behavior": "fail"}), [{"id": "n"}])
