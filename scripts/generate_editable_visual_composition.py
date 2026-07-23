#!/usr/bin/env python3
"""Build or validate Editable Visual Composition prompts.

This script does not call an LLM, generate images, register assets, assemble
PPTX, or special-case slide numbers. Page-specific hand-authored examples live
under fixtures/examples and may be used as few-shot material by a separate LLM
workflow.
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

from validate_blueprint import editable_source_items, load_composition_archetype_object, load_route_object  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def find_slide(payload: Any, slide_number: int) -> dict[str, Any]:
    if isinstance(payload, dict):
        for key in ("slides", "items", "design_intents", "routes", "archetypes"):
            items = payload.get(key)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and item.get("slide_number") == slide_number:
                        return item
        if payload.get("slide_number") == slide_number:
            return payload
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and item.get("slide_number") == slide_number:
                return item
    raise SystemExit(f"Could not find slide_number={slide_number}")


def asset_summary(slide: dict[str, Any], asset_manifest: Any) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for key in ("generated_layer", "sourced_asset_layer"):
        for item in slide.get(key, []) if isinstance(slide.get(key), list) else []:
            if isinstance(item, dict):
                assets.append(
                    {
                        "asset_id": item.get("asset_id"),
                        "asset_type": item.get("asset_type"),
                        "visual_role": item.get("visual_role"),
                        "expected_zone": item.get("expected_zone"),
                        "asset_visual_map": item.get("asset_visual_map", {}),
                    }
                )
    if isinstance(asset_manifest, dict):
        for item in asset_manifest.get("assets", asset_manifest.get("slots", [])) or []:
            if isinstance(item, dict):
                assets.append(
                    {
                        "asset_id": item.get("asset_id") or item.get("id"),
                        "status": item.get("status"),
                        "x": item.get("x"),
                        "y": item.get("y"),
                        "w": item.get("w"),
                        "h": item.get("h"),
                    }
                )
    return assets


def prompt_for(
    *,
    slide: dict[str, Any],
    design_intent: dict[str, Any],
    visual_bible: dict[str, Any],
    route: dict[str, Any],
    archetype: dict[str, Any],
    assets: list[dict[str, Any]],
) -> str:
    source_items = editable_source_items(slide.get("editable_layer") if isinstance(slide.get("editable_layer"), dict) else {})
    source_payload = [
        {
            "source_id": item_id,
            "role": item.get("role"),
            "text": item.get("text"),
            "zone": item.get("zone"),
        }
        for item_id, item in source_items.items()
    ]
    contract = {
        "task": "Create one schema-compliant Editable Visual Composition JSON. Do not assemble PPTX.",
        "approval": {"approved": False, "approved_by": "", "approval_notes": ""},
        "hard_rules": [
            "Every source editable text object must appear exactly once in editable_objects.",
            "Use source_id equal to the editable_layer id.",
            "Text must match source text exactly unless text_revision_approved=true with an explicit note.",
            "Every editable object must have zone.",
            "Every native_support item must have zone.",
            "typographic_treatment must include hierarchy_level.",
            "relationship_to_asset must reference an asset slot or state no_asset_relation.",
            "near_focus must reference focus_point, along_axis must reference primary_axis, floating_in_quiet_field must reference quiet_fields, and on_path must reference path_points when asset_visual_map is available.",
            "Do not use cards, shadows, rounded containers, icons, or baked image text to solve hierarchy.",
        ],
    }
    payload = {
        "contract": contract,
        "slide": {
            "slide_number": slide.get("slide_number"),
            "title": slide.get("title"),
            "page_function": slide.get("page_function"),
            "page_mode": slide.get("page_mode"),
            "visual_idea": slide.get("visual_idea"),
        },
        "design_intent": design_intent,
        "page_production_route": route,
        "composition_archetype": archetype,
        "visual_bible": {
            "style_direction": visual_bible.get("style_direction"),
            "design_tokens": visual_bible.get("design_tokens"),
            "font_plan": visual_bible.get("font_plan"),
            "do_not_use": visual_bible.get("do_not_use"),
        },
        "editable_layer_source_text": source_payload,
        "asset_manifest_or_slots": assets,
        "output_shape": {
            "slide_number": slide.get("slide_number"),
            "title": slide.get("title"),
            "composition_version": "v1",
            "text_layer_concept": "",
            "why_text_is_visual": "",
            "editable_objects": [],
            "native_support": [],
            "anti_patterns": [
                "plain bullet list",
                "left text block plus right image",
                "ordinary paragraph stack",
                "card stack",
                "shadow container",
                "generated image plus text overlay without relationship",
            ],
            "approval": contract["approval"],
        },
    }
    return (
        "You are designing the editable text composition layer for a PPT page.\n"
        "Return JSON only. Follow this contract exactly.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
    )


def validate_evc_output(evc: dict[str, Any], slide: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for field in ("slide_number", "title", "composition_version", "text_layer_concept", "why_text_is_visual", "editable_objects", "native_support", "anti_patterns", "approval"):
        if field not in evc:
            errors.append(f"editable_visual_composition missing {field}")
    if evc.get("approval", {}).get("approved") is not False:
        warnings.append("editable_visual_composition.approval.approved should default to false before human review")

    source = editable_source_items(slide.get("editable_layer") if isinstance(slide.get("editable_layer"), dict) else {})
    objects = [item for item in evc.get("editable_objects", []) if isinstance(item, dict)]
    by_source: dict[str, dict[str, Any]] = {}
    for item in objects:
        source_id = str(item.get("source_id") or "").strip()
        if not source_id:
            errors.append(f"editable object {item.get('id') or '<unknown>'} missing source_id")
            continue
        by_source[source_id] = item
    for source_id, item in source.items():
        evc_item = by_source.get(source_id)
        if not evc_item:
            errors.append(f"missing editable object for source_id {source_id}")
            continue
        if evc_item.get("text") != item.get("text") and evc_item.get("text_revision_approved") is not True:
            errors.append(f"text changed for {source_id} without text_revision_approved=true")
        if not isinstance(evc_item.get("zone"), dict):
            errors.append(f"editable object {source_id} missing zone")
        treatment = evc_item.get("typographic_treatment") if isinstance(evc_item.get("typographic_treatment"), dict) else {}
        if "hierarchy_level" not in treatment:
            errors.append(f"editable object {source_id} missing typographic_treatment.hierarchy_level")
        rel = evc_item.get("relationship_to_asset") if isinstance(evc_item.get("relationship_to_asset"), dict) else {}
        if not rel:
            errors.append(f"editable object {source_id} missing relationship_to_asset")
    for idx, item in enumerate(evc.get("native_support", []), start=1):
        if isinstance(item, dict) and not isinstance(item.get("zone"), dict):
            errors.append(f"native_support[{idx}] missing zone")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("design_intent", type=Path)
    parser.add_argument("page_decomposition", type=Path)
    parser.add_argument("visual_bible", type=Path)
    parser.add_argument("--slide-number", type=int, required=True)
    parser.add_argument("--page-production-route", type=Path, required=True)
    parser.add_argument("--composition-archetype", type=Path, required=True)
    parser.add_argument("--asset-manifest", type=Path)
    parser.add_argument("--prompt-only", action="store_true", help="Write the prompt for an external LLM and exit.")
    parser.add_argument("--validate-output", type=Path, help="Validate an LLM-returned EVC JSON instead of building a prompt.")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    design_payload = load_json(args.design_intent)
    page_payload = load_json(args.page_decomposition)
    visual_bible = load_json(args.visual_bible)
    route_payload = load_json(args.page_production_route)
    archetype_payload = load_json(args.composition_archetype)
    manifest_payload = load_json(args.asset_manifest) if args.asset_manifest and args.asset_manifest.exists() else {}

    intent = find_slide(design_payload, args.slide_number)
    slide = find_slide(page_payload, args.slide_number)
    route = load_route_object(route_payload, args.slide_number, args.page_production_route.parent) or find_slide(route_payload, args.slide_number)
    archetype = load_composition_archetype_object(archetype_payload, args.slide_number, args.composition_archetype.parent) or archetype_payload
    assets = asset_summary(slide, manifest_payload)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.validate_output:
        evc = load_json(args.validate_output)
        if not isinstance(evc, dict):
            raise SystemExit("EVC output root must be an object")
        errors, warnings = validate_evc_output(evc, slide)
        args.out.write_text(json.dumps({"errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(args.out)
        return 1 if errors else 0

    if not args.prompt_only:
        raise SystemExit("Only --prompt-only and --validate-output modes are supported. This script does not call a model.")
    prompt = prompt_for(slide=slide, design_intent=intent, visual_bible=visual_bible, route=route, archetype=archetype, assets=assets)
    args.out.write_text(prompt, encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
