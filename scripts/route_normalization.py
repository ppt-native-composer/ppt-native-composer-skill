#!/usr/bin/env python3
"""Canonical Page Production Route normalization.

This module is the only production source for route vocabulary migration.
Callers must preserve the returned provenance instead of silently replacing a
legacy route value.
"""

from __future__ import annotations

from typing import Any


CANONICAL_ROUTES = (
    "element_asset_hybrid",
    "full_substrate_hybrid",
    "visual_reference_mode",
    "template_native_plus_skin",
    "pure_native_safety",
)

LEGACY_ROUTE_ALIASES = {
    "element_first_composition": "element_asset_hybrid",
    "element_based": "element_asset_hybrid",
    "element_hybrid": "element_asset_hybrid",
    "full_substrate": "full_substrate_hybrid",
    "full_slide_substrate": "full_substrate_hybrid",
    "template_native": "template_native_plus_skin",
    "native_only": "pure_native_safety",
}


class RouteNormalizationError(ValueError):
    """Raised when a route cannot be normalized to the canonical vocabulary."""


def normalize_route(value: Any, *, strict: bool = True) -> dict[str, Any]:
    raw = str(value or "").strip()
    lowered = raw.lower()
    if lowered in CANONICAL_ROUTES:
        canonical = lowered
        source = "canonical"
    elif lowered in LEGACY_ROUTE_ALIASES:
        canonical = LEGACY_ROUTE_ALIASES[lowered]
        source = "legacy_alias"
    else:
        if strict:
            raise RouteNormalizationError(f"Unknown page production route: {raw or '<missing>'}")
        canonical = ""
        source = "unknown"
    return {
        "raw_route": raw or None,
        "canonical_route": canonical or None,
        "normalization_source": source,
        "legacy_alias_used": source == "legacy_alias",
    }


def extract_route(payload: Any, *, strict: bool = True) -> dict[str, Any]:
    """Extract a route from canonical and legacy document shapes."""
    data = payload if isinstance(payload, dict) else {}
    candidates: list[tuple[str, Any]] = []
    route = data.get("route")
    if isinstance(route, dict):
        candidates.extend(
            [
                ("route.selected_route", route.get("selected_route")),
                ("route.route_id", route.get("route_id")),
            ]
        )
    page_route = data.get("page_production_route")
    if isinstance(page_route, dict):
        candidates.append(("page_production_route.selected_route", page_route.get("selected_route")))
    candidates.extend(
        [
            ("selected_route", data.get("selected_route")),
            ("route_id", data.get("route_id")),
        ]
    )
    slides = data.get("slides")
    if isinstance(slides, list):
        for index, slide in enumerate(slides):
            if not isinstance(slide, dict):
                continue
            slide_route = slide.get("page_production_route")
            if isinstance(slide_route, dict):
                candidates.append(
                    (f"slides[{index}].page_production_route.selected_route", slide_route.get("selected_route"))
                )
    for source_path, value in candidates:
        if value not in (None, ""):
            return {**normalize_route(value, strict=strict), "source_path": source_path}
    if strict:
        raise RouteNormalizationError("Page production route is missing")
    return {
        "raw_route": None,
        "canonical_route": None,
        "normalization_source": "missing",
        "legacy_alias_used": False,
        "source_path": None,
    }


def normalize_route_record(record: dict[str, Any]) -> dict[str, Any]:
    result = dict(record)
    info = normalize_route(record.get("selected_route"))
    result["selected_route"] = info["canonical_route"]
    result["route_provenance"] = info
    return result
