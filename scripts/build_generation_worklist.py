#!/usr/bin/env python3
"""Build a generation worklist by joining asset prompts with asset slots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blueprint", help="Path to blueprint JSON. Used to infer project dir by default.")
    parser.add_argument("--project-dir", help="Project folder. Defaults to blueprint parent.")
    parser.add_argument("--mode", choices=["host-native", "manual"], default="host-native")
    args = parser.parse_args()

    blueprint = Path(args.blueprint).resolve()
    project_dir = Path(args.project_dir).resolve() if args.project_dir else blueprint.parent
    prompts_path = project_dir / "prompts" / "asset_prompts.json"
    slots_path = project_dir / "assets" / "asset_slots.json"
    if not prompts_path.exists():
        raise SystemExit(f"Missing prompts: {prompts_path}. Run generate_asset_prompts.py first.")
    if not slots_path.exists():
        raise SystemExit(f"Missing asset slots: {slots_path}. Run prepare_asset_slots.py first.")

    prompts = json.loads(prompts_path.read_text(encoding="utf-8")).get("prompts", [])
    slots = {slot["id"]: slot for slot in json.loads(slots_path.read_text(encoding="utf-8")).get("slots", [])}
    work = []
    for item in prompts:
        slot = slots.get(item["id"])
        filename = item.get("filename")
        path = project_dir / "assets" / filename if filename else None
        if slot:
            filename = slot.get("filename") or filename
            path = Path(slot.get("path") or (project_dir / "assets" / filename))
        work.append(
            {
                "id": item["id"],
                "slide_number": item.get("slide_number"),
                "kind": item.get("kind"),
                "mode": args.mode,
                "filename": filename,
                "path": str(path) if path else "",
                "slot_status": slot.get("status") if slot else "no-slot",
                "prompt": item.get("prompt", ""),
            }
        )

    output = project_dir / "prompts" / "generation_worklist.json"
    output.write_text(json.dumps({"mode": args.mode, "items": work}, ensure_ascii=False, indent=2), encoding="utf-8")

    md = project_dir / "prompts" / "generation_worklist.md"
    lines = [f"# Generation Worklist ({args.mode})", ""]
    for idx, item in enumerate(work, start=1):
        lines.extend(
            [
                f"## {idx}. {item['id']}",
                "",
                f"- Slide: {item.get('slide_number')}",
                f"- Kind: {item.get('kind')}",
                f"- Output: `{item.get('path')}`",
                f"- Slot status: {item.get('slot_status')}",
                "",
                item.get("prompt", ""),
                "",
            ]
        )
    md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Items: {len(work)}")
    print(f"JSON: {output}")
    print(f"Markdown: {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
