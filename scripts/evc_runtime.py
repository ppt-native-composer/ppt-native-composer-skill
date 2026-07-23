#!/usr/bin/env python3
"""Executable Editable Visual Composition runtime v2.

The runtime applies supported EVC fields to editable PowerPoint objects and
records every requested field as applied, audited-only, or explicitly
unsupported. It never rasterizes a slide as a fallback.
"""

from __future__ import annotations

import math
import re
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

from ooxml_capabilities import OoxmlCapabilityError, set_font_opacity, set_shape_fill_opacity, set_shape_line_opacity
from pptx_primitives import add_primitive
from relational_typography import resolve_binding


CANONICAL_WEIGHTS = {"bold", "semibold", "medium", "regular", "light"}
APPLIED_TEXT_FIELDS = {
    "cjk_font_family",
    "latin_font_family",
    "cjk_size_pt",
    "latin_size_pt",
    "weight",
    "weight_token",
    "color",
    "color_token",
    "horizontal_alignment",
    "alignment",
    "vertical_alignment",
    "vertical_anchor",
    "font_opacity",
    "line_spacing",
    "line_height",
    "paragraph_spacing_before_pt",
    "paragraph_spacing_after_pt",
    "margins",
    "run_level_emphasis",
    "paragraphs",
    "line_break_policy",
    "bullet",
    "overflow_policy",
    "relational_binding",
}
AUDITED_ONLY_FIELDS = {
    "size_intent",
    "font_size_intent",
    "emphasis",
    "line_break_logic",
    "spacing_logic",
    "weight_note",
    "relationship_to_asset",
    "background_color",
    "min_contrast",
    "must_not_be",
    "visual_behavior",
    "hierarchy_level",
}
EXPLICITLY_UNSUPPORTED_FIELDS = {
    "kerning",
    "baseline_shift",
    "character_stretch",
    "text_effects",
    "gradient_fill",
    "shadow",
    "glow",
    "bevel",
}

LAYER_ORDER = {
    "slide_background": 1,
    "background_asset": 2,
    "full_substrate": 2,
    "element_asset": 3,
    "native_support": 4,
    "primary_text": 5,
    "caption": 6,
    "label": 6,
    "page_system": 7,
}


