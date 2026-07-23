#!/usr/bin/env python3
"""Select draft Page Production Routes for a decomposed deck.

This script only writes route planning JSON. It does not generate images,
assemble PPTX, register assets, or approve routes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from design_intent_lifecycle import validate_for_route_selection  # noqa: E402
from route_normalization import normalize_route, normalize_route_record  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def slide_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("slides", "items", "design_intents"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if isinstance(payload.get("slide_number"), int):
            return [payload]
    return []


def by_slide(payload: Any) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for item in slide_items(payload):
        number = item.get("slide_number")
        if isinstance(number, int):
            result[number] = item
    return result


def text_blob(*values: Any) -> str:
    return " ".join(str(value or "") for value in values).lower()


def route_for(slide: dict[str, Any], intent: dict[str, Any]) -> dict[str, Any]:
    lifecycle_errors = validate_for_route_selection(intent)
    if lifecycle_errors:
        raise ValueError("; ".join(lifecycle_errors))
    number = int(slide.get("slide_number") or intent.get("slide_number") or 0)
    title = str(slide.get("title") or intent.get("title") or "")
    function = str(slide.get("page_function") or intent.get("page_function") or "")
    blob = text_blob(
        function,
        title,
        slide.get("visual_idea"),
        slide.get("core_message"),
        intent.get("main_visual_move"),
        intent.get("visual_metaphor"),
        intent.get("asset_intent", {}).get("visual_job") if isinstance(intent.get("asset_intent"), dict) else "",
    )

    if any(token in blob for token in ("execution", "执行", "流程", "排期", "预算", "权益", "人员", "四段", "现场体验")):
        selected = "template_native_plus_skin"
        archetype_id = "experience_path"
        route_reason = "Execution content needs editable native structure first; visual assets should skin the path/nodes instead of becoming a full-page reference."
        strategy = {
            "asset_count": 1,
            "asset_types": ["path_skin_asset", "node_marker_system"],
            "asset_roles": ["light-route skin for editable stage nodes"],
            "requires_whole_slide_field": False,
            "requires_element_assets": True,
            "requires_clean_substrate": False,
            "requires_visual_reference": False,
        }
        cost = "low"
        generations = 1
        iterations = 1
        why_native = "Native-only would become a plain process/table page and would not express the experience-system idea."
    elif any(token in blob for token in ("光场", "聚焦", "校准", "显影", "focus", "calibrated", "light field")):
        selected = "full_substrate_hybrid"
        archetype_id = "calibrated_focus"
        route_reason = "The page's core action is a calibrated light/focus field; a whole-slide textless substrate is justified, but it still needs EVC to avoid text overlay stack."
        strategy = {
            "asset_count": 1,
            "asset_types": ["full_slide_clean_substrate"],
            "asset_roles": ["calibrated focus field with text-safe anchor zones"],
            "requires_whole_slide_field": True,
            "requires_element_assets": False,
            "requires_clean_substrate": True,
            "requires_visual_reference": False,
        }
        cost = "medium"
        generations = 1
        iterations = 2
        why_native = "Native-only cannot create the calibrated light/focus field with enough proposal-level visual impact."
    elif any(token in blob for token in ("strategy", "策略", "判断", "机制", "认知", "路径", "坐标", "汇聚", "position")):
        selected = "element_asset_hybrid"
        archetype_id = "focal_convergence"
        route_reason = "The page can be built from focused visual elements: positioning point, evidence/path strands, and decision-layer cues composed with editable argument labels."
        strategy = {
            "asset_count": 3,
            "asset_types": ["position_marker", "path_strands", "layer_field"],
            "asset_roles": [
                "clear clinical position marker",
                "evidence/path trajectories",
                "subtle decision-layer context"
            ],
            "requires_whole_slide_field": False,
            "requires_element_assets": True,
            "requires_clean_substrate": False,
            "requires_visual_reference": False,
        }
        cost = "medium"
        generations = 2
        iterations = 2
        why_native = "Native-only would make the strategy page feel like text reasoning without visual proof."
    else:
        selected = "element_asset_hybrid"
        archetype_id = "editorial_argument_spread"
        route_reason = "Default to focused element assets plus editable composition because no whole-slide field requirement is proven."
        strategy = {
            "asset_count": 2,
            "asset_types": ["visual_anchor", "supporting_marker"],
            "asset_roles": ["page-specific visual anchor", "editable text support marker"],
            "requires_whole_slide_field": False,
            "requires_element_assets": True,
            "requires_clean_substrate": False,
            "requires_visual_reference": False,
        }
        cost = "medium"
        generations = 1
        iterations = 1
        why_native = "Native-only may be too plain for a creative proposal page."

    return normalize_route_record({
        "slide_number": number,
        "page_title": title,
        "selected_route": selected,
        "composition_archetype_id": archetype_id,
        "composition_archetype_status": "draft_suggested_not_approved",
        "route_reason": route_reason,
        "why_not_full_reference": "Visual Reference Mode is not needed by default; the selected route can be tested at lower cost before any full-page reference workflow.",
        "why_not_native_only": why_native,
        "visual_asset_strategy": strategy,
        "cost_level": cost,
        "expected_generation_count": generations,
        "expected_iteration_count": iterations,
        "approval": {
            "approved": False,
            "approved_by": "",
            "approval_notes": "",
        },
    })


def parse_expected_route(value: str) -> tuple[int, str, str]:
    parts = value.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("expected route must use slide_number:selected_route:composition_archetype_id")
    try:
        slide_number = int(parts[0])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected route slide_number must be an integer") from exc
    if not parts[1] or not parts[2]:
        raise argparse.ArgumentTypeError("expected route and composition archetype must be non-empty")
    return slide_number, parts[1], parts[2]


def validate_routes(
    routes: list[dict[str, Any]],
    expected_routes: list[tuple[int, str, str]] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    required_archetype_routes = {
        "element_asset_hybrid",
        "template_native_plus_skin",
        "full_substrate_hybrid",
    }
    selected_routes: dict[str, str] = {}
    composition_archetypes: dict[str, str] = {}

    for route in routes:
        number = route.get("slide_number")
        route_info = normalize_route(route.get("selected_route"), strict=False)
        selected = str(route_info.get("canonical_route") or "")
        archetype_id = str(route.get("composition_archetype_id") or "")
        key = str(number)
        selected_routes[key] = selected
        composition_archetypes[key] = archetype_id

        if not selected:
            errors.append(f"slide {number}: selected_route is required")
        if not archetype_id:
            errors.append(f"slide {number}: composition_archetype_id is required")
        if selected in required_archetype_routes and not archetype_id:
            errors.append(f"slide {number}: {selected} requires non-empty composition_archetype_id")

    route_by_slide = {
        int(route.get("slide_number")): route
        for route in routes
        if isinstance(route.get("slide_number"), int)
    }
    for slide_number, expected_selected, expected_archetype in expected_routes or []:
        route = route_by_slide.get(slide_number)
        if route is None:
            errors.append(f"slide {slide_number}: expected route is missing")
            continue
        actual_selected = route.get("selected_route")
        actual_archetype = route.get("composition_archetype_id")
        if actual_selected != expected_selected:
            errors.append(
                f"slide {slide_number}: expected selected_route={expected_selected}, got {actual_selected}"
            )
        if actual_archetype != expected_archetype:
            errors.append(
                f"slide {slide_number}: expected composition_archetype_id={expected_archetype}, got {actual_archetype}"
            )

    return {
        "valid": not errors,
        "route_count": len(routes),
        "errors": errors,
        "warnings": warnings,
        "selected_routes": selected_routes,
        "composition_archetypes": composition_archetypes,
        "visual_reference_pages": [
            route.get("slide_number")
            for route in routes
            if route.get("selected_route") == "visual_reference_mode"
        ],
        "total_expected_generation_count": sum(
            int(route.get("expected_generation_count") or 0) for route in routes
        ),
        "total_expected_iteration_count": sum(
            int(route.get("expected_iteration_count") or 0) for route in routes
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("page_decomposition", type=Path)
    parser.add_argument("design_intent", type=Path)
    parser.add_argument("visual_bible", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--validation-out", type=Path)
    parser.add_argument(
        "--expect-route",
        type=parse_expected_route,
        action="append",
        default=[],
        metavar="SLIDE:ROUTE:ARCHETYPE",
        help="Require one slide to match selected_route and composition_archetype_id.",
    )
    args = parser.parse_args()

    page_payload = load_json(args.page_decomposition)
    intent_payload = load_json(args.design_intent)
    visual_bible = load_json(args.visual_bible)

    intents = by_slide(intent_payload)
    routes = []
    for slide in slide_items(page_payload):
        number = slide.get("slide_number")
        if not isinstance(number, int):
            continue
        routes.append(route_for(slide, intents.get(number, {})))

    output = {
        "route_version": "v4s_plus_route_patch",
        "project_name": visual_bible.get("project_name", "") if isinstance(visual_bible, dict) else "",
        "default_priority": [
            "element_asset_hybrid",
            "template_native_plus_skin for execution/data pages",
            "full_substrate_hybrid only when whole-field visual is required",
            "visual_reference_mode only when high-design full-page reference is necessary",
            "pure_native_safety for highly editable/compliance-heavy pages"
        ],
        "routes": routes,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.validation_out:
        validation = validate_routes(routes, args.expect_route)
        args.validation_out.parent.mkdir(parents=True, exist_ok=True)
        args.validation_out.write_text(
            json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if validation["errors"]:
            print(args.validation_out)
            return 1
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
