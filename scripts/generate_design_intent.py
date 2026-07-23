#!/usr/bin/env python3
"""Generate a draft Design Intent from page decomposition and Visual Bible."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return payload


def editable_names(editable_layer: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("title", "page_number"):
        item = editable_layer.get(key)
        if isinstance(item, dict):
            names.append(str(item.get("id") or item.get("role") or key))
    for group in ("body", "labels", "data", "table_text", "notes"):
        for item in as_list(editable_layer.get(group)):
            if isinstance(item, dict):
                names.append(str(item.get("id") or item.get("role") or group))
    return names


def compact_text(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text if text else fallback


def build_design_intent(page: dict[str, Any], visual_bible: dict[str, Any], source_excerpt: str = "") -> dict[str, Any]:
    editable_layer = as_dict(page.get("editable_layer"))
    generated = [item for item in as_list(page.get("generated_layer")) if isinstance(item, dict)]
    primary_asset = generated[0] if generated else {}
    project_bans = [str(item) for item in as_list(visual_bible.get("do_not_use")) if str(item).strip()]
    title = compact_text(page.get("title"), "Untitled slide")
    core_message = compact_text(page.get("core_message"), "the page's core message")
    audience_takeaway = compact_text(page.get("audience_takeaway"), core_message)
    visual_idea = compact_text(page.get("visual_idea"), "a project-specific visual idea")
    composition = as_dict(page.get("composition_plan"))
    integration = compact_text(composition.get("integration_logic"), "editable text must participate in the visual logic")
    relationship_type = "anchored" if "anchor" in integration.lower() or "锚" in integration else "structural_label"
    page_bans = [
        "project-irrelevant stock metaphor",
        "generic technology background",
        "literal icon row",
        "left text plus right image",
        "ordinary bullet list",
        "cards",
        "shadows",
        "baked title or body copy inside image",
    ]
    do_not_do = []
    for item in project_bans + page_bans:
        if item not in do_not_do:
            do_not_do.append(item)

    return {
        "slide_number": page.get("slide_number"),
        "title": title,
        "page_function": page.get("page_function", ""),
        "intent_version": "v1",
        "lifecycle_status": "draft_for_routing",
        "route_binding": None,
        "design_problem": f"The audience may not immediately understand why this page's claim matters: {core_message}",
        "desired_perception": audience_takeaway,
        "core_design_argument": f"The design must make the page argument visible instead of turning it into ordinary explanatory copy: {visual_idea}",
        "main_visual_move": "Turn the page argument into an integrated visual structure.",
        "visual_metaphor": "Project-specific metaphor to be derived from the active script and visual bible.",
        "why_this_works": "A project-specific metaphor is required because generic style language cannot prove the page argument.",
        "rejected_directions": [
            {"direction": "generic style background", "reason": "It decorates the slide but does not prove the page argument."},
            {"direction": "literal icon explanation", "reason": "It turns the page into a normal explanation slide rather than a creative proposal page."},
            {"direction": "left text plus right image", "reason": "It separates editable text from the visual logic instead of making them work together."},
        ],
        "text_image_relationship": {
            "relationship_type": relationship_type,
            "description": integration,
            "must_not_be": [
                "adjacent left text plus right image",
                "ordinary bullet list",
                "text baked into generated image",
            ],
        },
        "editable_strategy": {
            "must_remain_editable": editable_names(editable_layer),
            "how_editable_text_participates_in_visual": integration,
            "what_must_not_be_baked_into_image": [
                "slide title",
                "page number",
                "main argument",
                "proof points",
                "section label",
                "long Chinese body copy",
            ],
        },
        "asset_intent": {
            "asset_type": primary_asset.get("asset_type", "full_slide_visual_substrate"),
            "visual_job": compact_text(primary_asset.get("visual_role"), "provide the page's visual argument structure"),
            "what_it_must_prove": core_message,
            "what_breaks_if_removed": "The page loses its visual proof structure and collapses into editable text without the intended argument logic.",
        },
        "layout_intent": {
            "composition_logic": compact_text(composition.get("type"), "Use the approved composition plan as the page structure."),
            "negative_space_logic": "Negative space must preserve readability while still supporting the page's visual logic.",
            "visual_hierarchy": "The generated/sourced asset carries the visual argument; editable text clarifies and labels the argument.",
            "native_support_role": "Native PPT graphics may only provide light alignment or labeling support, not the main visual identity.",
        },
        "do_not_do": do_not_do,
        "prompt_brief": f"Create a project-specific proposal visual asset that makes this page argument visible: {core_message}. The visual must integrate with editable PowerPoint text and avoid generic decoration, left-text/right-image composition, icons-as-explanation, cards, shadows, labels, logos, and baked copy.",
        "visual_qa_expectations": [
            "design intent is visible",
            "text participates in visual logic",
            "asset is structural, not decorative",
            "editable text remains editable",
        ],
        "source_excerpt": source_excerpt,
        "approved": False,
        "approved_by": "",
        "approval_notes": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("page_decomposition", help="Path to page_decomposition JSON.")
    parser.add_argument("visual_bible", help="Path to visual_bible JSON.")
    parser.add_argument("--source-excerpt", default="", help="Optional source excerpt text.")
    parser.add_argument("--out", required=True, help="Output design_intent.json path.")
    args = parser.parse_args()

    page = load_json(Path(args.page_decomposition))
    visual_bible = load_json(Path(args.visual_bible))
    design_intent = build_design_intent(page, visual_bible, args.source_excerpt)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(design_intent, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Design intent: {out}")
    print(f"approved: {design_intent['approved']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
