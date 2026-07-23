#!/usr/bin/env python3
"""Check asset slots and report missing/placeholder/ready/invalid assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def image_info(path: Path) -> tuple[tuple[int, int] | None, bool, bool]:
    try:
        with Image.open(path) as img:
            rgba = img.convert("RGBA")
            has_alpha = img.mode in {"RGBA", "LA"} or "transparency" in img.info
            # Fake checkerboard detection: many near-neutral alternating gray/white blocks.
            sample = rgba.resize((16, 16))
            pixels = list(sample.getdata())
            light_gray = sum(1 for r, g, b, _ in pixels if abs(r - g) < 8 and abs(g - b) < 8 and 185 <= r <= 245)
            opaque = sum(1 for *_, a in pixels if a > 245)
            fake_checker = light_gray > 80 and opaque > 220 and not has_alpha
            return img.size, has_alpha, fake_checker
    except Exception:
        return None, False, False


def expected_ratio(slot: dict[str, Any]) -> float | None:
    zone = slot.get("expected_zone")
    if not isinstance(zone, dict):
        return None
    try:
        w = float(zone.get("w"))
        h = float(zone.get("h"))
    except Exception:
        return None
    if w <= 0 or h <= 0:
        return None
    return w / h


def dimensions_wrong(slot: dict[str, Any], dims: tuple[int, int] | None) -> bool:
    if not dims:
        return False
    ratio = expected_ratio(slot)
    if ratio is None:
        return False
    actual = dims[0] / dims[1] if dims[1] else 0
    if actual <= 0:
        return True
    return abs(math.log(actual / ratio)) > math.log(1.45)


def status_for_slot(slot: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    path = Path(slot.get("path") or project_dir / "assets" / slot["filename"])
    record = dict(slot)
    record["path"] = str(path)
    if not path.exists():
        record["status"] = "missing"
        return record

    digest = sha256(path)
    dims, has_alpha, fake_checker = image_info(path)
    record["sha256"] = digest
    record["dimensions"] = dims
    record["has_alpha"] = has_alpha
    record["fake_checkerboard_suspected"] = fake_checker

    if slot.get("placeholder_sha256") and digest == slot.get("placeholder_sha256"):
        record["status"] = "placeholder"
    elif dims is None:
        record["status"] = "invalid"
        record["issue"] = "not a readable image"
    elif slot.get("transparency_required") and (not has_alpha or fake_checker):
        record["status"] = "invalid_transparency"
        record["issue"] = "transparency required but image has no alpha channel or appears to use fake checkerboard"
    elif dimensions_wrong(slot, dims):
        record["status"] = "wrong_dimensions"
        record["issue"] = "image ratio differs strongly from expected_zone"
    else:
        record["status"] = "ready"
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blueprint", help="Path to blueprint JSON. Used only to locate the project by default.")
    parser.add_argument("--project-dir", help="Project folder. Defaults to blueprint parent.")
    parser.add_argument("--mode", choices=["draft", "assembly"], default="draft", help="draft reports; assembly fails on blocking statuses.")
    args = parser.parse_args()

    blueprint = Path(args.blueprint).resolve()
    project_dir = Path(args.project_dir).resolve() if args.project_dir else blueprint.parent
    slots_path = project_dir / "assets" / "asset_slots.json"
    if not slots_path.exists():
        raise SystemExit(f"Missing asset slots file: {slots_path}. Run prepare_asset_slots.py first.")

    payload = json.loads(slots_path.read_text(encoding="utf-8"))
    checked = []
    counts = {"ready": 0, "placeholder": 0, "missing": 0, "invalid_transparency": 0, "wrong_dimensions": 0, "invalid": 0}
    for slot in payload.get("slots", []):
        if not isinstance(slot, dict):
            continue
        record = status_for_slot(slot, project_dir)
        counts[record["status"]] = counts.get(record["status"], 0) + 1
        checked.append(record)

    output = project_dir / "validation" / "asset_status.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"mode": args.mode, "counts": counts, "slots": checked}, ensure_ascii=False, indent=2), encoding="utf-8")
    for key in ("ready", "placeholder", "missing", "invalid_transparency", "wrong_dimensions", "invalid"):
        print(f"{key}: {counts.get(key, 0)}")
    print(f"Status: {output}")

    if args.mode == "assembly":
        blocking = counts.get("missing", 0) + counts.get("placeholder", 0) + counts.get("invalid_transparency", 0) + counts.get("invalid", 0)
        severe_ratio = counts.get("wrong_dimensions", 0)
        return 1 if blocking or severe_ratio else 0
    return 1 if counts.get("invalid", 0) or counts.get("invalid_transparency", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