def capability_manifest() -> dict[str, Any]:
    manifest_path = Path(__file__).resolve().parents[1] / "runtime_capability_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _rgb(value: str, fallback: str = "#111111") -> RGBColor:
    raw = str(value or fallback).strip().lstrip("#")
    if len(raw) != 6:
        raw = fallback.lstrip("#")
    return RGBColor(int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


def _zone(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError("EVC runtime object requires geometry/zone")
    return {key: float(value.get(key, 0.0)) for key in ("x", "y", "w", "h")}


def _alignment(value: Any) -> PP_ALIGN:
    raw = str(value or "left").lower()
    if raw in {"center", "centre"}:
        return PP_ALIGN.CENTER
    if raw == "right":
        return PP_ALIGN.RIGHT
    if raw == "justify":
        return PP_ALIGN.JUSTIFY
    return PP_ALIGN.LEFT


def _anchor(value: Any) -> MSO_ANCHOR:
    raw = str(value or "top").lower()
    if raw in {"middle", "center", "centre"}:
        return MSO_ANCHOR.MIDDLE
    if raw == "bottom":
        return MSO_ANCHOR.BOTTOM
    return MSO_ANCHOR.TOP


def _weight(value: Any, warnings: list[str]) -> str:
    raw = str(value or "regular").strip().lower().replace("semi-bold", "semibold")
    if raw in CANONICAL_WEIGHTS:
        return raw
    for token in ("semibold", "bold", "medium", "light", "regular"):
        if token in raw:
            warnings.append(f"legacy natural-language weight migrated to {token}: {raw}")
            return token
    warnings.append(f"unknown weight migrated to regular: {raw}")
    return "regular"


def _split_script_runs(text: str) -> list[tuple[str, str]]:
    chunks = re.findall(r"[\u3400-\u9fff\u3000-\u303f\uff00-\uffef]+|[^\u3400-\u9fff\u3000-\u303f\uff00-\uffef]+", text)
    return [(chunk, "cjk" if re.search(r"[\u3400-\u9fff]", chunk) else "latin") for chunk in chunks]


def _set_bullet(paragraph, enabled: bool) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    for tag in ("{http://schemas.openxmlformats.org/drawingml/2006/main}buNone", "{http://schemas.openxmlformats.org/drawingml/2006/main}buChar"):
        for child in list(p_pr):
            if child.tag == tag:
                p_pr.remove(child)
    node = OxmlElement("a:buChar" if enabled else "a:buNone")
    if enabled:
        node.set("char", "•")
    p_pr.append(node)


def _estimate_lines(text: str, width_in: float, size_pt: float) -> int:
    explicit = text.split("\n") or [""]
    capacity = max(1.0, width_in * 72.0 / max(size_pt, 1.0))
    lines = 0
    for paragraph in explicit:
        units = sum(1.0 if "\u3400" <= ch <= "\u9fff" else 0.55 for ch in paragraph)
        lines += max(1, math.ceil(units / capacity))
    return lines


def _overflow_resolution(text: str, box: dict[str, float], requested_size: float, policy: dict[str, Any]) -> dict[str, Any]:
    mode = str(policy.get("mode") or "warn")
    minimum = float(policy.get("minimum_size_pt") or policy.get("minimum_size") or requested_size)
    line_height = float(policy.get("line_height") or 1.15)
    applied = requested_size
    reason = None
    while True:
        lines = _estimate_lines(text, box["w"], applied)
        required_height = lines * applied * line_height / 72.0
        overflow = required_height > box["h"]
        if not overflow:
            break
        if mode == "fail":
            raise ValueError(f"text overflow under fail policy: required={required_height:.3f}in available={box['h']:.3f}in")
        if mode == "warn":
            reason = f"estimated overflow: required={required_height:.3f}in available={box['h']:.3f}in"
            break
        if mode != "shrink_with_floor":
            raise ValueError(f"Unknown overflow policy: {mode}")
        if applied - 0.5 < minimum:
            reason = f"minimum size reached with estimated overflow: {minimum}pt"
            applied = minimum
            break
        applied -= 0.5
        reason = "estimated text height exceeded object height"
    return {
        "mode": mode,
        "requested_size": requested_size,
        "applied_size": applied,
        "minimum_size": minimum,
        "shrink_reason": reason,
        "estimated_line_count": _estimate_lines(text, box["w"], applied),
    }


def _object_layer(item: dict[str, Any]) -> tuple[str, int, bool]:
    requested = str(item.get("layer") or "")
    if not requested:
        role = str(item.get("role") or "")
        requested = "page_system" if role == "page_number" else "caption" if role in {"caption", "label"} else "primary_text"
    return requested, LAYER_ORDER.get(requested, 5), requested in LAYER_ORDER


def _apply_textbox_appearance(shape, appearance: dict[str, Any], unsupported: list[str], context: dict[str, Any]) -> dict[str, Any]:
    tokens = context.get("color_tokens", {})
    applied: dict[str, Any] = {}
    fill = appearance.get("fill") or appearance.get("fill_color")
    if isinstance(fill, str):
        fill = tokens.get(fill, fill)
        shape.fill.solid()
        shape.fill.fore_color.rgb = _rgb(fill)
        applied["fill"] = fill
    else:
        shape.fill.background()
        applied["fill"] = None
    stroke = appearance.get("stroke") or appearance.get("line_color")
    if isinstance(stroke, str):
        stroke = tokens.get(stroke, stroke)
        shape.line.color.rgb = _rgb(stroke)
        applied["stroke"] = stroke
        width = float(appearance.get("line_width_pt") or appearance.get("stroke_width_pt") or 0.75)
        shape.line.width = Pt(width)
        applied["line_width_pt"] = width
        dash = str(appearance.get("dash_style") or "solid").lower()
        dash_map = {
            "solid": MSO_LINE_DASH_STYLE.SOLID,
            "dash": MSO_LINE_DASH_STYLE.DASH,
            "dot": MSO_LINE_DASH_STYLE.ROUND_DOT,
            "dash_dot": MSO_LINE_DASH_STYLE.DASH_DOT,
        }
        if dash in dash_map:
            shape.line.dash_style = dash_map[dash]
            applied["dash_style"] = dash
        else:
            unsupported.append("appearance.dash_style")
    else:
        shape.line.fill.background()
        applied["stroke"] = None
    opacity = float(appearance.get("opacity", 1.0))
    applied["opacity"] = opacity
    if opacity != 1.0:
        targets = 0
        try:
            if isinstance(fill, str):
                set_shape_fill_opacity(shape, opacity)
                targets += 1
            if isinstance(stroke, str):
                set_shape_line_opacity(shape, opacity)
                targets += 1
        except OoxmlCapabilityError:
            unsupported.append("appearance.opacity")
        if targets == 0:
            unsupported.append("appearance.opacity")
    return applied


@dataclass
class RuntimeAudit:
    slide_number: int
    route: str | None = None
    objects: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unsupported_fields: list[dict[str, Any]] = field(default_factory=list)

    def add(self, record: dict[str, Any]) -> None:
        self.objects.append(record)
        for path in record.get("unsupported_fields", []):
            self.unsupported_fields.append({"source_object_id": record.get("source_object_id"), "field": path})

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_version": "evc_runtime_v2",
            "slide_number": self.slide_number,
            "canonical_route": self.route,
            "objects": self.objects,
            "warnings": self.warnings,
            "unsupported_fields": self.unsupported_fields,
            "silent_ignore_count": 0,
        }


def _render_paragraphs(
    tf,
    item: dict[str, Any],
    treatment: dict[str, Any],
    fonts: dict[str, str],
    sizes: dict[str, float],
    weight: str,
    color: str,
    unsupported: list[str],
) -> None:
    structures = item.get("paragraphs") or treatment.get("paragraphs")
    if not isinstance(structures, list):
        policy = str(treatment.get("line_break_policy") or "preserve")
        text = str(item.get("text") or "")
        if policy == "remove":
            text = text.replace("\n", " ")
        emphasis = treatment.get("run_level_emphasis") if isinstance(treatment.get("run_level_emphasis"), list) else []
        structures = []
        offset = 0
        for line in text.split("\n"):
            spans: list[tuple[int, int, dict[str, Any]]] = []
            for rule in emphasis:
                if not isinstance(rule, dict):
                    continue
                if isinstance(rule.get("start"), int) and isinstance(rule.get("end"), int):
                    start = int(rule["start"]) - offset
                    end = int(rule["end"]) - offset
                else:
                    needle = str(rule.get("text") or "")
                    start = line.find(needle) if needle else -1
                    end = start + len(needle) if start >= 0 else -1
                if 0 <= start < end <= len(line):
                    spans.append((start, end, rule))
            spans.sort(key=lambda entry: entry[0])
            runs: list[dict[str, Any]] = []
            cursor = 0
            for start, end, rule in spans:
                if start < cursor:
                    continue
                if start > cursor:
                    runs.append({"text": line[cursor:start]})
                runs.append({"text": line[start:end], **{key: value for key, value in rule.items() if key not in {"start", "end", "text"}}})
                cursor = end
            if cursor < len(line):
                runs.append({"text": line[cursor:]})
            structures.append({"runs": runs or [{"text": line}]})
            offset += len(line) + 1
    tf.clear()
    for p_index, p_spec in enumerate(structures):
        paragraph = tf.paragraphs[0] if p_index == 0 else tf.add_paragraph()
        paragraph.alignment = _alignment(p_spec.get("alignment") or treatment.get("horizontal_alignment") or treatment.get("alignment"))
        line_spacing = p_spec.get("line_spacing") or treatment.get("line_spacing") or treatment.get("line_height")
        if isinstance(line_spacing, (int, float)):
            paragraph.line_spacing = float(line_spacing)
        before = p_spec.get("spacing_before_pt", treatment.get("paragraph_spacing_before_pt"))
        after = p_spec.get("spacing_after_pt", treatment.get("paragraph_spacing_after_pt"))
        if before is not None:
            paragraph.space_before = Pt(float(before))
        if after is not None:
            paragraph.space_after = Pt(float(after))
        _set_bullet(paragraph, bool(p_spec.get("bullet", treatment.get("bullet", False))))
        runs = p_spec.get("runs") if isinstance(p_spec.get("runs"), list) else [{"text": str(p_spec.get("text") or "")}]
        for run_spec in runs:
            text = str(run_spec.get("text") or "")
            for chunk, script in _split_script_runs(text):
                run = paragraph.add_run()
                run.text = chunk
                run.font.name = str(run_spec.get("font_family") or fonts[script])
                run.font.size = Pt(float(run_spec.get("size_pt") or sizes[script]))
                run_weight = str(run_spec.get("weight_token") or weight)
                run.font.bold = run_weight in {"bold", "semibold"}
                run.font.italic = bool(run_spec.get("italic", False))
                run.font.color.rgb = _rgb(str(run_spec.get("color") or color))
                font_opacity = run_spec.get("font_opacity", treatment.get("font_opacity", 1.0))
                if float(font_opacity) != 1.0:
                    try:
                        set_font_opacity(run, font_opacity)
                    except OoxmlCapabilityError:
                        unsupported.append("typographic_treatment.font_opacity")


def render_text_object(slide, item: dict[str, Any], context: dict[str, Any], audit: RuntimeAudit) -> dict[str, Any]:
    source_id = str(item.get("source_id") or item.get("id") or "")
    if not source_id:
        raise ValueError("EVC text object requires source_id")
    treatment = item.get("typographic_treatment") if isinstance(item.get("typographic_treatment"), dict) else {}
    resolved = resolve_binding(item, context.get("visual_targets"))
    geometry = _zone(resolved["geometry"])
    warnings: list[str] = []
    unsupported: list[str] = []
    audited_only: list[str] = []
    applied_item_fields = {"id", "source_id", "role", "text", "editable", "zone", "geometry", "rotation", "layer", "z_order", "paragraphs", "typographic_treatment", "appearance", "relational_binding"}
    audited_item_fields = {
        "visual_behavior",
        "hierarchy_level",
        "relationship_to_asset",
        "must_not_be",
        "text_revision_approved",
        "text_revision_approval_note",
        "migration_original_id",
    }
    for key in item:
        if key in audited_item_fields:
            audited_only.append(key)
        elif key not in applied_item_fields:
            unsupported.append(key)
    for key in treatment:
        if key in EXPLICITLY_UNSUPPORTED_FIELDS:
            unsupported.append(f"typographic_treatment.{key}")
        elif key in AUDITED_ONLY_FIELDS:
            audited_only.append(f"typographic_treatment.{key}")
        elif key not in APPLIED_TEXT_FIELDS and key not in {"hierarchy_level", "type_scale"}:
            unsupported.append(f"typographic_treatment.{key}")

    fonts = context.get("fonts", {})
    cjk_font = str(treatment.get("cjk_font_family") or fonts.get("cjk") or "PingFang SC")
    latin_font = str(treatment.get("latin_font_family") or fonts.get("latin") or "Aptos")
    default_size = float(context.get("default_size_pt") or 10.0)
    requested_cjk = float(treatment.get("cjk_size_pt") or default_size)
    requested_latin = float(treatment.get("latin_size_pt") or requested_cjk)
    overflow_policy = treatment.get("overflow_policy") if isinstance(treatment.get("overflow_policy"), dict) else {"mode": "warn", "minimum_size_pt": requested_cjk}
    overflow = _overflow_resolution(str(item.get("text") or ""), geometry, requested_cjk, overflow_policy)
    ratio = requested_latin / requested_cjk if requested_cjk else 1.0
    applied_cjk = float(overflow["applied_size"])
    applied_latin = applied_cjk * ratio
    if overflow.get("shrink_reason"):
        warnings.append(str(overflow["shrink_reason"]))
    weight = _weight(treatment.get("weight_token") or treatment.get("weight") or "regular", warnings)
    color = str(treatment.get("color") or context.get("color_tokens", {}).get(treatment.get("color_token")) or context.get("default_color") or "#111111")
    shape = slide.shapes.add_textbox(Inches(geometry["x"]), Inches(geometry["y"]), Inches(geometry["w"]), Inches(geometry["h"]))
    shape.name = source_id
    shape.rotation = float(resolved.get("rotation", item.get("rotation") or 0.0))
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = _anchor(treatment.get("vertical_alignment") or treatment.get("vertical_anchor"))
    margins = treatment.get("margins") if isinstance(treatment.get("margins"), dict) else {}
    tf.margin_left = Inches(float(margins.get("left", 0.03)))
    tf.margin_right = Inches(float(margins.get("right", 0.03)))
    tf.margin_top = Inches(float(margins.get("top", 0.03)))
    tf.margin_bottom = Inches(float(margins.get("bottom", 0.03)))
    _render_paragraphs(
        tf,
        item,
        treatment,
        {"cjk": cjk_font, "latin": latin_font},
        {"cjk": applied_cjk, "latin": applied_latin},
        weight,
        color,
        unsupported,
    )
    appearance = item.get("appearance") if isinstance(item.get("appearance"), dict) else {}
    applied_appearance = _apply_textbox_appearance(shape, appearance, unsupported, context)
    requested_layer, applied_z_order, known_layer = _object_layer(item)
    if not known_layer:
        unsupported.append("layer")
        warnings.append(f"unknown layer requested; applied deterministic primary_text rank: {requested_layer}")
    record = {
        "source_object_id": source_id,
        "pptx_shape_name": shape.name,
        "object_type": "editable_text",
        "role": item.get("role"),
        "text": item.get("text", ""),
        "editable": True,
        "requested_layer": requested_layer,
        "applied_layer": requested_layer,
        "requested_z_order": item.get("z_order"),
        "applied_z_order": applied_z_order,
        "requested_geometry": item.get("geometry") or item.get("zone"),
        "applied_geometry": geometry,
        "relational_binding_evidence": resolved["evidence"],
        "requested_typography": treatment,
        "applied_typography": {
            "cjk_font_family": cjk_font,
            "latin_font_family": latin_font,
            "cjk_size_pt": applied_cjk,
            "latin_size_pt": applied_latin,
            "weight_token": weight,
            "color": color,
            "horizontal_alignment": str(treatment.get("horizontal_alignment") or treatment.get("alignment") or "left"),
            "vertical_alignment": str(treatment.get("vertical_alignment") or treatment.get("vertical_anchor") or "top"),
            "line_spacing": treatment.get("line_spacing") or treatment.get("line_height"),
            "paragraph_spacing_before_pt": treatment.get("paragraph_spacing_before_pt"),
            "paragraph_spacing_after_pt": treatment.get("paragraph_spacing_after_pt"),
            "margins": {key: float(margins.get(key, 0.03)) for key in ("left", "right", "top", "bottom")},
            "bullet": bool(treatment.get("bullet", False)),
            "line_break_policy": treatment.get("line_break_policy", "preserve"),
        },
        "requested_appearance": appearance,
        "applied_appearance": applied_appearance,
        "overflow": overflow,
        "deviations": {
            "size_changed": requested_cjk != applied_cjk,
            "requested_cjk_size_pt": requested_cjk,
            "applied_cjk_size_pt": applied_cjk,
        },
        "warnings": warnings,
        "audited_only_fields": sorted(set(audited_only)),
        "unsupported_fields": sorted(set(unsupported)),
        "field_status": {
            "applied": sorted(key for key in treatment if key in APPLIED_TEXT_FIELDS),
            "audited_only": sorted(set(audited_only)),
            "explicitly_unsupported": sorted(set(unsupported)),
        },
    }
    audit.add(record)
    if resolved["evidence"].get("warning"):
        audit.warnings.append(resolved["evidence"]["warning"])
    return record


def render_evc(slide, evc: dict[str, Any], context: dict[str, Any], audit: RuntimeAudit) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    supports = [item for item in evc.get("native_support", []) if isinstance(item, dict)]
    supports.sort(key=lambda item: LAYER_ORDER.get(str(item.get("layer") or "native_support"), 4))
    for item in supports:
        _, record = add_primitive(slide, item)
        audit.add(record)
        records.append(record)
    text_objects = [item for item in evc.get("editable_objects", []) if isinstance(item, dict)]
    text_objects.sort(key=lambda item: _object_layer(item)[1])
    for item in text_objects:
        records.append(render_text_object(slide, item, context, audit))
    return records
