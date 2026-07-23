#!/usr/bin/env python3
"""Validate a PPT Native Composer deck blueprint JSON file."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


PAGE_MODES = {"full_image", "hybrid_native", "template_native"}
ASSET_REQUIRED_MODES = {"full_image", "hybrid_native"}
VALIDATION_MODES = {"draft", "assembly", "deliverable"}
READY_STATUSES = {"ready", "registered", "exists", "source_ready", "approved"}
NOT_READY_STATUSES = {"", "pending", "missing", "placeholder", "invalid", "invalid_transparency", "draft"}
OOXML_EFFECT_TAGS = ("outerShdw", "innerShdw", "effectDag")
DESIGN_INTENT_REQUIRED_MODES = {"full_image", "hybrid_native"}
EDITABLE_VISUAL_COMPOSITION_REQUIRED_MODES = {"full_image", "hybrid_native"}
STORYBOARD_REQUIRED_MODES = {"full_image", "hybrid_native"}
DESIGN_INTENT_QA_REQUIRED = (
    "design intent is visible",
    "text participates in visual logic",
    "asset is structural, not decorative",
    "editable text remains editable",
)
STORYBOARD_QA_REQUIRED = (
    "text and image are interlocked",
    "asset is structural, not decorative",
    "editable text remains editable",
)
EDITABLE_VISUAL_COMPOSITION_BAD_PATTERNS = (
    "plain bullet list",
    "left text block plus right image",
    "ordinary paragraph stack",
    "horizontal keyword row",
    "card stack",
    "shadow container",
    "generated substrate plus overlay text stack",
    "generated image plus text overlay without relationship",
)
GENERIC_DESIGN_INTENT_PLACEHOLDERS = (
    "Turn the page argument into an integrated visual structure.",
    "Project-specific metaphor to be derived",
    "A project-specific metaphor is required",
)
ROUTE_REQUIRED_MODES = {"assembly", "deliverable"}
ROUTES_REQUIRING_ARCHETYPE = {"element_asset_hybrid", "template_native_plus_skin", "full_substrate_hybrid", "visual_reference_mode"}
RELATIONSHIP_MAP_REQUIREMENTS = {
    "near_focus": "focus_point",
    "along_axis": "primary_axis",
    "floating_in_quiet_field": "quiet_fields",
    "on_path": "path_points",
}
TYPE_SCALE_REQUIRED = ("display", "title", "claim", "section", "body", "label", "caption", "page_number")
TYPE_SCALE_FIELDS = ("cjk_size_pt", "latin_size_pt", "weight", "line_height", "min_contrast")
CANONICAL_WEIGHT_TOKENS = {"bold", "semibold", "medium", "regular", "light"}
STYLE_ONLY_MOVES = {"科技感", "高级感", "生命科学感", "现代感", "大气", "高端", "premium", "modern", "tech", "technology feel"}
ACTION_MARKERS = (
    "托起",
    "承接",
    "生成",
    "嵌入",
    "锚定",
    "连接",
    "延展",
    "穿透",
    "支撑",
    "对照",
    "浮现",
    "转化",
    "rises",
    "anchors",
    "supports",
    "generates",
    "extends",
    "connects",
    "lifts",
    "carries",
)

TOP_LEVEL_REQUIRED = (
    "final_script_source",
    "deck_brief",
    "visual_bible",
    "page_family_map",
    "asset_generation_policy",
    "editability_policy",
    "validation_policy",
    "font_plan",
    "slides",
)

SLIDE_REQUIRED = (
    "slide_number",
    "title",
    "page_function",
    "page_mode",
    "core_message",
    "audience_takeaway",
    "visual_idea",
    "composition_plan",
    "editable_layer",
    "generated_layer",
    "sourced_asset_layer",
    "native_graphic_layer",
    "visual_text_layer",
    "validation_checks",
)


def textish(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts: list[str] = []
        for key in (
            "id",
            "text",
            "role",
            "visual_role",
            "prompt",
            "reason",
            "reason_required",
            "purpose",
            "asset_type",
            "object_type",
        ):
            item = value.get(key)
            if isinstance(item, str):
                parts.append(item)
        return " ".join(parts)
    return str(value)


def norm(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def is_true(value: Any) -> bool:
    return value is True


def asset_id(asset: dict[str, Any]) -> str:
    return str(asset.get("asset_id") or asset.get("id") or asset.get("name") or "asset")


def asset_status(asset: dict[str, Any]) -> str:
    return str(asset.get("status") or asset.get("slot_status") or "").strip().lower()


def asset_path(asset: dict[str, Any], project_dir: Path | None) -> Path | None:
    raw = asset.get("path") or asset.get("filename")
    if not raw:
        return None
    path = Path(str(raw))
    if path.is_absolute():
        return path
    if project_dir:
        return project_dir / "assets" / path
    return None


def asset_is_ready(asset: dict[str, Any], project_dir: Path | None) -> bool:
    status = asset_status(asset)
    if status in READY_STATUSES:
        return True
    if status in NOT_READY_STATUSES:
        return False
    path = asset_path(asset, project_dir)
    return bool(path and path.exists())


def load_json_ref(ref: str, project_dir: Path | None) -> dict[str, Any]:
    path = Path(ref)
    if not path.is_absolute() and project_dir:
        path = project_dir / path
    if not path.exists():
        return {"__load_error": f"ref does not exist: {path}"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"__load_error": f"could not read ref {path}: {exc}"}
    return payload if isinstance(payload, dict) else {"__load_error": f"ref must contain an object: {path}"}


def load_storyboard(slide: dict[str, Any], project_dir: Path | None) -> dict[str, Any]:
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
        return {"__load_error": f"storyboard_ref does not exist: {path}"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"__load_error": f"could not read storyboard_ref {path}: {exc}"}
    return payload if isinstance(payload, dict) else {"__load_error": f"storyboard_ref must contain an object: {path}"}


def load_design_intent(slide: dict[str, Any], project_dir: Path | None) -> dict[str, Any]:
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
        return {"__load_error": f"design_intent_ref does not exist: {path}"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"__load_error": f"could not read design_intent_ref {path}: {exc}"}
    return payload if isinstance(payload, dict) else {"__load_error": f"design_intent_ref must contain an object: {path}"}


def load_route_object(source: dict[str, Any], slide_number: int, project_dir: Path | None) -> dict[str, Any]:
    inline = source.get("page_production_route")
    if isinstance(inline, dict):
        if isinstance(inline.get("routes"), list):
            for route in inline.get("routes") or []:
                if isinstance(route, dict) and route.get("slide_number") == slide_number:
                    return route
        return inline
    ref = str(source.get("page_production_route_ref") or "").strip()
    if ref:
        payload = load_json_ref(ref, project_dir)
        if payload.get("__load_error"):
            return payload
        if isinstance(payload.get("routes"), list):
            for route in payload.get("routes") or []:
                if isinstance(route, dict) and route.get("slide_number") == slide_number:
                    return route
            return {"__load_error": f"page_production_route_ref has no route for slide {slide_number}"}
        return payload
    return {}


def load_composition_archetype_object(source: dict[str, Any], slide_number: int, project_dir: Path | None) -> dict[str, Any]:
    inline = source.get("composition_archetype")
    if isinstance(inline, dict):
        for key in ("archetypes", "items"):
            if isinstance(inline.get(key), list):
                for item in inline.get(key) or []:
                    if isinstance(item, dict) and item.get("slide_number") == slide_number:
                        return item
        return inline
    ref = str(source.get("composition_archetype_ref") or "").strip()
    if ref:
        payload = load_json_ref(ref, project_dir)
        if payload.get("__load_error"):
            return payload
        for key in ("archetypes", "items"):
            if isinstance(payload.get(key), list):
                for item in payload.get(key) or []:
                    if isinstance(item, dict) and item.get("slide_number") == slide_number:
                        return item
                return {"__load_error": f"composition_archetype_ref has no archetype for slide {slide_number}"}
        return payload
    return {}


def load_editable_visual_composition(slide: dict[str, Any], project_dir: Path | None) -> dict[str, Any]:
    inline = slide.get("editable_visual_composition")
    if isinstance(inline, dict):
        return inline
    ref = str(slide.get("editable_visual_composition_ref") or "").strip()
    if not ref:
        return {}
    path = Path(ref)
    if not path.is_absolute() and project_dir:
        path = project_dir / path
    if not path.exists():
        return {"__load_error": f"editable_visual_composition_ref does not exist: {path}"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"__load_error": f"could not read editable_visual_composition_ref {path}: {exc}"}
    return payload if isinstance(payload, dict) else {"__load_error": f"editable_visual_composition_ref must contain an object: {path}"}


def editable_item_ok(item: Any) -> bool:
    if isinstance(item, dict):
        return item.get("editable") is True
    return False


def editable_layer_has_text(editable_layer: dict[str, Any]) -> bool:
    items: list[Any] = []
    for field in ("title", "page_number"):
        if field in editable_layer:
            items.append(editable_layer.get(field))
    for field in ("body", "labels", "data", "table_text", "notes"):
        items.extend(as_list(editable_layer.get(field)))
    return any(isinstance(item, dict) and item.get("editable") is True and str(item.get("text") or "").strip() for item in items)


def editable_source_items(editable_layer: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    candidates: list[Any] = []
    for field in ("title", "page_number"):
        if field in editable_layer:
            candidates.append(editable_layer.get(field))
    for field in ("body", "labels", "data", "table_text", "notes"):
        candidates.extend(as_list(editable_layer.get(field)))
    for idx, item in enumerate(candidates, start=1):
        if not isinstance(item, dict) or item.get("editable") is not True:
            continue
        item_id = str(item.get("id") or "").strip()
        text = str(item.get("text") or "")
        if item_id and text.strip():
            result[item_id] = item
    return result


def generated_asset_mentions_forbidden_text(slide: dict[str, Any], asset: dict[str, Any]) -> str | None:
    title = norm(slide.get("title"))
    raw_haystack = " ".join(str(asset.get(k, "")) for k in ("visual_role", "prompt", "asset_type", "text", "role"))
    lowered = raw_haystack.lower()
    haystack = norm(raw_haystack)
    negative_title_policy = re.search(r"\b(do not|don't|without|no|禁止|不要|不得)\b[^.。;；]*(slide\s+title|page\s+title|title|标题|页标题)", lowered)
    negative_page_number_policy = re.search(r"\b(do not|don't|without|no|禁止|不要|不得)\b[^.。;；]*(page\s+number|slide\s+number|页码|页数)", lowered)

    title_command = re.search(r"\b(include|carry|render|bake|contain|show|place|add|承载|生成|包含|放入|写入)\b[^.。;；]*(slide\s+title|page\s+title|title|标题|页标题)", lowered)
    page_number_command = re.search(r"\b(include|carry|render|bake|contain|show|place|add|承载|生成|包含|放入|写入)\b[^.。;；]*(page\s+number|slide\s+number|页码|页数)", lowered)

    if title_command and not negative_title_policy:
        return "title"
    if page_number_command and not negative_page_number_policy:
        return "page_number"
    if title and title in haystack and not negative_title_policy:
        return "title"

    explicit_role = norm(" ".join(str(asset.get(k, "")) for k in ("asset_type", "role", "visual_role")))
    if re.search(r"(^|[_\-\s])(page|slide)?number($|[_\-\s])", explicit_role, flags=re.I):
        return "page_number"
    if "页码" in explicit_role:
        return "page_number"
    return None


def check_required_object(
    obj: dict[str, Any],
    required: tuple[str, ...],
    label: str,
    errors: list[str],
) -> None:
    for field in required:
        if field not in obj:
            errors.append(f"{label}: missing field {field}")


def count_ooxml_effects(pptx_path: Path) -> dict[str, int]:
    counts = {tag: 0 for tag in OOXML_EFFECT_TAGS}
    with zipfile.ZipFile(pptx_path) as archive:
        for name in archive.namelist():
            if not name.startswith("ppt/") or not name.endswith(".xml"):
                continue
            try:
                text = archive.read(name).decode("utf-8", errors="ignore")
            except Exception:
                continue
            for tag in OOXML_EFFECT_TAGS:
                counts[tag] += text.count(tag)
    return counts


def hex_rgb(value: Any) -> tuple[float, float, float] | None:
    text = str(value or "").strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return None
    return tuple(int(text[i : i + 2], 16) / 255 for i in (1, 3, 5))


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(value) for value in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: Any, bg: Any) -> float | None:
    fg_rgb = hex_rgb(fg)
    bg_rgb = hex_rgb(bg)
    if fg_rgb is None or bg_rgb is None:
        return None
    l1 = relative_luminance(fg_rgb)
    l2 = relative_luminance(bg_rgb)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def canonical_colors(data: dict[str, Any]) -> dict[str, str]:
    tokens = as_dict(as_dict(data.get("visual_bible")).get("design_tokens"))
    colors = tokens.get("colors")
    if isinstance(colors, dict):
        return {
            "paper": str(colors.get("paper") or colors.get("background") or "#F7F4EE"),
            "background": str(colors.get("background") or colors.get("paper") or "#F7F4EE"),
            "ink": str(colors.get("ink") or "#111111"),
            "muted": str(colors.get("muted") or "#666666"),
            "accent": str(colors.get("accent") or "#E6422E"),
            "secondary_accent": str(colors.get("secondary_accent") or colors.get("accent") or "#276EF1"),
            "line": str(colors.get("line") or colors.get("grid") or "#CFC7BA"),
        }
    return {}


def validate_visual_bible(data: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    visual_bible = data.get("visual_bible")
    if not isinstance(visual_bible, dict):
        errors.append("visual_bible must be an object")
        return

    if not visual_bible:
        errors.append("visual_bible must not be empty")
        return

    if not (visual_bible.get("asset_prompt_base") or visual_bible.get("asset_prompt_kit")):
        warnings.append("visual_bible should include asset_prompt_base or asset_prompt_kit for generated assets")

    do_not_use = [str(item).lower() for item in as_list(visual_bible.get("do_not_use"))]
    required_bans = ("shadow", "card", "fake depth")
    if do_not_use and not all(any(term in item for item in do_not_use) for term in required_bans):
        warnings.append("visual_bible.do_not_use should include shadow/card/fake-depth prohibitions")

    tokens = as_dict(visual_bible.get("design_tokens"))
    colors = tokens.get("colors")
    if isinstance(colors, list):
        errors.append("visual_bible.design_tokens.colors must be a canonical object, not a legacy list")
    elif isinstance(colors, dict):
        for field in ("paper", "background", "ink", "muted", "accent", "line"):
            if not str(colors.get(field) or "").strip():
                errors.append(f"visual_bible.design_tokens.colors.{field} is required")
        bg = colors.get("background") or colors.get("paper")
        muted_ratio = contrast_ratio(colors.get("muted"), bg)
        if muted_ratio is not None and muted_ratio < 4.5:
            errors.append(f"visual_bible.design_tokens.colors.muted contrast against background must be >= 4.5:1, got {muted_ratio:.2f}")

    font_plan_sources = [
        ("visual_bible.font_plan", as_dict(visual_bible.get("font_plan"))),
        ("font_plan", as_dict(data.get("font_plan"))),
    ]
    for source_label, font_plan in font_plan_sources:
        type_scale = as_dict(font_plan.get("type_scale"))
        if not type_scale:
            continue
        for level in TYPE_SCALE_REQUIRED:
            spec = as_dict(type_scale.get(level))
            if not spec:
                errors.append(f"{source_label}.type_scale.{level} is required when type_scale is used")
                continue
            for field in TYPE_SCALE_FIELDS:
                if field not in spec:
                    errors.append(f"{source_label}.type_scale.{level}.{field} is required")


def validate_deck_policy(data: dict[str, Any], mode: str, errors: list[str], warnings: list[str]) -> None:
    final_source = as_dict(data.get("final_script_source"))
    if mode in {"assembly", "deliverable"} and final_source.get("confirmed") is not True:
        errors.append("final_script_source.confirmed must be true for assembly/deliverable validation")

    editability_policy = as_dict(data.get("editability_policy"))
    if editability_policy:
        if editability_policy.get("title_must_be_editable") is not True:
            errors.append("editability_policy.title_must_be_editable must be true")
        if editability_policy.get("page_number_must_be_editable") is not True:
            errors.append("editability_policy.page_number_must_be_editable must be true")

    validation_policy = as_dict(data.get("validation_policy"))
    if validation_policy:
        for field in ("no_svg_shadow", "no_container_shadow", "no_card_shadow", "no_fake_depth"):
            if validation_policy.get(field) is not True:
                errors.append(f"validation_policy.{field} must be true")


def validate_route_and_archetype(
    data: dict[str, Any],
    slide: dict[str, Any],
    label: str,
    mode: str,
    project_dir: Path | None,
    errors: list[str],
) -> None:
    if mode not in ROUTE_REQUIRED_MODES:
        return
    slide_number = slide.get("slide_number")
    if not isinstance(slide_number, int):
        return

    route = load_route_object(slide, slide_number, project_dir) or load_route_object(data, slide_number, project_dir)
    if not route:
        errors.append(f"{label}: page_production_route or page_production_route_ref is required for {mode} validation")
    elif route.get("__load_error"):
        errors.append(f"{label}: {route['__load_error']}")
    else:
        if not str(route.get("selected_route") or "").strip():
            errors.append(f"{label}: page_production_route.selected_route is required")
        if not str(route.get("composition_archetype_id") or "").strip():
            errors.append(f"{label}: page_production_route.composition_archetype_id is required")
        if route.get("selected_route") in ROUTES_REQUIRING_ARCHETYPE and not str(route.get("composition_archetype_id") or "").strip():
            errors.append(f"{label}: selected_route={route.get('selected_route')} requires composition_archetype_id")
        if as_dict(route.get("approval")).get("approved") is not True:
            errors.append(f"{label}: page_production_route.approval.approved must be true for {mode} validation")

    archetype = load_composition_archetype_object(slide, slide_number, project_dir) or load_composition_archetype_object(data, slide_number, project_dir)
    if not archetype:
        errors.append(f"{label}: composition_archetype or composition_archetype_ref is required for {mode} validation")
    elif archetype.get("__load_error"):
        errors.append(f"{label}: {archetype['__load_error']}")
    else:
        if not str(archetype.get("archetype_id") or "").strip():
            errors.append(f"{label}: composition_archetype.archetype_id is required")
        if as_dict(archetype.get("approval")).get("approved") is not True:
            errors.append(f"{label}: composition_archetype.approval.approved must be true for {mode} validation")


def validate_native_graphics(slide: dict[str, Any], label: str, errors: list[str], warnings: list[str]) -> None:
    layer = as_list(slide.get("native_graphic_layer"))
    shape_count = len(layer)
    round_count = 0
    line_count = 0
    gradient_count = 0
    icon_count = 0
    default_table_count = 0

    for idx, item in enumerate(layer, start=1):
        if not isinstance(item, dict):
            errors.append(f"{label}: native_graphic_layer[{idx}] must be an object")
            continue
        if not str(item.get("reason_required") or "").strip():
            errors.append(f"{label}: native_graphic_layer[{idx}] missing reason_required")
        if item.get("must_not_be_decorative") is not True:
            errors.append(f"{label}: native_graphic_layer[{idx}].must_not_be_decorative must be true")

        text = textish(item).lower()
        structural_text = " ".join(
            str(item.get(key) or "")
            for key in ("object_type", "style", "preset", "shape_type")
        ).lower()
        object_type = str(item.get("object_type") or "").lower()
        if "round" in structural_text or "rounded" in structural_text or "card" in structural_text or "container" in structural_text:
            round_count += 1
        if "line" in object_type or "connector" in object_type or "rule" in text:
            line_count += 1
        if "gradient" in text:
            gradient_count += 1
        if "icon" in text:
            icon_count += 1
        if "default office table" in text or ("table" in text and "default" in text):
            default_table_count += 1

    if shape_count > 24:
        warnings.append(f"{label}: native_graphic_layer has {shape_count} items; risk of native-shape/SVG-like page")
    if round_count > 4:
        warnings.append(f"{label}: many rounded/card/container objects detected ({round_count})")
    if line_count > 18:
        warnings.append(f"{label}: many line/rule objects detected ({line_count})")
    if gradient_count > 0:
        warnings.append(f"{label}: gradient usage detected; verify it is not fake depth")
    if icon_count > 8:
        warnings.append(f"{label}: many icon objects detected ({icon_count})")
    if default_table_count > 0:
        warnings.append(f"{label}: suspected default Office table styling")


def validate_designer_storyboard(
    slide: dict[str, Any],
    label: str,
    page_mode: Any,
    project_dir: Path | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    if page_mode not in STORYBOARD_REQUIRED_MODES:
        return

    storyboard = load_storyboard(slide, project_dir)
    if not storyboard:
        errors.append(f"{label}: {page_mode} requires designer_storyboard or storyboard_ref")
        return
    if storyboard.get("__load_error"):
        errors.append(f"{label}: {storyboard['__load_error']}")
        return

    main_visual_action = str(storyboard.get("main_visual_action") or "").strip()
    if not main_visual_action:
        errors.append(f"{label}: designer_storyboard.main_visual_action is required")

    relationship = as_dict(storyboard.get("text_image_relationship"))
    rel_type = str(relationship.get("relationship_type") or "").strip().lower()
    if not rel_type:
        errors.append(f"{label}: designer_storyboard.text_image_relationship.relationship_type is required")
    elif rel_type == "adjacent":
        errors.append(f"{label}: designer_storyboard.text_image_relationship.relationship_type must not be adjacent")

    asset_role = as_dict(storyboard.get("asset_role"))
    if not str(asset_role.get("what_breaks_if_removed") or "").strip():
        errors.append(f"{label}: designer_storyboard.asset_role.what_breaks_if_removed is required")

    reading_path = as_list(storyboard.get("reading_path"))
    if len([step for step in reading_path if str(step).strip()]) < 3:
        errors.append(f"{label}: designer_storyboard.reading_path must contain at least 3 steps")

    expectations = [str(item).strip().lower() for item in as_list(storyboard.get("visual_qa_expectations"))]
    for required in STORYBOARD_QA_REQUIRED:
        if required not in expectations:
            errors.append(f"{label}: designer_storyboard.visual_qa_expectations must include '{required}'")

    anchor_strategy = as_dict(storyboard.get("anchor_strategy"))
    if anchor_strategy.get("required") is True and not as_list(anchor_strategy.get("anchor_to_editable_text_map")):
        errors.append(f"{label}: designer_storyboard.anchor_strategy.anchor_to_editable_text_map is required when anchor_strategy.required=true")


def main_visual_move_is_action(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    compact = norm(stripped)
    if compact in {norm(item) for item in STYLE_ONLY_MOVES}:
        return False
    if any(marker in stripped for marker in ACTION_MARKERS):
        return True
    if any(marker in lowered for marker in ACTION_MARKERS):
        return True
    if any(style in stripped for style in ("科技感", "高级感", "生命科学感")) and len(stripped) <= 12:
        return False
    return len(stripped) >= 6 and not stripped.endswith(("感", "style", "feel"))


def role_type_scale_key(role: str) -> str:
    lowered = role.lower()
    if "page_number" in lowered:
        return "page_number"
    if "title" in lowered:
        return "title"
    if "claim" in lowered or "main_argument" in lowered or "judgment" in lowered:
        return "claim"
    if "section" in lowered:
        return "section"
    if "caption" in lowered or "note" in lowered:
        return "caption"
    if "label" in lowered or "keyword" in lowered or "argument" in lowered:
        return "label"
    return "body"


def type_scale_defaults() -> dict[str, dict[str, Any]]:
    return {
        "display": {"cjk_size_pt": 30, "latin_size_pt": 30, "weight": "bold", "line_height": 1.08, "min_contrast": 4.5},
        "title": {"cjk_size_pt": 24, "latin_size_pt": 24, "weight": "bold", "line_height": 1.1, "min_contrast": 4.5},
        "claim": {"cjk_size_pt": 14, "latin_size_pt": 14, "weight": "semibold", "line_height": 1.15, "min_contrast": 4.5},
        "section": {"cjk_size_pt": 11, "latin_size_pt": 11, "weight": "semibold", "line_height": 1.15, "min_contrast": 4.5},
        "body": {"cjk_size_pt": 10, "latin_size_pt": 10, "weight": "regular", "line_height": 1.25, "min_contrast": 4.5},
        "label": {"cjk_size_pt": 9, "latin_size_pt": 9, "weight": "medium", "line_height": 1.12, "min_contrast": 4.5},
        "caption": {"cjk_size_pt": 8, "latin_size_pt": 8, "weight": "regular", "line_height": 1.2, "min_contrast": 4.5},
        "page_number": {"cjk_size_pt": 7, "latin_size_pt": 7, "weight": "regular", "line_height": 1.0, "min_contrast": 4.5},
    }


def resolved_type_scale(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scale = type_scale_defaults()
    visual_font_plan = as_dict(as_dict(data.get("visual_bible")).get("font_plan"))
    candidates = [as_dict(visual_font_plan.get("type_scale")), as_dict(as_dict(data.get("font_plan")).get("type_scale"))]
    for candidate in candidates:
        for key, value in candidate.items():
            if key in scale and isinstance(value, dict):
                scale[key] = {**scale[key], **value}
    return scale


def item_type_scale_key(item: dict[str, Any]) -> str:
    treatment = as_dict(item.get("typographic_treatment"))
    explicit = str(treatment.get("type_scale") or treatment.get("scale") or "").strip()
    if explicit:
        return explicit
    return role_type_scale_key(str(item.get("role") or ""))


def resolved_font_spec(item: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    treatment = as_dict(item.get("typographic_treatment"))
    scale = resolved_type_scale(data)
    key = item_type_scale_key(item)
    spec = dict(scale.get(key, scale["body"]))
    for field in ("cjk_size_pt", "latin_size_pt", "weight", "line_height", "min_contrast"):
        if field in treatment:
            spec[field] = treatment[field]
    return spec


def validate_typographic_weight(item: dict[str, Any], prefix: str, errors: list[str], warnings: list[str]) -> None:
    treatment = as_dict(item.get("typographic_treatment"))
    token = str(treatment.get("weight_token") or "").strip().lower()
    natural = str(treatment.get("weight") or "").strip().lower()
    if token and token not in CANONICAL_WEIGHT_TOKENS:
        errors.append(f"{prefix}.typographic_treatment.weight_token must be one of {sorted(CANONICAL_WEIGHT_TOKENS)}")
    if not token and natural and natural not in CANONICAL_WEIGHT_TOKENS:
        warnings.append(f"{prefix}: typographic_treatment.weight uses legacy natural language; migrate to weight_token plus weight_note")


def estimate_text_overflow(item: dict[str, Any], prefix: str, data: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    zone_value = as_dict(item.get("zone"))
    try:
        width = float(zone_value.get("w"))
        height = float(zone_value.get("h"))
    except Exception:
        return
    if width <= 0 or height <= 0:
        return
    text = str(item.get("text") or "")
    spec = resolved_font_spec(item, data)
    size_pt = spec.get("cjk_size_pt") or spec.get("latin_size_pt")
    try:
        size = float(size_pt)
    except Exception:
        size = 10
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_count = len(re.findall(r"[A-Za-z0-9]", text))
    punctuation_count = max(0, len(text) - cjk_count - latin_count)
    estimated_units = cjk_count + latin_count * 0.55 + punctuation_count * 0.45
    chars_per_line = max(1.0, width * 72 / max(size, 1) / 0.95)
    estimated_lines = max(1.0, estimated_units / chars_per_line)
    line_height = spec.get("line_height") or 1.18
    try:
        line_height_factor = float(line_height)
    except Exception:
        line_height_factor = 1.18
    required_height = estimated_lines * size * line_height_factor / 72
    if required_height > height * 1.45:
        errors.append(f"{prefix}: estimated text overflow is severe for zone {zone_value}")
    elif required_height > height * 1.05:
        warnings.append(f"{prefix}: estimated text overflow risk for zone {zone_value}")


def validate_text_color_contrast(item: dict[str, Any], prefix: str, errors: list[str], warnings: list[str]) -> None:
    treatment = as_dict(item.get("typographic_treatment"))
    color_token = str(treatment.get("color_token") or treatment.get("text_color") or "").strip()
    background = str(treatment.get("background_color") or treatment.get("background") or "").strip()
    color = str(treatment.get("color") or "").strip()
    if not background:
        return
    if color_token in {"accent", "secondary_accent"}:
        errors.append(f"{prefix}: {color_token} is reserved for decorative graphics unless contrast is explicitly proven")
    ratio = contrast_ratio(color, background) if color and background else None
    min_contrast = treatment.get("min_contrast")
    try:
        minimum = float(min_contrast) if min_contrast is not None else 4.5
    except Exception:
        minimum = 4.5
    if ratio is not None and ratio < minimum:
        role = str(item.get("role") or "")
        severity = errors if role in {"page_number", "caption", "body", "reasoning_copy"} or color_token in {"accent", "secondary_accent"} else warnings
        severity.append(f"{prefix}: text contrast must be >= {minimum:.1f}:1, got {ratio:.2f}")


def zone_center(zone: dict[str, Any]) -> tuple[float, float] | None:
    try:
        x = float(zone.get("x"))
        y = float(zone.get("y"))
        w = float(zone.get("w"))
        h = float(zone.get("h"))
    except Exception:
        return None
    return (x + w / 2, y + h / 2)


def point_from(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        return (float(value.get("x")), float(value.get("y")))
    except Exception:
        return None


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def point_segment_distance(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    sx, sy = start
    ex, ey = end
    px, py = point
    dx = ex - sx
    dy = ey - sy
    if dx == 0 and dy == 0:
        return distance(point, start)
    t = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)))
    projection = (sx + t * dx, sy + t * dy)
    return distance(point, projection)


def points_from(value: Any) -> list[tuple[float, float]]:
    return [point for item in as_list(value) if (point := point_from(item)) is not None]


def zone_intersects(a: dict[str, Any], b: dict[str, Any]) -> bool:
    try:
        ax, ay, aw, ah = float(a.get("x")), float(a.get("y")), float(a.get("w")), float(a.get("h"))
        bx, by, bw, bh = float(b.get("x")), float(b.get("y")), float(b.get("w")), float(b.get("h"))
    except Exception:
        return True
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def validate_asset_relationship_geometry(item: dict[str, Any], rel: dict[str, Any], asset_map: dict[str, Any], prefix: str, errors: list[str], warnings: list[str]) -> None:
    coordinate_space = str(asset_map.get("coordinate_space") or "").strip()
    if not coordinate_space:
        warnings.append(f"{prefix}: asset_visual_map.coordinate_space is missing; relationship geometry treated as advisory")
        return
    if coordinate_space != "slide_inches":
        warnings.append(f"{prefix}: asset_visual_map.coordinate_space={coordinate_space} is not slide_inches; relationship geometry treated as advisory")
        return
    zone = as_dict(item.get("zone"))
    center = zone_center(zone)
    if center is None:
        return
    anchor_type = str(rel.get("anchor_type") or "").strip()
    if anchor_type == "near_focus":
        focus = point_from(rel.get("focus_point"))
        if focus and distance(center, focus) > 3.6:
            errors.append(f"{prefix}.relationship_to_asset.focus_point is too far from the editable object zone")
    elif anchor_type == "along_axis":
        points = points_from(rel.get("primary_axis"))
        if len(points) >= 2:
            nearest = min(point_segment_distance(center, points[idx], points[idx + 1]) for idx in range(len(points) - 1))
            if nearest > 1.6:
                errors.append(f"{prefix}.relationship_to_asset.primary_axis is not near the editable object zone")
    elif anchor_type == "on_path":
        points = points_from(rel.get("path_points"))
        if len(points) >= 2:
            nearest = min(point_segment_distance(center, points[idx], points[idx + 1]) for idx in range(len(points) - 1))
            if nearest > 1.3:
                errors.append(f"{prefix}.relationship_to_asset.path_points are not near the editable object zone")
    elif anchor_type == "floating_in_quiet_field":
        fields = [field for field in as_list(rel.get("quiet_fields")) if isinstance(field, dict)]
        if fields and not any(zone_intersects(zone, field) for field in fields):
            errors.append(f"{prefix}.relationship_to_asset.quiet_fields do not overlap the editable object zone")


def validate_design_intent(
    slide: dict[str, Any],
    label: str,
    page_mode: Any,
    mode: str,
    project_dir: Path | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    if page_mode not in DESIGN_INTENT_REQUIRED_MODES:
        return

    intent = load_design_intent(slide, project_dir)
    if not intent:
        errors.append(f"{label}: {page_mode} requires design_intent or design_intent_ref")
        return
    if intent.get("__load_error"):
        errors.append(f"{label}: {intent['__load_error']}")
        return

    intent_text = json.dumps(intent, ensure_ascii=False)
    for placeholder in GENERIC_DESIGN_INTENT_PLACEHOLDERS:
        if placeholder.lower() in intent_text.lower():
            errors.append(f"{label}: design_intent contains generic placeholder phrase: {placeholder}")

    if mode in {"assembly", "deliverable"}:
        approval = as_dict(intent.get("approval"))
        if intent.get("approved") is not True and approval.get("approved") is not True:
            errors.append(f"{label}: design_intent.approval.approved must be true for {mode} validation")

    for field in ("design_problem", "desired_perception", "core_design_argument", "main_visual_move"):
        if not str(intent.get(field) or "").strip():
            errors.append(f"{label}: design_intent.{field} is required")

    main_move = str(intent.get("main_visual_move") or "").strip()
    if main_move and not main_visual_move_is_action(main_move):
        errors.append(f"{label}: design_intent.main_visual_move must be an action sentence, not a style-only phrase")

    relationship = as_dict(intent.get("text_image_relationship"))
    rel_type = str(relationship.get("relationship_type") or "").strip().lower()
    if rel_type == "adjacent":
        errors.append(f"{label}: design_intent.text_image_relationship.relationship_type must not be adjacent")

    editable_strategy = as_dict(intent.get("editable_strategy"))
    if not as_list(editable_strategy.get("must_remain_editable")):
        errors.append(f"{label}: design_intent.editable_strategy.must_remain_editable is required")

    asset_intent = as_dict(intent.get("asset_intent"))
    if not str(asset_intent.get("what_breaks_if_removed") or "").strip():
        errors.append(f"{label}: design_intent.asset_intent.what_breaks_if_removed is required")

    rejected = [item for item in as_list(intent.get("rejected_directions")) if isinstance(item, dict) and str(item.get("direction") or "").strip() and str(item.get("reason") or "").strip()]
    if len(rejected) < 2:
        errors.append(f"{label}: design_intent.rejected_directions must include at least 2 rejected directions with reasons")

    expectations = [str(item).strip().lower() for item in as_list(intent.get("visual_qa_expectations"))]
    for required in DESIGN_INTENT_QA_REQUIRED:
        if required not in expectations:
            errors.append(f"{label}: design_intent.visual_qa_expectations must include '{required}'")

    prompt_brief = str(intent.get("prompt_brief") or "")
    if len(prompt_brief) > 1400:
        warnings.append(f"{label}: design_intent.prompt_brief is long; keep it closer to art direction than a full prompt")
    if not as_list(intent.get("do_not_do")):
        warnings.append(f"{label}: design_intent.do_not_do is empty")
    layout_intent = as_dict(intent.get("layout_intent"))
    if not str(layout_intent.get("native_support_role") or "").strip():
        warnings.append(f"{label}: design_intent.layout_intent.native_support_role is empty")


def validate_editable_visual_composition(
    slide: dict[str, Any],
    label: str,
    page_mode: Any,
    mode: str,
    editable_layer: dict[str, Any],
    deck: dict[str, Any],
    project_dir: Path | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    if mode not in {"assembly", "deliverable"}:
        return
    if page_mode not in EDITABLE_VISUAL_COMPOSITION_REQUIRED_MODES:
        return
    if not editable_layer_has_text(editable_layer):
        return

    composition = load_editable_visual_composition(slide, project_dir)
    if not composition:
        errors.append(f"{label}: {page_mode} with editable text requires editable_visual_composition or editable_visual_composition_ref for {mode} validation")
        return
    if composition.get("__load_error"):
        errors.append(f"{label}: {composition['__load_error']}")
        return

    for field in ("text_layer_concept", "why_text_is_visual"):
        if not str(composition.get(field) or "").strip():
            errors.append(f"{label}: editable_visual_composition.{field} is required")

    approval = as_dict(composition.get("approval"))
    if approval.get("approved") is not True:
        errors.append(f"{label}: editable_visual_composition.approval.approved must be true for {mode} validation")

    objects = [item for item in as_list(composition.get("editable_objects")) if isinstance(item, dict)]
    if not objects:
        errors.append(f"{label}: editable_visual_composition.editable_objects must contain at least one editable object")

    asset_map_refs = [
        {
            "asset_id": asset_id(asset),
            "asset_visual_map": as_dict(asset.get("asset_visual_map")),
        }
        for asset in [*as_list(slide.get("generated_layer")), *as_list(slide.get("sourced_asset_layer"))]
        if isinstance(asset, dict) and isinstance(asset.get("asset_visual_map"), dict)
    ]
    bad_patterns = {str(item).strip().lower() for item in as_list(composition.get("anti_patterns"))}
    if not bad_patterns:
        warnings.append(f"{label}: editable_visual_composition.anti_patterns is empty")
    role_by_id: dict[str, str] = {}
    source_items = editable_source_items(editable_layer)
    evc_by_source_id: dict[str, dict[str, Any]] = {}
    for idx, item in enumerate(objects, start=1):
        prefix = f"{label}: editable_visual_composition.editable_objects[{idx}]"
        if item.get("editable") is not True:
            errors.append(f"{prefix}.editable must be true")
        for field in ("id", "role", "visual_behavior", "hierarchy_level", "zone", "typographic_treatment", "relationship_to_asset"):
            if field not in item:
                errors.append(f"{prefix} missing {field}")
        behavior = str(item.get("visual_behavior") or "").strip()
        if behavior in {"", "plain_bullet", "paragraph_stack", "text_stack", "ordinary_text"}:
            errors.append(f"{prefix}.visual_behavior must be art-directed, not {behavior or 'empty'}")
        rel = as_dict(item.get("relationship_to_asset"))
        if not str(rel.get("why_this_position") or "").strip():
            errors.append(f"{prefix}.relationship_to_asset.why_this_position is required")
        anchor_type = str(rel.get("anchor_type") or "").strip()
        if not anchor_type:
            errors.append(f"{prefix}.relationship_to_asset.anchor_type is required")
        required_map_ref = RELATIONSHIP_MAP_REQUIREMENTS.get(anchor_type)
        if required_map_ref:
            if required_map_ref not in rel:
                errors.append(f"{prefix}.relationship_to_asset.{required_map_ref} is required when anchor_type={anchor_type}")
            if not asset_map_refs:
                warnings.append(f"{prefix}: anchor_type={anchor_type} claims asset relation but no asset_visual_map exists on slide assets")
            else:
                asset_ref = str(rel.get("asset_reference") or "").strip()
                matching_maps = [
                    entry["asset_visual_map"]
                    for entry in asset_map_refs
                    if entry["asset_id"] == asset_ref
                ] or ([asset_map_refs[0]["asset_visual_map"]] if len(asset_map_refs) == 1 else [])
                if not matching_maps:
                    warnings.append(f"{prefix}: asset_reference does not match an asset_visual_map; relationship geometry treated as advisory")
                else:
                    validate_asset_relationship_geometry(item, rel, matching_maps[0], prefix, errors, warnings)
        must_not = {str(value).strip().lower() for value in as_list(item.get("must_not_be"))}
        if any(pattern in must_not for pattern in EDITABLE_VISUAL_COMPOSITION_BAD_PATTERNS):
            role_by_id[str(item.get("id") or idx)] = str(item.get("role") or "")
        treatment = as_dict(item.get("typographic_treatment"))
        if "hierarchy_level" not in treatment:
            errors.append(f"{prefix}.typographic_treatment.hierarchy_level is required")
        validate_typographic_weight(item, prefix, errors, warnings)
        source_id = str(item.get("source_id") or "").strip()
        if not source_id:
            warnings.append(f"{prefix}: missing source_id; id fallback is allowed only for migration and fails production validation")
            errors.append(f"{prefix}.source_id is required")
        if source_id:
            evc_by_source_id[source_id] = item
        if "zone" in item and isinstance(item.get("zone"), dict):
            estimate_text_overflow(item, prefix, deck, errors, warnings)
            validate_text_color_contrast(item, prefix, errors, warnings)

    if len(role_by_id) < max(1, min(3, len(objects))):
        warnings.append(f"{label}: editable_visual_composition should explicitly reject overlay/bullet/text-stack patterns on key objects")

    for source_id, source in source_items.items():
        item = evc_by_source_id.get(source_id)
        if not item:
            errors.append(f"{label}: editable_visual_composition missing source editable_layer text id {source_id}")
            continue
        if str(item.get("text") or "") != str(source.get("text") or ""):
            approved = item.get("text_revision_approved") is True or composition.get("text_revision_approved") is True
            note = str(item.get("text_revision_approval_note") or as_dict(composition.get("approval")).get("approval_notes") or "").strip()
            if not approved or not note:
                errors.append(f"{label}: editable_visual_composition text for {source_id} differs from editable_layer without text_revision_approved=true and approval note")

    for idx, item in enumerate(as_list(composition.get("native_support")), start=1):
        if not isinstance(item, dict):
            continue
        if "zone" not in item:
            errors.append(f"{label}: editable_visual_composition.native_support[{idx}].zone is required")


def validate_slide(slide: dict[str, Any], idx: int, mode: str, project_dir: Path | None, deck: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    label = f"Slide {slide.get('slide_number', idx)}"

    check_required_object(slide, SLIDE_REQUIRED, label, errors)

    number = slide.get("slide_number")
    if not isinstance(number, int):
        errors.append(f"{label}: slide_number must be an integer")

    page_mode = slide.get("page_mode")
    if page_mode not in PAGE_MODES:
        errors.append(f"{label}: page_mode must be one of {sorted(PAGE_MODES)}")

    core_message = str(slide.get("core_message") or "").strip()
    visual_idea = str(slide.get("visual_idea") or "").strip()
    if not visual_idea:
        errors.append(f"{label}: visual_idea is required")
    elif norm(visual_idea) == norm(core_message):
        errors.append(f"{label}: visual_idea must not equal core_message")

    composition = slide.get("composition_plan")
    if not isinstance(composition, dict):
        errors.append(f"{label}: composition_plan must be an object")
        composition = {}
    else:
        for field in ("type", "asset_zone", "text_safe_zone", "integration_logic", "approved"):
            if field not in composition:
                errors.append(f"{label}: composition_plan missing {field}")
        if mode in {"assembly", "deliverable"} and composition.get("approved") is not True:
            errors.append(f"{label}: composition_plan.approved must be true for {mode} validation")

    editable_layer = slide.get("editable_layer")
    if not isinstance(editable_layer, dict):
        errors.append(f"{label}: editable_layer must be an object")
        editable_layer = {}
    title_item = editable_layer.get("title")
    page_number_item = editable_layer.get("page_number")
    if not editable_item_ok(title_item):
        errors.append(f"{label}: editable_layer.title.editable must be true")
    if not editable_item_ok(page_number_item):
        errors.append(f"{label}: editable_layer.page_number.editable must be true")

    validate_route_and_archetype(deck, slide, label, mode, project_dir, errors)

    generated_layer = [item for item in as_list(slide.get("generated_layer")) if isinstance(item, dict)]
    sourced_layer = [item for item in as_list(slide.get("sourced_asset_layer")) if isinstance(item, dict)]
    asset_count = len(generated_layer) + len(sourced_layer)
    if page_mode in ASSET_REQUIRED_MODES and asset_count == 0:
        errors.append(f"{label}: {page_mode} requires generated_layer or sourced_asset_layer")

    for idx_asset, item in enumerate(as_list(slide.get("generated_layer")), start=1):
        if not isinstance(item, dict):
            errors.append(f"{label}: generated_layer[{idx_asset}] must be an object")
            continue
        for field in ("asset_id", "asset_type", "visual_role", "prompt"):
            if not str(item.get(field) or "").strip():
                errors.append(f"{label}: generated_layer[{idx_asset}] missing {field}")
        forbidden = generated_asset_mentions_forbidden_text(slide, item)
        if forbidden:
            errors.append(f"{label}: generated_layer[{idx_asset}] role/prompt contains {forbidden}; titles/page numbers must stay editable")

    validate_design_intent(slide, label, page_mode, mode, project_dir, errors, warnings)
    validate_editable_visual_composition(slide, label, page_mode, mode, editable_layer, deck, project_dir, errors, warnings)
    validate_native_graphics(slide, label, errors, warnings)

    if mode in {"assembly", "deliverable"}:
        for item in generated_layer + sourced_layer:
            if not asset_is_ready(item, project_dir):
                errors.append(f"{label}: asset {asset_id(item)} is not ready for {mode} validation")

    if mode == "deliverable":
        checks = as_dict(slide.get("validation_checks"))
        if checks.get("visual_qa_passed") is not True:
            errors.append(f"{label}: validation_checks.visual_qa_passed must be true for deliverable validation")

    return errors, warnings


def validate(data: dict[str, Any], *, mode: str, project_dir: Path | None, pptx_path: Path | None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if mode not in VALIDATION_MODES:
        errors.append(f"mode must be one of {sorted(VALIDATION_MODES)}")
        return errors, warnings

    check_required_object(data, TOP_LEVEL_REQUIRED, "Deck", errors)
    validate_visual_bible(data, errors, warnings)
    validate_deck_policy(data, mode, errors, warnings)

    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        errors.append("slides must be a non-empty array")
    else:
        seen_numbers: set[int] = set()
        for idx, slide in enumerate(slides, start=1):
            if not isinstance(slide, dict):
                errors.append(f"Slide {idx}: slide entry must be an object")
                continue
            number = slide.get("slide_number")
            if isinstance(number, int):
                if number in seen_numbers:
                    errors.append(f"Slide {number}: duplicate slide_number")
                seen_numbers.add(number)
            slide_errors, slide_warnings = validate_slide(slide, idx, mode, project_dir, data)
            errors.extend(slide_errors)
            warnings.extend(slide_warnings)

    if pptx_path:
        if not pptx_path.exists():
            errors.append(f"PPTX path does not exist: {pptx_path}")
        else:
            try:
                counts = count_ooxml_effects(pptx_path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Could not inspect PPTX OOXML effects: {exc}")
            else:
                for tag, count in counts.items():
                    if count > 0:
                        errors.append(f"PPTX contains forbidden OOXML effect {tag}: {count}")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blueprint", help="Path to deck blueprint JSON.")
    parser.add_argument("--mode", choices=sorted(VALIDATION_MODES), default="draft", help="Validation gate to run.")
    parser.add_argument("--project-dir", help="Project folder for resolving asset paths.")
    parser.add_argument("--pptx", help="Optional PPTX path for OOXML effect checks.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable result.")
    args = parser.parse_args()

    path = Path(args.blueprint)
    project_dir = Path(args.project_dir).resolve() if args.project_dir else None
    pptx_path = Path(args.pptx).resolve() if args.pptx else None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: could not read JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(data, dict):
        print("ERROR: blueprint root must be an object", file=sys.stderr)
        return 2

    errors, warnings = validate(data, mode=args.mode, project_dir=project_dir, pptx_path=pptx_path)

    if args.json:
        print(json.dumps({"mode": args.mode, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    else:
        print(f"Blueprint: {path}")
        print(f"Mode: {args.mode}")
        print(f"Errors: {len(errors)}")
        for item in errors:
            print(f"  - {item}")
        print(f"Warnings: {len(warnings)}")
        for item in warnings:
            print(f"  - {item}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
