#!/usr/bin/env python3
"""Create asset slots from generated/sourced asset layers."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


def slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_\-]+", "_", value.strip())
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "asset"


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def make_placeholder(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (1200, 800), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 1200, 800), fill=(238, 238, 238, 255))
    draw.rectangle((40, 40, 1160, 760), outline=(210, 60, 40, 255), width=8)
    draw.line((40, 40, 1160, 760), fill=(210, 60, 40, 255), width=4)
    draw.line((1160, 40, 40, 760), fill=(210, 60, 40, 255), width=4)
    draw.text((86, 370), f"PLACEHOLDER - NOT VALID FOR ASSEMBLY: {label[:64]}", fill=(30, 30, 30, 255))
    img.save(path)


def composition_asset_zone(slide: dict[str, Any]) -> dict[str, Any]:
    plan = slide.get("composition_plan", {})
    if isinstance(plan, dict) and isinstance(plan.get("asset_zone"), dict):
        return plan["asset_zone"]
    return {}


def asset_id(asset: dict[str, Any], slide_number: int, idx: int) -> str:
    return str(asset.get("asset_id") or asset.get("id") or f"slide_{slide_number}_asset_{idx}")


def filename_for(asset: dict[str, Any], slot_id: str) -> str:
    return str(asset.get("filename") or f"{slug(slot_id)}.png")


def slot_from_asset(
    asset: dict[str, Any],
    *,
    slide_number: int,
    idx: int,
    kind: str,
    fallback_zone: dict[str, Any],
    assets_dir: Path,
) -> dict[str, Any]:
    sid = asset_id(asset, slide_number, idx)
    filename = filename_for(asset, sid)
    expected_zone = asset.get("expected_zone") if isinstance(asset.get("expected_zone"), dict) else fallback_zone
    return {
        "id": sid,
        "asset_id": sid,
        "slide_number": slide_number,
        "kind": kind,
        "filename": filename,
        "required": True,
        "asset_type": str(asset.get("asset_type") or kind),
        "visual_role": str(asset.get("visual_role") or ""),
        "expected_zone": expected_zone,
        "transparency_required": bool(asset.get("transparency_required")),
        "text_allowed": bool(asset.get("text_allowed")),
        "logo_allowed": bool(asset.get("logo_allowed")),
        "exact_cn_text_required": bool(asset.get("exact_cn_text_required")),
        "status": "missing",
        "path": str(assets_dir / filename),
        "integration_with_editable_layer": asset.get("integration_with_editable_layer", ""),
    }


def build_slots(data: dict[str, Any], assets_dir: Path) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for slide in data.get("slides", []) or []:
        if not isinstance(slide, dict):
            continue
        n = int(slide.get("slide_number") or len(slots) + 1)
        fallback_zone = composition_asset_zone(slide)
        for idx, item in enumerate(as_list(slide.get("generated_layer")), start=1):
            if isinstance(item, dict):
                slots.append(slot_from_asset(item, slide_number=n, idx=idx, kind="generated_asset", fallback_zone=fallback_zone, assets_dir=assets_dir))
        for idx, item in enumerate(as_list(slide.get("sourced_asset_layer")), start=1):
            if isinstance(item, dict):
                slots.append(slot_from_asset(item, slide_number=n, idx=idx, kind="sourced_asset", fallback_zone=fallback_zone, assets_dir=assets_dir))
        for idx, item in enumerate(as_list(slide.get("visual_text_layer")), start=1):
            if isinstance(item, dict):
                asset = {
                    "asset_id": item.get("id") or f"slide_{n}_visual_text_{idx}",
                    "asset_type": "visual_text_asset",
                    "visual_role": item.get("reason") or item.get("text") or "visual text asset",
                    "transparency_required": True,
                    "text_allowed": True,
                    "logo_allowed": False,
                    "exact_cn_text_required": bool(item.get("exact_cn_text_required", True)),
                }
                slots.append(slot_from_asset(asset, slide_number=n, idx=idx, kind="visual_text_asset", fallback_zone=fallback_zone, assets_dir=assets_dir))
    return slots


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blueprint", help="Path to blueprint JSON.")
    parser.add_argument("--project-dir", help="Project folder. Defaults to blueprint parent.")
    parser.add_argument("--create-placeholders", action="store_true", help="Create draft-only placeholder PNGs for missing slots.")
    args = parser.parse_args()

    blueprint = Path(args.blueprint).resolve()
    project_dir = Path(args.project_dir).resolve() if args.project_dir else blueprint.parent
    assets_dir = project_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(blueprint.read_text(encoding="utf-8"))
    slots = build_slots(data, assets_dir)

    for slot in slots:
        path = Path(slot["path"])
        if args.create_placeholders and not path.exists():
            make_placeholder(path, slot.get("visual_role", slot["id"]))
            slot["status"] = "placeholder"
            slot["placeholder_sha256"] = sha256(path)
        elif path.exists():
            slot["status"] = "ready"
        else:
            slot["status"] = "missing"

    output = assets_dir / "asset_slots.json"
    output.write_text(json.dumps({"slots": slots}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Slots: {len(slots)}")
    print(f"Asset slots: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
