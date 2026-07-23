#!/usr/bin/env python3
"""Generate asset prompt manifests from generated/sourced asset layers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FIXTURE_TERMS: tuple[str, ...] = ()

DEFAULT_VISUAL_BANS = (
    "no text, captions, labels, title, page number, body copy, or fake UI text inside the image",
    "no logos, QR codes, watermarks, fake brand marks, or unapproved product packaging",
    "no unapproved people, sensitive subject matter, or project-specific iconography not present in the brief",
    "no unreviewed claims, unsupported data panels, or invented factual statements",
    "no Office SmartArt, default arrows, card stacks, container shadows, drop shadows, or fake depth",
)
GENERIC_DESIGN_INTENT_PLACEHOLDERS = (
    "Turn the page argument into an integrated visual structure.",
    "Project-specific metaphor to be derived",
    "A project-specific metaphor is required",
)


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def zone_ratio(zone: dict[str, Any]) -> str:
    try:
        w = float(zone.get("w"))
        h = float(zone.get("h"))
    except Exception:
        return "unspecified"
    if h <= 0:
        return "unspecified"
    return f"{w / h:.2f}:1 zone ratio"


def asset_id(asset: dict[str, Any], slide_number: Any, idx: int) -> str:
    return str(asset.get("asset_id") or asset.get("id") or f"slide_{slide_number}_asset_{idx}")


def asset_filename(asset: dict[str, Any], slide_number: Any, idx: int) -> str:
    return str(asset.get("filename") or f"{asset_id(asset, slide_number, idx)}.png")


def visual_bible_prompt_base(data: dict[str, Any]) -> str:
    bible = data.get("visual_bible", {})
    if not isinstance(bible, dict):
        return ""
    kit = bible.get("asset_prompt_kit", {})
    parts = [
        bible.get("asset_prompt_base", ""),
        bible.get("style_direction", ""),
        kit.get("shared_rendering_language", "") if isinstance(kit, dict) else "",
        kit.get("negative_prompt", "") if isinstance(kit, dict) else "",
    ]
    return " ".join(str(part) for part in parts if part).strip()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def resolve_storyboard(slide: dict[str, Any], project_dir: Path | None) -> dict[str, Any]:
    inline = slide.get("designer_storyboard")
    if isinstance(inline, dict):
        return inline
    ref = str(slide.get("storyboard_ref") or "").strip()
    if not ref:
        return {}
    path = Path(ref)
    if not path.is_absolute() and project_dir:
        path = project_dir / path
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_design_intent(slide: dict[str, Any], project_dir: Path | None) -> dict[str, Any]:
    inline = slide.get("design_intent")
    if isinstance(inline, dict):
        return inline
    ref = str(slide.get("design_intent_ref") or "").strip()
    if not ref:
        return {}
    path = Path(ref)
    if not path.is_absolute() and project_dir:
        path = project_dir / path
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def join_list(value: Any) -> str:
    items = [str(item).strip() for item in as_list(value) if str(item).strip()]
    return "; ".join(items)


def scrub_fixture_terms(text: str) -> str:
    cleaned = text
    for term in FIXTURE_TERMS:
        cleaned = cleaned.replace(term, "")
    return " ".join(cleaned.split())


def concise_do_not_use(intent: dict[str, Any], data: dict[str, Any]) -> list[str]:
    raw = as_list(intent.get("do_not_do"))
    raw.extend(as_list(as_dict(data.get("visual_bible")).get("do_not_use")))
    keep_terms = (
        "drug", "pack", "logo", "medical", "efficacy", "claim", "patient", "doctor",
        "lung", "DNA", "UI", "microcopy", "QR", "SmartArt", "flowchart", "arrow",
        "card", "shadow", "text", "title", "page number", "body copy", "data",
        "packaging", "microscope", "eye", "table", "流程", "表格", "卡片", "阴影",
        "药盒", "医生", "患者", "肺", "疗效", "声明", "二维码", "文字", "标题", "页码",
    )
    result: list[str] = []
    for item in raw:
        text = scrub_fixture_terms(str(item).strip())
        if not text:
            continue
        if any(term.lower() in text.lower() for term in keep_terms) and text not in result:
            result.append(text)
    compact = list(DEFAULT_VISUAL_BANS)
    for item in result:
        lower = item.lower()
        if not any(lower in existing.lower() or existing.lower() in lower for existing in compact):
            compact.append(item)
        if len(compact) >= 8:
            break
    return compact


def storyboard_prompt_block(storyboard: dict[str, Any]) -> str:
    if not storyboard:
        return ""
    relationship = as_dict(storyboard.get("text_image_relationship"))
    anchor = as_dict(storyboard.get("anchor_strategy"))
    sketch = as_dict(storyboard.get("composition_sketch"))
    parts = [
        "Designer Storyboard source:",
        f"First impression: {storyboard.get('first_impression', '')}",
        f"Main visual action: {storyboard.get('main_visual_action', '')}",
        f"Text-image relationship: {relationship.get('relationship_type', '')} - {relationship.get('description', '')}",
        f"Anchor strategy: {anchor.get('anchor_logic', '')}; anchor map: {json.dumps(anchor.get('anchor_to_editable_text_map', []), ensure_ascii=False)}",
        f"Negative space strategy: {storyboard.get('negative_space_strategy', '')}",
        f"Composition sketch: {sketch.get('plain_language', '')}; zones: {json.dumps(sketch.get('zones', []), ensure_ascii=False)}; layer order: {join_list(sketch.get('layer_order'))}",
        f"Prompt implications: {join_list(storyboard.get('prompt_implications'))}",
        f"Do not use: {join_list(storyboard.get('do_not_use'))}",
    ]
    return "\n".join(part for part in parts if str(part).strip())


def design_intent_prompt_block(intent: dict[str, Any]) -> str:
    if not intent:
        return ""
    relationship = as_dict(intent.get("text_image_relationship"))
    asset_intent = as_dict(intent.get("asset_intent"))
    layout_intent = as_dict(intent.get("layout_intent"))
    editable_strategy = as_dict(intent.get("editable_strategy"))
    rejected = []
    for item in as_list(intent.get("rejected_directions")):
        if isinstance(item, dict) and item.get("direction") and item.get("reason"):
            rejected.append(f"{item['direction']}: {item['reason']}")
    parts = [
        "Design Intent:",
        f"Design problem: {intent.get('design_problem', '')}",
        f"Desired perception: {intent.get('desired_perception', '')}",
        f"Core design argument: {intent.get('core_design_argument', '')}",
        f"Main visual move: {intent.get('main_visual_move', '')}",
        f"Visual metaphor: {intent.get('visual_metaphor', '')}",
        f"Why this works: {intent.get('why_this_works', '')}",
        f"Text-image relationship: {relationship.get('relationship_type', '')} - {relationship.get('description', '')}",
        f"Editable strategy: {editable_strategy.get('how_editable_text_participates_in_visual', '')}",
        f"Asset intent: {asset_intent.get('visual_job', '')} It must prove: {asset_intent.get('what_it_must_prove', '')}",
        f"Layout intent: {layout_intent.get('composition_logic', '')} Negative space: {layout_intent.get('negative_space_logic', '')} Hierarchy: {layout_intent.get('visual_hierarchy', '')}",
        f"Rejected directions: {join_list(rejected)}",
        f"Do not do: {join_list(intent.get('do_not_do'))}",
        f"Prompt brief: {intent.get('prompt_brief', '')}",
    ]
    return "\n".join(part for part in parts if str(part).strip())


def concise_design_intent_prompt(
    *,
    intent: dict[str, Any],
    data: dict[str, Any],
    asset: dict[str, Any],
    slide: dict[str, Any],
    expected_zone: dict[str, Any],
    text_allowed: bool,
    logo_allowed: bool,
    exact_cn: bool,
    transparency: bool,
) -> str:
    relationship = as_dict(intent.get("text_image_relationship"))
    editable_strategy = as_dict(intent.get("editable_strategy"))
    asset_intent = as_dict(intent.get("asset_intent"))
    layout_intent = as_dict(intent.get("layout_intent"))
    main_move = scrub_fixture_terms(str(intent.get("main_visual_move") or "").strip())
    metaphor = scrub_fixture_terms(str(intent.get("visual_metaphor") or "").strip())
    relationship_text = scrub_fixture_terms(str(relationship.get("description") or "").strip())
    editable_text = scrub_fixture_terms(str(editable_strategy.get("how_editable_text_participates_in_visual") or "").strip())
    visual_job = scrub_fixture_terms(str(asset_intent.get("visual_job") or asset.get("visual_role") or "").strip())
    composition = scrub_fixture_terms(str(layout_intent.get("composition_logic") or "").strip())
    negative_space = scrub_fixture_terms(str(layout_intent.get("negative_space_logic") or "").strip())
    bans = concise_do_not_use(intent, data)
    ratio = zone_ratio(expected_zone) if isinstance(expected_zone, dict) else "16:9"
    text_policy = "No text of any kind inside the image." if not text_allowed else "Only approved short visual text may appear."
    logo_policy = "No logos or brand marks." if not logo_allowed else "Only supplied, approved logos may appear."
    exact_policy = "Do not attempt exact Chinese text." if not exact_cn else "If Chinese text is explicitly required, preserve it exactly."
    transparency_policy = "Use transparent isolated asset treatment." if transparency else "Use a full-slide integrated visual substrate."
    prompt = f"""Create a 16:9 high-design medical launch proposal visual substrate.

