#!/usr/bin/env python3
"""Deprecated: generate a legacy draft Designer Storyboard.

New V4-R work should use generate_design_intent.py instead. This file is kept
only to avoid breaking existing references.
"""

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


def editable_objects(editable_layer: dict[str, Any]) -> list[str]:
    objects: list[str] = []
    for key in ("title", "page_number"):
        item = editable_layer.get(key)
        if isinstance(item, dict):
            objects.append(str(item.get("id") or item.get("role") or key))
    for group in ("body", "labels", "data", "table_text", "notes"):
        for item in as_list(editable_layer.get(group)):
            if isinstance(item, dict):
                objects.append(str(item.get("id") or item.get("role") or group))
    return objects


def anchor_map(editable_layer: dict[str, Any]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for item in as_list(editable_layer.get("body")) + as_list(editable_layer.get("labels")):
        if not isinstance(item, dict):
            continue
        anchor_layer = item.get("anchor_layer") or item.get("anchoring")
        if anchor_layer:
            mapped.append(
                {
                    "editable_object_id": item.get("id") or item.get("role"),
                    "editable_text": item.get("text", ""),
                    "anchor_layer": anchor_layer,
                    "anchor_index": item.get("anchor_index"),
                    "zone": item.get("zone", {}),
                }
            )
    return mapped


def zones_from_composition(composition: dict[str, Any]) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    if isinstance(composition.get("asset_zone"), dict):
        zones.append({"name": "visual substrate zone", "role": "full generated visual logic", "zone": composition["asset_zone"]})
    if isinstance(composition.get("text_safe_zone"), dict):
        zones.append({"name": "editable text-safe zone", "role": "editable title, argument, proof labels, and page number", "zone": composition["text_safe_zone"]})
    return zones


def build_storyboard(page: dict[str, Any], visual_bible: dict[str, Any], source_excerpt: str = "") -> dict[str, Any]:
    editable_layer = as_dict(page.get("editable_layer"))
    composition = as_dict(page.get("composition_plan"))
    generated = [item for item in as_list(page.get("generated_layer")) if isinstance(item, dict)]
    primary_asset = generated[0] if generated else {}
    anchors = anchor_map(editable_layer)
    do_not_use = list(as_list(visual_bible.get("do_not_use")))
    do_not_use.extend(
        [
            "adjacent left-text/right-image composition",
            "blank disconnected text zone",
            "decorative background without argument structure",
            "text baked into generated image",
        ]
    )

    title = str(page.get("title") or "")
    visual_idea = str(page.get("visual_idea") or "")
    main_action = (
        "A full-slide generated substrate turns mature-root foundation strata into visible evidence-anchor lines that extend into editable proof labels, "
        "then rises into a new platform structure."
    )
    if "anchor" not in visual_idea.lower() and primary_asset.get("visual_role"):
        main_action = str(primary_asset.get("visual_role"))

    return {
        "slide_number": page.get("slide_number"),
        "title": title,
        "page_function": page.get("page_function", ""),
        "storyboard_version": "v1",
        "first_impression": "A full-slide editorial substrate, not a split layout: the viewer first sees mature layered roots/foundation generating a new platform architecture.",
        "second_impression": "Subtle low-contrast strata/root lines travel into the editable text area, making the left-side proof points feel attached to the visual system.",
        "third_impression": "The four proof points can be read as evidence labels for four capability layers rather than as a separate bullet list.",
        "main_visual_action": main_action,
        "visual_tension": "The page tension comes from a mature, grounded operating base producing a precise upward platform system while evidence lines pull that logic into editable text.",
        "reading_path": [
            f"Read the editable title: {title}",
            "See the right-side mature foundation and platform-generation structure.",
            "Follow the subtle evidence-anchor lines into the left editable proof labels.",
            "Resolve the argument: the new company is generated from mature roots, not starting from zero.",
        ],
        "text_image_relationship": {
            "relationship_type": "interlocked",
            "description": "Editable text behaves as evidence labels attached to generated strata/root anchor lines. The image supplies the visual logic and the PowerPoint text remains editable.",
            "must_not_be": [
                "left-side text plus right-side illustration",
                "detached background behind ordinary bullets",
                "text baked into the generated asset",
            ],
        },
        "editable_text_strategy": {
            "editable_objects": editable_objects(editable_layer),
            "placement_logic": "Title and main argument establish claim hierarchy; proof points sit on or near evidence lanes extending from the generated substrate.",
            "why_text_remains_editable": "Strategic claim text, page number, and proof labels must remain PowerPoint text for later human revisions and client-side editing.",
        },
        "asset_role": {
            "asset_type": primary_asset.get("asset_type", ""),
            "structural_role": primary_asset.get("visual_role", ""),
            "what_breaks_if_removed": "The mature-root/platform-generation structure and the evidence-anchor logic disappear, leaving only editable labels without visual proof.",
        },
        "anchor_strategy": {
            "required": True,
            "anchor_count": len(anchors),
            "anchor_logic": "Each editable proof point aligns to one subtle generated strata/root line so text and image become one argument structure.",
            "anchor_to_editable_text_map": anchors,
        },
        "negative_space_strategy": "Left-side negative space must remain warm, low-detail, and readable while still carrying faint anchor-line logic. It is not a blank reserved column.",
        "composition_sketch": {
            "plain_language": "Full-slide generated substrate. Right side carries layered mature foundation and upward platform generation. Four quiet anchor lines extend left into editable evidence labels. Title and main claim sit above the evidence lanes.",
            "zones": zones_from_composition(composition),
            "layer_order": [
                "full-slide generated substrate",
                "editable title and page number",
                "editable main argument",
                "editable evidence labels aligned to anchor lanes",
                "minimal native support ticks/rules only if needed",
            ],
        },
        "prompt_implications": [
            "Generate the full-slide visual logic, including low-contrast anchor lines, not a right-side illustration.",
            "Keep the left text area readable but visually connected.",
            "Do not include text, labels, icons, endpoints, badges, title, or page number in the image.",
            "Make the asset structural enough that deleting it removes the page's argument map.",
        ],
        "visual_qa_expectations": [
            "text and image are interlocked",
            "asset is structural, not decorative",
            "editable text remains editable",
        ],
        "do_not_use": do_not_use,
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
    parser.add_argument("--out", required=True, help="Output designer_storyboard.json path.")
    args = parser.parse_args()

    page = load_json(Path(args.page_decomposition))
    visual_bible = load_json(Path(args.visual_bible))
    storyboard = build_storyboard(page, visual_bible, args.source_excerpt)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(storyboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Designer storyboard: {out}")
    print(f"approved: {storyboard['approved']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
