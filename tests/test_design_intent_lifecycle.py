from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from design_intent_lifecycle import approve, bind_to_route, validate_for_evc, validate_for_route_selection  # noqa: E402


def test_route_selection_accepts_only_draft_for_routing() -> None:
    assert validate_for_route_selection({"lifecycle_status": "draft_for_routing"}) == []
    assert validate_for_route_selection({"lifecycle_status": "route_bound"})


def test_route_bound_then_human_approved_is_required_for_evc() -> None:
    draft = {"lifecycle_status": "draft_for_routing", "approved": False}
    bound = bind_to_route(draft, "element_first_composition")
    assert bound["route_binding"]["selected_route"] == "element_asset_hybrid"
    assert validate_for_evc(bound, "element_asset_hybrid")
    approved = approve(bound, approved_by="human_reviewer", approval_notes="Approved")
    assert validate_for_evc(approved, "element_asset_hybrid") == []


def test_approval_before_route_binding_fails() -> None:
    with pytest.raises(ValueError):
        approve({"lifecycle_status": "draft_for_routing"}, approved_by="human_reviewer", approval_notes="No")
