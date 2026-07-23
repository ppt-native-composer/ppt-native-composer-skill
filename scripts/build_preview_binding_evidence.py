#!/usr/bin/env python3
"""Build non-enforcing preview review material from existing runtime evidence.

This tool never reads image pixels, modifies a PPTX, or upgrades a visual
judgment. It makes the object-to-preview review trail inspectable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    candidate = Path(path)
    if not candidate.exists():
        return {"_missing_input": str(candidate)}
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def runtime_objects(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("objects"), list):
        return [item for item in payload["objects"] if isinstance(item, dict)]
    collected: list[dict[str, Any]] = []
    for slide in payload.get("slides", []) or []:
        if isinstance(slide, dict):
            collected.extend(item for item in slide.get("objects", []) or [] if isinstance(item, dict))
    return collected


def evc_items(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("source_id") or item.get("id")): item
        for item in payload.get("editable_objects", []) or []
        if isinstance(item, dict) and (item.get("source_id") or item.get("id"))
    }


def build_evidence(editability: dict[str, Any], runtime: dict[str, Any], evc: dict[str, Any], preview: str | None, case_id: str | None, human_notes: dict[str, Any]) -> dict[str, Any]:
    runtime_by_id = {str(item.get("source_object_id")): item for item in runtime_objects(runtime)}
    evc_by_id = evc_items(evc)
    composition_pattern = evc.get("composition_pattern")
    records = []
    for record in runtime_objects(editability):
        if record.get("object_type") != "editable_text":
            continue
        source_id = str(record.get("source_object_id") or "")
        spec = evc_by_id.get(source_id, {})
        runtime_record = runtime_by_id.get(source_id, record)
        relationship = spec.get("relationship_to_asset") if isinstance(spec.get("relationship_to_asset"), dict) else {}
        linked = relationship.get("asset_id") or relationship.get("asset_reference") or relationship.get("bound_element_ids")
        mechanical = "pass" if record.get("editable") and record.get("pptx_shape_name") else "partial"
        note = human_notes.get(source_id) if isinstance(human_notes, dict) else None
        records.append(
            {
                "case_id": case_id,
                "slide_id": runtime_record.get("slide_number") or record.get("slide_number"),
                "source_object_id": source_id,
                "pptx_shape_identity": record.get("pptx_shape_name"),
                "requested_relationship_to_asset": relationship,
                "requested_visual_behavior": spec.get("visual_behavior"),
                "requested_geometry": runtime_record.get("requested_geometry") or record.get("requested_geometry"),
                "applied_geometry": runtime_record.get("applied_geometry") or record.get("applied_geometry"),
                "relational_binding": spec.get("relational_binding"),
                "relational_binding_evidence": runtime_record.get("relational_binding_evidence"),
                "composition_pattern": composition_pattern,
                "reading_sequence": (spec.get("relational_binding") or {}).get("reading_sequence"),
                "linked_asset_id": linked,
                "preview_path": preview,
                "preview_region": None,
                "mechanical_evidence_status": mechanical,
                "human_review_status": "manual_required",
                "human_reviewer_note": note or "",
                "binding_status": "manual_required",
                "readiness_unchanged": True,
                "enforcement": False,
            }
        )
    return {
        "evidence_version": "phase5_preview_binding_v1",
        "case_id": case_id,
        "enforcement": False,
        "readiness_unchanged": True,
        "records": records,
        "manual_review_questions": [
            "Does the text form a visual relationship with its intended asset or native element?",
            "Is the relationship more than mere proximity?",
            "Do requested and applied geometry deviations weaken the intended expression?",
        ],
    }


def markdown_report(evidence: dict[str, Any]) -> str:
    lines = ["# Preview Binding Review", "", "This is non-enforcing review material. All visual judgments remain manual_required.", ""]
    for record in evidence["records"]:
        lines.extend([
            f"## {record['source_object_id']}",
            f"- PPTX shape: `{record['pptx_shape_identity']}`",
            f"- Mechanical evidence: `{record['mechanical_evidence_status']}`",
            f"- Requested behavior: `{record['requested_visual_behavior']}`",
            f"- Binding status: `{record['binding_status']}`",
            f"- Preview: `{record['preview_path']}`",
            "",
        ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--editability-map-v2", required=True)
    parser.add_argument("--runtime-report", required=True)
    parser.add_argument("--evc", required=True)
    parser.add_argument("--preview")
    parser.add_argument("--human-notes")
    parser.add_argument("--case-id")
    parser.add_argument("--output", required=True)
    parser.add_argument("--markdown-out")
    args = parser.parse_args()
    evidence = build_evidence(
        load_json(args.editability_map_v2), load_json(args.runtime_report), load_json(args.evc), args.preview, args.case_id, load_json(args.human_notes)
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown_out:
        markdown = Path(args.markdown_out)
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(markdown_report(evidence) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
