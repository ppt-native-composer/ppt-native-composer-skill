#!/usr/bin/env python3
"""Batch apply style packs, assemble PPTX variants, and validate outputs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from apply_style_pack import DEFAULT_LIBRARY, apply_pack, load_library


SCRIPT_DIR = Path(__file__).resolve().parent


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def parse_asset(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Assets must use id=/path/to/file.png")
    key, path = value.split("=", 1)
    if not key.strip() or not path.strip():
        raise argparse.ArgumentTypeError("Assets must use id=/path/to/file.png")
    return key.strip(), path.strip()


def style_short(key: str) -> str:
    parts = {
        "editorial_event_signal": "editorial",
        "swiss_modular_red": "swiss",
        "data_journalism_dark": "dark",
        "risograph_zine": "zine",
        "glass_saas_signal": "glass",
    }
    return parts.get(key, key.replace("_", "-"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blueprints", nargs="+", help="Input blueprint JSON files.")
    parser.add_argument("--styles", default="editorial_event_signal,swiss_modular_red,data_journalism_dark", help="Comma-separated style pack keys.")
    parser.add_argument("--project-root", required=True, help="Working project root for intermediate files.")
    parser.add_argument("--output-root", required=True, help="Output folder for PPTX and previews.")
    parser.add_argument("--library", default=str(DEFAULT_LIBRARY), help="Style pack library JSON.")
    parser.add_argument("--asset", action="append", default=[], type=parse_asset, help="Register shared asset as id=/path/to/file.png. Can repeat.")
    parser.add_argument("--render", action="store_true", help="Render PDF/contact-sheet previews.")
    parser.add_argument("--summary", help="Optional summary JSON path.")
    args = parser.parse_args()

    packs = load_library(Path(args.library).resolve())
    styles = [item.strip() for item in args.styles.split(",") if item.strip()]
    unknown = [key for key in styles if key not in packs]
    if unknown:
        raise SystemExit(f"Unknown style packs: {', '.join(unknown)}")

    project_root = Path(args.project_root).resolve()
    output_root = Path(args.output_root).resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    assets = dict(args.asset)
    results: list[dict[str, Any]] = []

    for blueprint_arg in args.blueprints:
        source = Path(blueprint_arg).resolve()
        data = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SystemExit(f"Blueprint root must be object: {source}")
        for style_key in styles:
            short = style_short(style_key)
            name = f"{source.stem}-{short}"
            project_dir = project_root / name
            project_dir.mkdir(parents=True, exist_ok=True)
            styled_blueprint = project_root / f"{name}.json"
            pptx_path = output_root / f"{name}.pptx"
            preview_dir = output_root / f"{name}-preview"

            styled = apply_pack(data, style_key, packs[style_key])
            styled_blueprint.write_text(json.dumps(styled, ensure_ascii=False, indent=2), encoding="utf-8")

            commands = [
                [sys.executable, str(SCRIPT_DIR / "validate_blueprint.py"), str(styled_blueprint)],
                [sys.executable, str(SCRIPT_DIR / "prepare_asset_slots.py"), str(styled_blueprint), "--project-dir", str(project_dir), "--create-placeholders"],
            ]
            for cmd in commands:
                run(cmd)

            for asset_id, asset_path in assets.items():
                slots_path = project_dir / "assets" / "asset_slots.json"
                slots = json.loads(slots_path.read_text(encoding="utf-8")).get("slots", [])
                if any(slot.get("id") == asset_id for slot in slots):
                    run([
                        sys.executable,
                        str(SCRIPT_DIR / "register_asset.py"),
                        asset_id,
                        asset_path,
                        "--project-dir",
                        str(project_dir),
                        "--note",
                        "batch registered shared regression asset",
                    ])

            asset_status = run([sys.executable, str(SCRIPT_DIR / "check_assets.py"), str(styled_blueprint), "--project-dir", str(project_dir)])
            run([sys.executable, str(SCRIPT_DIR / "assemble_pptx.py"), str(styled_blueprint), "--project-dir", str(project_dir), "-o", str(pptx_path)])
            package_status = run([sys.executable, str(SCRIPT_DIR / "inspect_pptx_package.py"), str(pptx_path)])
            if args.render:
                run([sys.executable, str(SCRIPT_DIR / "render_preview.py"), str(pptx_path), "--outdir", str(preview_dir)])

            results.append(
                {
                    "blueprint": str(source),
                    "style_pack": style_key,
                    "project_dir": str(project_dir),
                    "styled_blueprint": str(styled_blueprint),
                    "pptx": str(pptx_path),
                    "preview_dir": str(preview_dir) if args.render else None,
                    "asset_status": asset_status.stdout.strip(),
                    "package_status": package_status.stdout.strip(),
                }
            )
            print(f"PASS {name}")

    summary = {"count": len(results), "results": results}
    if args.summary:
        summary_path = Path(args.summary).resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
