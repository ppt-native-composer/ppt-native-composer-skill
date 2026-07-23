#!/usr/bin/env python3
"""Inspect a PPTX package for missing required parts and broken relationships."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import zipfile
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET


REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def relationship_source_dir(rels_path: str) -> str:
    path = PurePosixPath(rels_path)
    if path.name == ".rels" and path.parent == PurePosixPath("_rels"):
        return ""
    parent = path.parent
    if parent.name == "_rels":
        return str(parent.parent)
    return str(parent)


def resolve_target(rels_path: str, target: str) -> str | None:
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return None
    if target.startswith("/"):
        return target.lstrip("/")
    base = relationship_source_dir(rels_path)
    return posixpath.normpath(posixpath.join(base, target)).lstrip("./")


def inspect(path: str) -> tuple[list[str], list[str], int]:
    errors: list[str] = []
    warnings: list[str] = []
    slide_count = 0

    try:
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
            if bad:
                errors.append(f"Corrupt ZIP member: {bad}")

            names = set(zf.namelist())
            required = {
                "[Content_Types].xml",
                "_rels/.rels",
                "ppt/presentation.xml",
                "ppt/_rels/presentation.xml.rels",
            }
            for item in sorted(required):
                if item not in names:
                    errors.append(f"Missing required part: {item}")

            slide_names = sorted(
                name
                for name in names
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
            )
            slide_count = len(slide_names)
            if slide_count == 0:
                errors.append("No slide XML parts found")

            for name in names:
                if not name.endswith(".rels"):
                    continue
                try:
                    root = ET.fromstring(zf.read(name))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"Malformed relationships XML: {name}: {exc}")
                    continue
                for rel in root.findall(f"{REL_NS}Relationship"):
                    target = rel.attrib.get("Target", "")
                    mode = rel.attrib.get("TargetMode", "")
                    if not target or mode == "External":
                        continue
                    resolved = resolve_target(name, target)
                    if resolved and resolved not in names:
                        errors.append(f"Broken relationship: {name} -> {target} (resolved {resolved})")

            for xml_name in ("ppt/presentation.xml", *slide_names):
                if xml_name not in names:
                    continue
                try:
                    ET.fromstring(zf.read(xml_name))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"Malformed XML: {xml_name}: {exc}")

            media_names = [name for name in names if name.startswith("ppt/media/")]
            if not media_names:
                warnings.append("No ppt/media assets found; this may be valid for text-only decks")

    except zipfile.BadZipFile as exc:
        errors.append(f"Not a valid zip/PPTX package: {exc}")
    except FileNotFoundError:
        errors.append(f"File not found: {path}")

    return errors, warnings, slide_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", help="Path to PPTX file.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("-o", "--output", help="Optional JSON output path.")
    args = parser.parse_args()

    errors, warnings, slide_count = inspect(args.pptx)
    result = {
        "pptx": args.pptx,
        "slides": slide_count,
        "errors": errors,
        "warnings": warnings,
        "result": "FAIL" if errors else "PASS",
    }
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    print(f"PPTX: {args.pptx}")
    print(f"Slides: {slide_count}")
    print(f"Errors: {len(errors)}")
    for item in errors:
        print(f"  - {item}")
    print(f"Warnings: {len(warnings)}")
    for item in warnings:
        print(f"  - {item}")

    if errors:
        print("Result: FAIL")
        return 1
    print("Result: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
