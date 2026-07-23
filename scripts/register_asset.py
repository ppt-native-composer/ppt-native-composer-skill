#!/usr/bin/env python3
"""Register a generated or sourced asset file into an asset slot."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def image_meta(path: Path) -> dict:
    with Image.open(path) as img:
        return {
            "dimensions": list(img.size),
            "mode": img.mode,
            "has_alpha": img.mode in {"RGBA", "LA"} or "transparency" in img.info,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slot_id", help="Asset slot id.")
    parser.add_argument("source_file", help="Generated/sourced image file.")
    parser.add_argument("--project-dir", required=True, help="Project folder containing assets/asset_slots.json.")
    parser.add_argument("--copy", action="store_true", help="Copy source file into the slot path. Default moves/overwrites by copying too, preserving source.")
    parser.add_argument("--note", default="", help="Optional provenance note.")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    source = Path(args.source_file).resolve()
    slots_path = project_dir / "assets" / "asset_slots.json"
    if not slots_path.exists():
        raise SystemExit(f"Missing asset slots: {slots_path}")
    if not source.exists():
        raise SystemExit(f"Missing source file: {source}")

    payload = json.loads(slots_path.read_text(encoding="utf-8"))
    slot = None
    for item in payload.get("slots", []):
        if item.get("id") == args.slot_id:
            slot = item
            break
    if slot is None:
        raise SystemExit(f"Slot not found: {args.slot_id}")

    target = Path(slot.get("path") or (project_dir / "assets" / slot["filename"]))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    slot["status"] = "ready"
    slot["registered_source"] = str(source)
    slot["registered_sha256"] = sha256(target)
    slot["registered_note"] = args.note
    slot.update(image_meta(target))
    slots_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Registered: {args.slot_id}")
    print(f"Target: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