Main visual move: {main_move}
Visual metaphor: {metaphor}

Build the image as an abstract, premium editorial medical proposal field, not a product ad or clinical data claim. The asset's job is: {visual_job}

Text-image relationship: {relationship_text}
Editable PowerPoint text will be placed separately; keep readable low-interference zones where the editable claim, reasoning, keywords, or execution nodes can visually participate in the structure. {editable_text}

Composition: {composition}
Negative space: {negative_space}
Target framing: full-slide {ratio}, no measurement marks.

{text_policy} {logo_policy} {exact_policy} {transparency_policy}
Avoid: {join_list(bans)}."""
    return scrub_fixture_terms(prompt)


def prompt_for_generated_asset(asset: dict[str, Any], data: dict[str, Any], slide: dict[str, Any], idx: int, project_dir: Path | None) -> dict[str, Any]:
    composition = slide.get("composition_plan", {}) if isinstance(slide.get("composition_plan"), dict) else {}
    expected_zone = asset.get("expected_zone") or composition.get("asset_zone") or {}
    base = visual_bible_prompt_base(data)
    role = str(asset.get("visual_role") or "").strip()
    asset_type = str(asset.get("asset_type") or "visual_asset")
    integration = str(asset.get("integration_with_editable_layer") or composition.get("integration_logic") or "").strip()
    prompt_draft = str(asset.get("prompt_draft") or asset.get("prompt") or "").strip()
    transparency = bool(asset.get("transparency_required"))
    text_allowed = bool(asset.get("text_allowed"))
    logo_allowed = bool(asset.get("logo_allowed"))
    exact_cn = bool(asset.get("exact_cn_text_required"))
    production_prompt = str(asset.get("production_prompt") or "").strip()
    design_intent = resolve_design_intent(slide, project_dir)
    if slide.get("page_mode") in {"hybrid_native", "full_image"}:
        if not design_intent:
            raise SystemExit(f"Slide {slide.get('slide_number')}: design_intent or design_intent_ref is required before asset prompt generation")
        if design_intent.get("approved") is not True and design_intent.get("approval", {}).get("approved") is not True:
            raise SystemExit(f"Slide {slide.get('slide_number')}: design_intent.approval.approved must be true before asset prompt generation")
        design_text = json.dumps(design_intent, ensure_ascii=False).lower()
        for phrase in GENERIC_DESIGN_INTENT_PLACEHOLDERS:
            if phrase.lower() in design_text:
                raise SystemExit(f"Slide {slide.get('slide_number')}: design_intent contains generic placeholder phrase: {phrase}")
    design_intent_block = design_intent_prompt_block(design_intent)
    storyboard = resolve_storyboard(slide, project_dir)
    storyboard_block = storyboard_prompt_block(storyboard)

    if design_intent_block:
        prompt = concise_design_intent_prompt(
            intent=design_intent,
            data=data,
            asset=asset,
            slide=slide,
            expected_zone=expected_zone,
            text_allowed=text_allowed,
            logo_allowed=logo_allowed,
            exact_cn=exact_cn,
            transparency=transparency,
        )
    elif storyboard_block:
        prompt = (
            f"Create one high-design PPT proposal visual asset based on the legacy Designer Storyboard, not by mechanically combining style words.\n"
            f"Slide number: {slide.get('slide_number')}.\n"
            f"Asset id: {asset_id(asset, slide.get('slide_number'), idx)}.\n"
            f"Asset type: {asset_type}.\n\n"
            f"{storyboard_block}\n\n"
            f"Page decomposition asset role: {role}.\n"
            f"Integration with editable PowerPoint layer: {integration}.\n"
            f"Visual Bible / style base: {base or 'use the locked project Visual Bible'}.\n"
            f"Target zone: {expected_zone}; approximate ratio: {zone_ratio(expected_zone) if isinstance(expected_zone, dict) else 'unspecified'}.\n"
            f"Text policy: {'text is allowed only as explicitly specified' if text_allowed else 'do not include any text, including slide title, page number, labels, captions, fake UI text, or body copy'}.\n"
            f"Logo policy: {'logos are allowed only if supplied and legally approved' if logo_allowed else 'do not include logos, fake brand marks, QR codes, or watermarks'}.\n"
            f"Transparency policy: {'transparent background / isolated PNG asset required' if transparency else 'background may be integrated within the asset zone'}.\n"
            f"Exact Chinese text policy: {'exact Chinese text is required; do not alter characters' if exact_cn else 'do not attempt exact Chinese text inside the image'}.\n"
            f"The visual must satisfy the storyboard's text-image relationship and anchor strategy. It must be structural, not decorative."
        )
    elif production_prompt:
        prompt = production_prompt
    else:
        prompt = (
            f"Create one PPT proposal visual asset.\n"
            f"Slide number: {slide.get('slide_number')}.\n"
            f"Asset id: {asset_id(asset, slide.get('slide_number'), idx)}.\n"
            f"Asset type: {asset_type}.\n"
            f"Expression role on the page: {role}.\n"
            f"Visual Bible / style base: {base or 'use the locked project Visual Bible'}.\n"
            f"Page-specific draft direction: {prompt_draft or 'use the declared visual role and Visual Bible without adding text or logos'}.\n"
            f"Target zone: {expected_zone}; approximate ratio: {zone_ratio(expected_zone) if isinstance(expected_zone, dict) else 'unspecified'}.\n"
            f"Integration with editable PowerPoint layer: {integration}.\n"
            f"Text policy: {'text is allowed only as explicitly specified' if text_allowed else 'do not include any text, including slide title, page number, labels, captions, fake UI text, or body copy'}.\n"
            f"Logo policy: {'logos are allowed only if supplied and legally approved' if logo_allowed else 'do not include logos, fake brand marks, QR codes, or watermarks'}.\n"
            f"Transparency policy: {'transparent background / isolated PNG asset required' if transparency else 'background may be integrated within the asset zone'}.\n"
            f"Exact Chinese text policy: {'exact Chinese text is required; do not alter characters' if exact_cn else 'do not attempt exact Chinese text inside the image'}.\n"
            f"Do not make this a generic background. The asset must carry the declared expression role."
        )
    return {
        "id": asset_id(asset, slide.get("slide_number"), idx),
        "slide_number": slide.get("slide_number"),
        "kind": "generated_asset",
        "asset_type": asset_type,
        "visual_role": role,
        "filename": asset_filename(asset, slide.get("slide_number"), idx),
        "expected_zone": expected_zone,
        "transparency_required": transparency,
        "text_allowed": text_allowed,
        "logo_allowed": logo_allowed,
        "exact_cn_text_required": exact_cn,
        "prompt": prompt,
    }


def manifest_for_sourced_asset(asset: dict[str, Any], slide: dict[str, Any], idx: int) -> dict[str, Any]:
    composition = slide.get("composition_plan", {}) if isinstance(slide.get("composition_plan"), dict) else {}
    expected_zone = asset.get("expected_zone") or composition.get("asset_zone") or {}
    return {
        "id": asset_id(asset, slide.get("slide_number"), idx),
        "slide_number": slide.get("slide_number"),
        "kind": "sourced_asset",
        "asset_type": asset.get("asset_type") or "sourced_asset",
        "visual_role": asset.get("visual_role") or "",
        "filename": asset_filename(asset, slide.get("slide_number"), idx),
        "expected_zone": expected_zone,
        "source": asset.get("source") or asset.get("path") or "",
        "prompt": "Sourced asset: no image generation prompt. Register a real file that satisfies the declared visual_role and expected_zone.",
    }


def build_manifest(data: dict[str, Any], project_dir: Path | None = None) -> dict[str, Any]:
    prompts: list[dict[str, Any]] = []
    for slide in data.get("slides", []) or []:
        if not isinstance(slide, dict):
            continue
        for idx, asset in enumerate(as_list(slide.get("generated_layer")), start=1):
            if isinstance(asset, dict):
                prompts.append(prompt_for_generated_asset(asset, data, slide, idx, project_dir))
        for idx, asset in enumerate(as_list(slide.get("sourced_asset_layer")), start=1):
            if isinstance(asset, dict):
                prompts.append(manifest_for_sourced_asset(asset, slide, idx))
    return {"prompts": prompts}


def write_markdown(manifest: dict[str, Any], path: Path) -> None:
    lines = ["# Asset Prompts", ""]
    for idx, item in enumerate(manifest["prompts"], start=1):
        lines.append(f"## {idx}. {item['id']}")
        lines.append("")
        lines.append(f"- Slide: {item.get('slide_number')}")
        lines.append(f"- Kind: {item.get('kind')}")
        lines.append(f"- Asset type: {item.get('asset_type')}")
        lines.append(f"- Filename: `{item.get('filename')}`")
        lines.append(f"- Visual role: {item.get('visual_role')}")
        lines.append(f"- Expected zone: `{item.get('expected_zone')}`")
        lines.append("")
        lines.append(item["prompt"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blueprint", help="Path to blueprint JSON.")
    parser.add_argument("--project-dir", help="Project folder. Defaults to blueprint parent.")
    args = parser.parse_args()

    blueprint = Path(args.blueprint).resolve()
    project_dir = Path(args.project_dir).resolve() if args.project_dir else blueprint.parent
    prompts_dir = project_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(blueprint.read_text(encoding="utf-8"))
    manifest = build_manifest(data, project_dir)
    json_path = prompts_dir / "asset_prompts.json"
    md_path = prompts_dir / "asset_prompts.md"
    json_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(manifest, md_path)
    print(f"Prompts: {len(manifest['prompts'])}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
