#!/usr/bin/env python3
"""Create a draft page decomposition from a single-page GPT script."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SLIDE_W = 13.333333
SLIDE_H = 7.5


def first_nonempty(lines: list[str], default: str) -> str:
    for line in lines:
        value = line.strip().strip("#").strip()
        if value:
            return value
    return default


def extract_field(text: str, names: list[str]) -> str:
    for name in names:
        pattern = rf"^\s*(?:[-*]\s*)?{re.escape(name)}\s*[:：]\s*(.+?)\s*$"
        match = re.search(pattern, text, flags=re.I | re.M)
        if match:
            return match.group(1).strip()
    return ""


def bullet_lines(text: str) -> list[str]:
    values = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^[-*]\s+", stripped) or re.match(r"^\d+[.)、]\s*", stripped):
            value = re.sub(r"^[-*]\s+", "", stripped)
            value = re.sub(r"^\d+[.)、]\s*", "", value).strip()
            if value and not re.match(r"^[^:：]{1,18}[:：]", value):
                values.append(value)
    return values[:6]


def slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", value.strip())
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "asset"


def page_mode_from_family(page_family: str | None, text: str) -> str:
    haystack = f"{page_family or ''} {text}".lower()
    if any(token in haystack for token in ("kv", "cover", "chapter", "封面", "章节")):
        return "full_image"
    if any(token in haystack for token in ("timeline", "budget", "table", "schedule", "时间", "预算", "表格")):
        return "template_native"
    return "hybrid_native"


def build_decomposition(script_text: str, visual_bible: dict[str, Any], page_family: str | None) -> dict[str, Any]:
    lines = [line for line in script_text.splitlines() if line.strip()]
    title = extract_field(script_text, ["title", "page title", "标题", "页标题"]) or first_nonempty(lines, "Untitled Page")
    core_message = extract_field(script_text, ["core_message", "core message", "核心信息", "主判断", "核心判断"]) or first_nonempty(lines[1:], title)
    page_function = extract_field(script_text, ["page_function", "page function", "页面功能", "页功能"]) or page_family or "argument"
    audience_takeaway = extract_field(script_text, ["audience_takeaway", "audience takeaway", "受众记忆", "客户记住"]) or core_message
    visual_idea = extract_field(script_text, ["visual_idea", "visual idea", "视觉主意", "视觉概念"])
    if not visual_idea:
        visual_idea = f"Use a project-specific structural visual asset to make this point tangible: {core_message}"

    mode = extract_field(script_text, ["page_mode", "page mode", "页面模式"]) or page_mode_from_family(page_family, script_text)
    if mode not in {"full_image", "hybrid_native", "template_native"}:
        mode = "hybrid_native"

    body = bullet_lines(script_text)
    if not body and core_message != title:
        body = [core_message]

    asset_zone = {"x": 6.55, "y": 1.0, "w": 6.05, "h": 5.65}
    text_safe_zone = {"x": 0.7, "y": 0.85, "w": 5.45, "h": 5.8}
    asset_id = f"s00_{slug(title)[:36]}_core"
    prompt_base = visual_bible.get("asset_prompt_base") or visual_bible.get("asset_prompt_kit", {}).get("shared_rendering_language", "")

    generated_layer = []
    if mode in {"full_image", "hybrid_native"}:
        generated_layer.append(
            {
                "asset_id": asset_id,
                "asset_type": "core_visual_metaphor",
                "visual_role": visual_idea,
                "prompt": "Draft prompt seed. Run generate_asset_prompts.py to produce the production prompt from visual_role, Visual Bible, and composition_plan.asset_zone.",
                "dimensions": {"ratio": "zone_specific", "target_px": [1800, 1200]},
                "expected_zone": asset_zone,
                "transparency_required": False,
                "text_allowed": False,
                "logo_allowed": False,
                "exact_cn_text_required": False,
                "style_inheritance": "visual_bible.asset_prompt_base" if prompt_base else "visual_bible",
                "integration_with_editable_layer": "Core asset occupies asset_zone; editable title, page number, core message, and proof points sit in text_safe_zone.",
                "status": "missing",
            }
        )

    return {
        "title": title,
        "page_function": page_function,
        "page_mode": mode,
        "core_message": core_message,
        "audience_takeaway": audience_takeaway,
        "visual_idea": visual_idea,
        "composition_plan": {
            "type": "hero_asset_plus_editable_argument" if mode == "hybrid_native" else "mode_specific_layout",
            "asset_zone": asset_zone,
            "text_safe_zone": text_safe_zone,
            "integration_logic": "The visual asset must carry the page argument; editable text explains and labels it without becoming part of the image.",
            "approved": False,
            "approved_by": "",
            "approval_notes": "",
        },
        "editable_layer": {
            "title": {"id": "title", "role": "title", "text": title, "editable": True},
            "page_number": {"id": "page_number", "role": "page_number", "text": "", "editable": True},
            "body": [{"id": f"body_{idx}", "role": "proof_point", "text": item, "editable": True} for idx, item in enumerate(body, start=1)],
            "labels": [],
            "data": [],
            "table_text": [],
            "notes": [],
        },
        "generated_layer": generated_layer,
        "sourced_asset_layer": [],
        "native_graphic_layer": [
            {
                "object_type": "flat_rule",
                "purpose": "Support hierarchy between editable proof points without shadows or card containers.",
                "reason_required": "The page needs editable proof hierarchy that does not rely on fake depth.",
                "must_not_be_decorative": True,
            }
        ],
        "visual_text_layer": [],
        "validation_checks": {
            "package_passed": False,
            "editability_passed": False,
            "asset_delete_test_passed": False,
            "visual_qa_passed": False,
            "no_shadow_passed": False,
        },
        "validation_checklist": [
            "composition_plan.approved remains false until a human reviewer approves it",
            "title and page number stay editable",
            "core asset must not include slide title or page number",
            "asset must carry the visual argument, not act as decoration",
            "no SVG-like shadows, card shadows, or fake depth",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", help="Single-page GPT script as .md or .txt")
    parser.add_argument("visual_bible", help="visual_bible.json")
    parser.add_argument("--page-family", help="Optional page family hint, e.g. strategy or execution")
    parser.add_argument("-o", "--output", help="Output JSON path. Defaults to page_decomposition.json next to script.")
    args = parser.parse_args()

    script_path = Path(args.script).resolve()
    visual_bible_path = Path(args.visual_bible).resolve()
    script_text = script_path.read_text(encoding="utf-8")
    visual_bible = json.loads(visual_bible_path.read_text(encoding="utf-8"))
    if not isinstance(visual_bible, dict):
        raise SystemExit("visual_bible must be a JSON object")

    decomposition = build_decomposition(script_text, visual_bible, args.page_family)
    output = Path(args.output).resolve() if args.output else script_path.with_name("page_decomposition.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decomposition, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Page mode: {decomposition['page_mode']}")
    print("Approved: false")
    print(f"Output: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
