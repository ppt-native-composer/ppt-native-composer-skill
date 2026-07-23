#!/usr/bin/env python3
"""Design Intent lifecycle helpers for the canonical production pipeline."""

from __future__ import annotations

from typing import Any

from route_normalization import normalize_route


LIFECYCLE_DRAFT_FOR_ROUTING = "draft_for_routing"
LIFECYCLE_ROUTE_BOUND = "route_bound"
LIFECYCLE_HUMAN_APPROVED = "human_approved"
LIFECYCLE_STATUSES = {
    LIFECYCLE_DRAFT_FOR_ROUTING,
    LIFECYCLE_ROUTE_BOUND,
    LIFECYCLE_HUMAN_APPROVED,
}


def lifecycle_status(intent: dict[str, Any]) -> str:
    return str(intent.get("lifecycle_status") or LIFECYCLE_DRAFT_FOR_ROUTING)


def validate_for_route_selection(intent: dict[str, Any]) -> list[str]:
    status = lifecycle_status(intent)
    if status != LIFECYCLE_DRAFT_FOR_ROUTING:
        return [f"route selection requires lifecycle_status=draft_for_routing, got {status}"]
    return []


def bind_to_route(intent: dict[str, Any], route: Any) -> dict[str, Any]:
    normalized = normalize_route(route)
    result = dict(intent)
    result["lifecycle_status"] = LIFECYCLE_ROUTE_BOUND
    result["route_binding"] = {
        "selected_route": normalized["canonical_route"],
        "route_provenance": normalized,
    }
    result["approved"] = False
    result["approved_by"] = ""
    result["approval_notes"] = ""
    return result


def approve(intent: dict[str, Any], *, approved_by: str, approval_notes: str) -> dict[str, Any]:
    status = lifecycle_status(intent)
    if status != LIFECYCLE_ROUTE_BOUND:
        raise ValueError(f"Design Intent approval requires route_bound status, got {status}")
    result = dict(intent)
    result["lifecycle_status"] = LIFECYCLE_HUMAN_APPROVED
    result["approved"] = True
    result["approved_by"] = approved_by
    result["approval_notes"] = approval_notes
    return result


def validate_for_evc(intent: dict[str, Any], route: Any) -> list[str]:
    errors: list[str] = []
    status = lifecycle_status(intent)
    if status != LIFECYCLE_HUMAN_APPROVED:
        errors.append(f"EVC requires lifecycle_status=human_approved, got {status}")
    if intent.get("approved") is not True:
        errors.append("EVC requires Design Intent approved=true")
    binding = intent.get("route_binding") if isinstance(intent.get("route_binding"), dict) else {}
    bound = normalize_route(binding.get("selected_route"), strict=False).get("canonical_route")
    requested = normalize_route(route, strict=False).get("canonical_route")
    if not bound:
        errors.append("EVC requires Design Intent route_binding.selected_route")
    elif requested and bound != requested:
        errors.append(f"Design Intent is bound to {bound}, not {requested}")
    return errors
