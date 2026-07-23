#!/usr/bin/env python3
"""Scaffold a PPT Native Composer project folder."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def slugify(value: str) -> str:
    allowed = []
    for char in value.strip().lower():
        if char.isalnum():
            allowed.append(char)
        elif char in {" ", "-", "_"}:
            allowed.append("-")
    slug = "".join(allowed).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "ppt-native-project"


def default_blueprint(project_name: str) -> dict:
    return {
        "deck_brief": {
            "project_name": project_name,
            "deck_type": "",
            "audience": "",
            "objective": "",
            "creative_summary": "",
            "production_notes": "",
        },
        "visual_bible": {
            "moodboard_reference": "",
            "style_direction": "",
            "design_tokens": {
                "colors": ["#111111", "#F7F3EC", "#FF5A3D", "#246BFE"],
                "shape_language": "editable cards, thin dividers, object-led visual accents",
                "texture": "subtle grain",
                "lighting": "soft directional highlight",
                "layout_density": "proposal-balanced",
            },
            "visual_motifs": ["accent label", "thin rule line", "object anchor"],
            "page_family_map": {
                "strategy_pages": "larger visual field and concise editable thesis",
                "execution_pages": "designed native structures with integrated visual assets",
                "data_pages": "editable values with designed table/chart skin",
                "chapter_pages": "high-impact full-image or hybrid visual page",
            },
            "asset_prompt_kit": {
                "shared_rendering_language": "",
                "transparent_png_rules": "transparent background for object assets; no ordinary body copy inside generated images",
                "visual_text_rules": "only short marked creative expressions may be generated as image text",
                "negative_prompt": "no fake logos, no QR codes, no random microcopy, no page numbers",
            },
            "native_component_style": "rounded cards, accent tabs, thin rules, integrated image anchors",
            "do_not_use": ["default Office SmartArt", "plain grid tables", "unmarked image text"],
        },
        "font_plan": {
            "cjk": "PingFang SC",
            "latin": "Aptos",
            "fallback": ["Microsoft YaHei", "Arial"],
            "hierarchy": {
                "title": "34-44pt editable title",
                "subtitle": "18-24pt editable support line",
                "body": "15-20pt editable body",
                "caption": "10-12pt captions",
                "data": "18-30pt key numbers",
            },
            "display_text_policy": "Page titles and body stay editable; only explicit visual_text_assets may be rasterized.",
        },
        "slides": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_name", help="Human-readable project name.")
    parser.add_argument("--root", default=".", help="Parent folder for the project.")
    parser.add_argument("--force", action="store_true", help="Allow an existing project directory.")
    args = parser.parse_args()

    project_dir = Path(args.root) / slugify(args.project_name)
    if project_dir.exists() and not args.force:
        raise SystemExit(f"Project exists: {project_dir}. Use --force to reuse it.")

    for child in ("assets", "prompts", "pptx", "validation", "previews"):
        (project_dir / child).mkdir(parents=True, exist_ok=True)

    blueprint = project_dir / "blueprint.json"
    if not blueprint.exists() or args.force:
        blueprint.write_text(
            json.dumps(default_blueprint(args.project_name), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(project_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
