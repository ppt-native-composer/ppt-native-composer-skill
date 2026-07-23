#!/usr/bin/env python3
"""Apply a bundled style pack to a PPT Native Composer blueprint."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LIBRARY = SKILL_DIR / "templates" / "style_packs" / "style_packs.json"


def load_library(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    packs = payload.get("style_packs")
    if not isinstance(packs, dict) or not packs:
        raise SystemExit(f"No style_packs found in {path}")
    return packs


def canonical_palette(palette: dict[str, Any]) -> dict[str, str]:
    background = str(palette.get("background") or palette.get("paper") or "#F7F3EC")
    grid = str(palette.get("grid") or "#D8D8D0")
    return {
        "paper": str(palette.get("paper") or background),
        "background": background,
        "ink": str(palette.get("ink") or "#111111"),
        "muted": str(palette.get("muted") or "#666666"),
        "accent": str(palette.get("accent") or "#E6422E"),
        "secondary_accent": str(palette.get("secondary_accent") or palette.get("accent") or "#276EF1"),
        "line": str(palette.get("line") or grid),
    }


def apply_pack(data: dict[str, Any], pack_key: str, pack: dict[str, Any]) -> dict[str, Any]:
    output = deepcopy(data)
    output["style_pack"] = deepcopy(pack)

    bible = output.setdefault("visual_bible", {})
    if isinstance(bible, dict):
        bible["moodboard_reference"] = pack.get("reference_summary", bible.get("moodboard_reference", ""))
        bible["style_direction"] = pack.get("quality_bar", bible.get("style_direction", ""))
        bible["visual_motifs"] = deepcopy(pack.get("visual_motifs", bible.get("visual_motifs", [])))
        bible["native_component_style"] = json.dumps(pack.get("native_component_skin", {}), ensure_ascii=False)
        kit = bible.setdefault("asset_prompt_kit", {})
        if isinstance(kit, dict):
            kit["shared_rendering_language"] = pack.get("asset_prompt_base", kit.get("shared_rendering_language", ""))
            kit["negative_prompt"] = ", ".join(pack.get("do_not_use", [])) or kit.get("negative_prompt", "")
        tokens = bible.setdefault("design_tokens", {})
        if isinstance(tokens, dict):
            pal = pack.get("palette", {})
            tokens["colors"] = canonical_palette(pal if isinstance(pal, dict) else {})
            tokens["shape_language"] = pack.get("composition_grammar", {}).get("grid", tokens.get("shape_language", ""))

    brief = output.setdefault("deck_brief", {})
    if isinstance(brief, dict):
        name = str(brief.get("project_name") or "Deck")
        brief["project_name"] = f"{name} / {pack.get('name', pack_key)}"
        notes = str(brief.get("production_notes") or "")
        suffix = f"Style pack applied: {pack_key}."
        brief["production_notes"] = f"{notes} {suffix}".strip()

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blueprint", nargs="?", help="Input blueprint JSON.")
    parser.add_argument("style_pack", nargs="?", help="Style pack key.")
    parser.add_argument("-o", "--output", help="Output blueprint path.")
    parser.add_argument("--library", default=str(DEFAULT_LIBRARY), help="Style pack library JSON.")
    parser.add_argument("--list", action="store_true", help="List available style packs.")
    args = parser.parse_args()

    library_path = Path(args.library).resolve()
    packs = load_library(library_path)

    if args.list:
        for key, pack in packs.items():
            print(f"{key}\t{pack.get('name', key)}\t{pack.get('layout_recipe', '')}")
        return 0

    if not args.blueprint or not args.style_pack:
        raise SystemExit("blueprint and style_pack are required unless --list is used")
    if args.style_pack not in packs:
        raise SystemExit(f"Unknown style pack: {args.style_pack}. Use --list to inspect options.")

    source = Path(args.blueprint).resolve()
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Blueprint root must be an object")

    output = apply_pack(data, args.style_pack, packs[args.style_pack])
    target = Path(args.output).resolve() if args.output else source.with_name(f"{source.stem}-{args.style_pack}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Style pack: {args.style_pack}")
    print(f"Output: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
