#!/usr/bin/env python3
"""Generate a Layout Intelligence scorecard from existing assembly artifacts.

This is an assisted Phase 1 tool. It does not modify PPTX files, does not call
validators, and does not decide final aesthetics. Checks that require rendered
visual judgment are explicitly marked as manual_required/not_run.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from route_normalization import extract_route  # noqa: E402


STATUS_PASS = "pass"
STATUS_PARTIAL = "partial"
STATUS_FAIL = "fail"
STATUS_NOT_RUN = "not_run"
STATUS_MANUAL_REQUIRED = "manual_required"
PROFILE_VERSION = "phase3b_profile_v0_1"
PROFILE_AUTO = "auto"
PROFILE_ELEMENT_FIRST = "element_first_strategy_profile"
PROFILE_MIGRATED_CONCEPT = "migrated_concept_text_profile"
PROFILE_EXECUTION_PATH = "execution_path_profile"
PROFILE_FULL_SUBSTRATE = "full_substrate_profile"

PROFILE_CHOICES = [
    PROFILE_AUTO,
    PROFILE_ELEMENT_FIRST,
    PROFILE_MIGRATED_CONCEPT,
    PROFILE_EXECUTION_PATH,
    PROFILE_FULL_SUBSTRATE,
]


def load_json(path: str | None, *, required: bool = False) -> tuple[Any, dict[str, Any]]:
    if not path:
        return None, {"status": STATUS_NOT_RUN, "warning": "input path not provided"}
    p = Path(path)
    if not p.exists():
        message = f"input file does not exist: {p}"
        if required:
            return None, {"status": STATUS_FAIL, "warning": message}
        return None, {"status": STATUS_NOT_RUN, "warning": message}
    try:
        return json.loads(p.read_text(encoding="utf-8")), {"status": STATUS_PASS, "path": str(p)}
    except Exception as exc:  # noqa: BLE001 - user-facing diagnostics
        return None, {"status": STATUS_FAIL, "warning": f"failed to parse JSON: {exc}", "path": str(p)}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def bbox_from_record(record: dict[str, Any]) -> dict[str, float] | None:
    if isinstance(record.get("bbox"), dict):
        source = record["bbox"]
    elif isinstance(record.get("zone"), dict):
        source = record["zone"]
    else:
        source = record
    try:
        x = float(source["x"])
        y = float(source["y"])
        w = float(source["w"])
        h = float(source["h"])
    except Exception:
        return None
    if w <= 0 or h <= 0:
        return None
    return {"x": x, "y": y, "w": w, "h": h}


def bbox_edges(bbox: dict[str, float]) -> tuple[float, float, float, float]:
    return bbox["x"], bbox["y"], bbox["x"] + bbox["w"], bbox["y"] + bbox["h"]


def bbox_center(bbox: dict[str, float]) -> tuple[float, float]:
    return bbox["x"] + bbox["w"] / 2, bbox["y"] + bbox["h"] / 2


def point_to_bbox_edge_distance(point: dict[str, Any], bbox: dict[str, float]) -> float:
    left, top, right, bottom = bbox_edges(bbox)
    px = float(point["x"])
    py = float(point["y"])
    dx = 0.0 if left <= px <= right else min(abs(px - left), abs(px - right))
    dy = 0.0 if top <= py <= bottom else min(abs(py - top), abs(py - bottom))
    return math.hypot(dx, dy)


def bbox_to_bbox_edge_distance(a: dict[str, float], b: dict[str, float]) -> float:
    a_left, a_top, a_right, a_bottom = bbox_edges(a)
    b_left, b_top, b_right, b_bottom = bbox_edges(b)
    dx = max(b_left - a_right, a_left - b_right, 0.0)
    dy = max(b_top - a_bottom, a_top - b_bottom, 0.0)
    return math.hypot(dx, dy)


def bboxes_overlap(a: dict[str, float], b: dict[str, float]) -> bool:
    a_left, a_top, a_right, a_bottom = bbox_edges(a)
    b_left, b_top, b_right, b_bottom = bbox_edges(b)
    return a_left < b_right and a_right > b_left and a_top < b_bottom and a_bottom > b_top


def bbox_clearance(a: dict[str, float], b: dict[str, float]) -> float:
    return 0.0 if bboxes_overlap(a, b) else bbox_to_bbox_edge_distance(a, b)


def point_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def cubic_bezier(points: list[dict[str, Any]], t: float) -> tuple[float, float]:
    p0, p1, p2, p3 = points
    mt = 1 - t
    x = (
        mt**3 * float(p0["x"])
        + 3 * mt**2 * t * float(p1["x"])
        + 3 * mt * t**2 * float(p2["x"])
        + t**3 * float(p3["x"])
    )
    y = (
        mt**3 * float(p0["y"])
        + 3 * mt**2 * t * float(p1["y"])
        + 3 * mt * t**2 * float(p2["y"])
        + t**3 * float(p3["y"])
    )
    return x, y


def sample_curve_points(element: dict[str, Any]) -> list[tuple[float, float]]:
    geometry = as_dict(element.get("geometry"))
    points = geometry.get("bezier_points") or geometry.get("path_points") or []
    if not isinstance(points, list) or not points:
        return []
    if len(points) == 4 and geometry.get("bezier_points"):
        return [cubic_bezier(points, i / 30) for i in range(31)]
    sampled: list[tuple[float, float]] = []
    for item in points:
        if isinstance(item, dict) and "x" in item and "y" in item:
            sampled.append((float(item["x"]), float(item["y"])))
    return sampled


def bbox_center_to_curve_distance(bbox: dict[str, float], element: dict[str, Any]) -> float | None:
    points = sample_curve_points(element)
    if not points:
        return None
    center = bbox_center(bbox)
    return min(point_distance(center, point) for point in points)


def cjk_weighted_count(text: str) -> float:
    total = 0.0
    for char in text:
        if char.isspace():
            continue
        code = ord(char)
        if (
            0x4E00 <= code <= 0x9FFF
            or 0x3400 <= code <= 0x4DBF
            or 0x3000 <= code <= 0x303F
            or 0xFF00 <= code <= 0xFFEF
        ):
            total += 1
        elif char.isascii() and char.isalnum():
            total += 0.5
        else:
            total += 1
    return total


def explicit_line_count(text: str) -> int:
    lines = text.splitlines() or [text]
    return max(1, len(lines))


def normalize_role(role: str, object_id: str) -> str:
    value = f"{role} {object_id}".lower()
    if "title" in value:
        return "title"
    if "claim" in value or "main" in value:
        return "claim"
    if "caption" in value or "body" in value:
        return "caption"
    if "page_number" in value or "page number" in value:
        return "page_number"
    if "proof" in value:
        return "proof_label"
    return "caption"


def role_threshold(thresholds: dict[str, Any], role: str) -> dict[str, Any]:
    return as_dict(as_dict(thresholds.get("typography_role_thresholds")).get(role))


def status_from_density(density: float | None, role_config: dict[str, Any], mapping: dict[str, Any]) -> tuple[str, str | None]:
    if density is None:
        return STATUS_NOT_RUN, "missing density metric"
    limit = role_config.get("max_cjk_chars_per_square_inch")
    if not isinstance(limit, (int, float)):
        return STATUS_NOT_RUN, "missing role density threshold"
    if density > float(limit) * float(mapping.get("density_above_role_max_multiplier_for_fail", 1.25)):
        return STATUS_FAIL, "density above 125% of role max"
    if density > float(limit):
        return STATUS_PARTIAL, "density above role max"
    return STATUS_PASS, None


def status_from_line_count(line_count: int, role_config: dict[str, Any]) -> tuple[str, str | None]:
    max_lines = role_config.get("max_lines")
    if not isinstance(max_lines, int):
        return STATUS_NOT_RUN, "missing max_lines threshold"
    if line_count > max_lines + 1:
        return STATUS_FAIL, "line count above max_lines + 1"
    if line_count > max_lines:
        return STATUS_PARTIAL, "line count above max_lines"
    return STATUS_PASS, None


def combine_status(statuses: list[str]) -> str:
    if STATUS_FAIL in statuses:
        return STATUS_FAIL
    if STATUS_PARTIAL in statuses:
        return STATUS_PARTIAL
    runnable = [status for status in statuses if status != STATUS_NOT_RUN]
    if not runnable:
        return STATUS_NOT_RUN
    return STATUS_PASS


def severity_for_status(status: str) -> str:
    if status == STATUS_FAIL:
        return "high"
    if status == STATUS_PARTIAL:
        return "medium"
    return "low"


def profile_rules(profile_id: str) -> dict[str, Any]:
    base = {
        "profile_id": profile_id,
        "profile_version": PROFILE_VERSION,
        "page_number_can_force_l2_fail": False,
        "binding_mode": "strict_element_first",
        "execution_line_count_fail_extra_lines": 2,
    }
    if profile_id == PROFILE_ELEMENT_FIRST:
        base["page_number_can_force_l2_fail"] = False
        base["binding_mode"] = "strict_element_first"
    elif profile_id == PROFILE_MIGRATED_CONCEPT:
        base["binding_mode"] = "profile_relaxed_concept"
    elif profile_id == PROFILE_EXECUTION_PATH:
        base["binding_mode"] = "profile_relaxed_execution"
        base["execution_line_count_fail_extra_lines"] = 3
    elif profile_id == PROFILE_FULL_SUBSTRATE:
        base["binding_mode"] = "substrate_level_relationship_manual"
    return base


def normalize_profile_route(assembly_plan: dict[str, Any]) -> dict[str, str | None]:
    info = extract_route(assembly_plan, strict=False)
    trust = None
    if info.get("normalization_source") == "canonical":
        trust = "canonical"
    elif info.get("normalization_source") == "legacy_alias":
        trust = "legacy_normalized"
    return {
        "profile_route_source": info.get("source_path"),
        "profile_route_raw": info.get("raw_route"),
        "profile_route_normalized": info.get("canonical_route"),
        "profile_route_trust": trust,
    }


def select_profile(requested_profile: str, assembly_plan: dict[str, Any], objects: list[dict[str, Any]]) -> dict[str, Any]:
    route_info = normalize_profile_route(assembly_plan)
    if requested_profile != PROFILE_AUTO:
        return {
            **profile_rules(requested_profile),
            "profile_reason": "explicit --profile argument",
            "profile_requested": requested_profile,
            "profile_selection_mode": "manual",
            "profile_precedence_decision": "explicit_profile_argument",
            "profile_conflict": False,
            "profile_conflict_reason": None,
            **route_info,
        }

    route_id = route_info.get("profile_route_normalized")
    route_trust = route_info.get("profile_route_trust")
    conflict = False
    conflict_reason = None
    if route_id == "element_asset_hybrid":
        profile_id = PROFILE_ELEMENT_FIRST
        reason = f"auto: canonical route from {route_info.get('profile_route_source')} is element_asset_hybrid"
        precedence_decision = "canonical_route_selected"
    elif route_id in {"full_substrate_hybrid", "visual_reference_mode"}:
        profile_id = PROFILE_FULL_SUBSTRATE
        reason = f"auto: canonical route from {route_info.get('profile_route_source')} requires substrate-level review"
        precedence_decision = "canonical_route_selected"
    elif route_id == "template_native_plus_skin":
        profile_id = PROFILE_EXECUTION_PATH
        reason = f"auto: canonical route from {route_info.get('profile_route_source')} is template_native_plus_skin"
        precedence_decision = "canonical_route_selected"
    elif route_id == "pure_native_safety":
        profile_id = PROFILE_MIGRATED_CONCEPT
        reason = f"auto: canonical route from {route_info.get('profile_route_source')} is pure_native_safety"
        precedence_decision = "canonical_route_selected"
    else:
        profile_id = PROFILE_MIGRATED_CONCEPT
        reason = "auto fallback: route provenance missing or unknown; no filename/object-prefix inference is allowed"
        precedence_decision = "route_missing_safe_fallback"
        conflict = route_id is None
        conflict_reason = "route provenance missing" if conflict else None
    return {
        **profile_rules(profile_id),
        "profile_reason": reason,
        "profile_requested": requested_profile,
        "profile_selection_mode": "auto",
        "profile_precedence_decision": precedence_decision,
        "profile_conflict": conflict,
        "profile_conflict_reason": conflict_reason,
        **route_info,
    }


def collect_editable_objects(editability_map: Any, evc: Any, assembly_plan: Any) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if isinstance(editability_map, dict) and isinstance(editability_map.get("objects"), list):
        editability_sources = editability_map["objects"]
    else:
        editability_sources = as_list(editability_map)
    for source in editability_sources:
        if not isinstance(source, dict):
            continue
        object_id = str(source.get("object_id") or source.get("id") or "")
        if object_id:
            records[object_id] = dict(source)

    evc_objects = as_list(as_dict(evc).get("editable_objects"))
    plan_objects = as_list(as_dict(assembly_plan).get("editable_text_objects"))
    by_id_sources = []
    for source in evc_objects + plan_objects:
        if isinstance(source, dict):
            by_id_sources.append(source)

    for source in by_id_sources:
        object_id = str(source.get("object_id") or source.get("id") or "")
        if not object_id:
            continue
        existing = records.setdefault(object_id, {})
        for key, value in source.items():
            if key not in existing or existing.get(key) in (None, "", []):
                existing[key] = value
        if "bbox" not in existing and isinstance(source.get("zone"), dict):
            existing["bbox"] = source["zone"]
        if "bound_element_ids" not in existing:
            rel = as_dict(source.get("relationship_to_asset"))
            if isinstance(rel.get("bound_element_ids"), list):
                existing["bound_element_ids"] = rel["bound_element_ids"]

    return list(records.values())


def collect_elements(assembly_plan: Any) -> dict[str, dict[str, Any]]:
    plan = as_dict(assembly_plan)
    elements: dict[str, dict[str, Any]] = {}
    for key, value in as_dict(plan.get("selected_local_assets")).items():
        if isinstance(value, dict):
            item = dict(value)
            item["element_id"] = key
            item["category"] = "selected_local_asset"
            elements[key] = item
    for key, value in as_dict(plan.get("native_element_geometry")).items():
        if isinstance(value, dict):
            item = dict(value)
            item["element_id"] = key
            item["category"] = "native_element"
            elements[key] = item
    for item in as_list(plan.get("editable_text_objects")):
        if isinstance(item, dict) and item.get("id"):
            elements[str(item["id"])] = {**item, "element_id": str(item["id"]), "category": "editable_text_object"}
    return elements


def node_bbox(elements: dict[str, dict[str, Any]], element_id: str) -> dict[str, float] | None:
    element = elements.get(element_id)
    if not element:
        return None
    bbox = bbox_from_record(element)
    if bbox:
        return bbox
    geometry = as_dict(element.get("geometry"))
    center = geometry.get("center")
    radii = geometry.get("radii")
    if isinstance(center, dict) and isinstance(radii, list) and radii:
        max_radius = max(float(radius) for radius in radii)
        return {
            "x": float(center["x"]) - max_radius,
            "y": float(center["y"]) - max_radius,
            "w": max_radius * 2,
            "h": max_radius * 2,
        }
    if isinstance(center, dict) and "radius" in geometry:
        radius = float(geometry["radius"])
        return {
            "x": float(center["x"]) - radius,
            "y": float(center["y"]) - radius,
            "w": radius * 2,
            "h": radius * 2,
        }
    return None


def typography_score(objects: list[dict[str, Any]], thresholds: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    mapping = as_dict(thresholds.get("status_mapping_rules"))
    result: dict[str, Any] = {}
    for obj in objects:
        object_id = str(obj.get("object_id") or obj.get("id") or "unknown")
        text = str(obj.get("text") or "")
        role = normalize_role(str(obj.get("role") or ""), object_id)
        bbox = bbox_from_record(obj)
        role_config = role_threshold(thresholds, role)
        issues: list[str] = []
        statuses: list[str] = []
        area = obj.get("text_box_area") if isinstance(obj.get("text_box_area"), (int, float)) else None
        density = obj.get("cjk_density") if isinstance(obj.get("cjk_density"), (int, float)) else None
        if bbox:
            if area is None:
                area = bbox["w"] * bbox["h"]
            if density is None and area > 0:
                density = cjk_weighted_count(text) / area
        else:
            issues.append("missing bbox")
            statuses.append(STATUS_NOT_RUN)

        metric_line_count = obj.get("estimated_rendered_line_count_v2")
        if not isinstance(metric_line_count, (int, float)):
            metric_line_count = obj.get("line_count_estimated")
        line_count = int(metric_line_count) if isinstance(metric_line_count, (int, float)) else explicit_line_count(text)
        density_status, density_issue = status_from_density(density, role_config, mapping)
        line_status, line_issue = status_from_line_count(line_count, role_config)
        if role == "page_number" and density_status == STATUS_FAIL and not profile.get("page_number_can_force_l2_fail"):
            density_status = STATUS_PARTIAL
            density_issue = "page number density warning; downgraded by profile"
        if profile.get("profile_id") == PROFILE_EXECUTION_PATH and role == "caption":
            max_lines = role_config.get("max_lines")
            if isinstance(max_lines, int) and line_count > max_lines and line_count <= max_lines + int(profile.get("execution_line_count_fail_extra_lines", 2)):
                line_status = STATUS_PARTIAL
                line_issue = "execution copy line count above concept max; profile treats as caveat"
        statuses.extend([density_status, line_status])
        if density_issue:
            issues.append(density_issue)
        if line_issue:
            issues.append(line_issue)

        font_size = obj.get("font_size_pt") or obj.get("font_size")
        missing_font_size = False
        if isinstance(font_size, (int, float)):
            min_size = role_config.get("min_size_pt")
            if isinstance(min_size, (int, float)) and float(font_size) < float(min_size):
                if role == "page_number" and not profile.get("page_number_can_force_l2_fail"):
                    statuses.append(STATUS_PARTIAL)
                    issues.append("font size below role minimum; page-number warning")
                else:
                    statuses.append(STATUS_FAIL if role_config.get("fail_if_below_min") else STATUS_PARTIAL)
                    issues.append("font size below role minimum")
            else:
                statuses.append(STATUS_PASS)
        else:
            missing_font_size = True
            statuses.append(STATUS_NOT_RUN)
            issues.append("missing_metric: font size not available in editability_map")

        if obj.get("role_minimum_violation") is True:
            if role in {"title", "claim", "proof_label"}:
                statuses.append(STATUS_FAIL)
            elif role == "page_number" and not profile.get("page_number_can_force_l2_fail"):
                statuses.append(STATUS_PARTIAL)
            else:
                statuses.append(STATUS_PARTIAL)
            if not any(issue.startswith("font size below role minimum") for issue in issues):
                issues.append("font size below role minimum")

        overflow_risk = obj.get("overflow_risk")
        if overflow_risk == "fail":
            statuses.append(STATUS_FAIL)
            issues.append("overflow risk fail")
        elif overflow_risk == "warning":
            statuses.append(STATUS_PARTIAL)
            issues.append("overflow risk warning")

        contrast_status = obj.get("contrast_status")
        if contrast_status == "fail":
            statuses.append(STATUS_PARTIAL)
            issues.append("contrast status fail")
        elif contrast_status == "warning":
            statuses.append(STATUS_PARTIAL)
            issues.append("contrast status warning")
        elif contrast_status == "manual_required":
            issues.append("contrast manual_required: image_or_texture or complex background")
        elif contrast_status == "not_run":
            issues.append("missing_metric: contrast not available")

        density_thresholds = as_dict(thresholds.get("density_thresholds"))
        if role == "claim":
            compression = as_dict(density_thresholds.get("claim_compression_risk"))
            if area is not None and area < float(compression.get("claim_area_below_square_inches", -1)):
                if cjk_weighted_count(text) > float(compression.get("claim_cjk_chars_above", 999999)):
                    statuses.append(STATUS_PARTIAL)
                    issues.append("claim compression risk")
        if role == "caption":
            crowding = as_dict(density_thresholds.get("caption_crowding_risk"))
            if area is not None and area < float(crowding.get("caption_area_below_square_inches", -1)):
                if cjk_weighted_count(text) > float(crowding.get("caption_cjk_chars_above", 999999)):
                    statuses.append(STATUS_PARTIAL)
                    issues.append("caption crowding risk")
            if obj.get("role_minimum_violation") is True and obj.get("text_density_level") in {"high", "severe"}:
                statuses.append(STATUS_FAIL)
                issues.append("caption below minimum with high density")

        status = combine_status(statuses)
        if missing_font_size and status == STATUS_PASS:
            status = STATUS_PARTIAL
        result[object_id] = {
            "role": role,
            "status": status,
            "severity": severity_for_status(status),
            "profile_treatment": "low_severity_consistency_warning" if role == "page_number" else "role_threshold",
            "metrics": {
                "text_box_area": round(area, 4) if area is not None else None,
                "cjk_char_count": cjk_weighted_count(text),
                "cjk_density": round(density, 4) if density is not None else None,
                "estimated_line_count": line_count,
                "estimated_rendered_line_count_v2": obj.get("estimated_rendered_line_count_v2"),
                "line_count_source": obj.get("line_count_source"),
                "font_size_pt": font_size,
                "font_weight": obj.get("font_weight"),
                "bold": obj.get("bold"),
                "paragraph_count": obj.get("paragraph_count"),
                "run_count": obj.get("run_count"),
                "has_mixed_font_sizes": obj.get("has_mixed_font_sizes"),
                "text_density_level": obj.get("text_density_level"),
                "role_minimum_violation": obj.get("role_minimum_violation"),
                "role_preferred_range_status": obj.get("role_preferred_range_status"),
                "overflow_risk": obj.get("overflow_risk"),
                "overflow_height_usage_ratio": obj.get("overflow_height_usage_ratio"),
                "contrast_ratio": obj.get("contrast_ratio"),
                "contrast_status": obj.get("contrast_status"),
                "text_color": obj.get("dominant_text_color") or obj.get("text_color"),
                "background_type": obj.get("background_type"),
                "background_color": obj.get("background_color"),
                "overlapping_texture_assets": obj.get("overlapping_texture_assets"),
            },
            "issues": issues,
            "rationale": "Mechanical typography checks only; preview-scale readability remains manual.",
            "recommended_action": "Provide font_size_pt in editability_map for strict size checks." if font_size is None else "Review issues before L2 pass.",
        }
    return result


def binding_score(objects: list[dict[str, Any]], elements: dict[str, dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    binding_mode = str(profile.get("binding_mode") or "strict_element_first")
    for obj in objects:
        object_id = str(obj.get("object_id") or obj.get("id") or "unknown")
        role = normalize_role(str(obj.get("role") or ""), object_id)
        bound_ids = as_list(obj.get("bound_element_ids"))
        missing = [item for item in bound_ids if item not in elements]
        required_notes: list[str] = []
        if binding_mode == "strict_element_first" and role == "proof_label":
            has_curve = any(str(item).startswith("reasoning_curve") for item in bound_ids)
            has_dot = any(str(item).startswith("path_anchor_dot") for item in bound_ids)
            if not has_curve:
                required_notes.append("proof label missing reasoning_curve binding")
            if not has_dot:
                required_notes.append("proof label missing path_anchor_dot binding")
        if binding_mode == "strict_element_first" and role == "claim":
            if "clinical_position_node" not in bound_ids:
                required_notes.append("claim missing clinical_position_node binding")
            if "coordinate_rings" not in bound_ids:
                required_notes.append("claim missing coordinate_rings binding")
        if binding_mode == "strict_element_first" and role == "title" and "map_entry_axis" not in bound_ids:
            required_notes.append("title missing map_entry_axis binding")

        if missing:
            metadata_status = STATUS_FAIL
        elif required_notes:
            metadata_status = STATUS_FAIL
        elif not bound_ids and binding_mode == "strict_element_first":
            metadata_status = STATUS_FAIL
        elif not bound_ids:
            metadata_status = STATUS_PARTIAL
            required_notes.append("binding ids unavailable for selected profile; rendered relationship remains manual_required")
        elif binding_mode == "substrate_level_relationship_manual":
            metadata_status = STATUS_PARTIAL
            required_notes.append("substrate-level relationship cannot be reduced to element-first binding ids")
        else:
            metadata_status = STATUS_PASS
        result[object_id] = {
            "metadata_binding": metadata_status,
            "spatial_proximity": STATUS_NOT_RUN,
            "rendered_relationship": STATUS_MANUAL_REQUIRED,
            "binding_status": metadata_status if metadata_status == STATUS_FAIL else STATUS_MANUAL_REQUIRED,
            "profile_binding_mode": binding_mode,
            "bound_element_ids": bound_ids,
            "missing_element_ids": missing,
            "notes": required_notes,
        }
    return result


def geometry_score(objects: list[dict[str, Any]], elements: dict[str, dict[str, Any]], thresholds: dict[str, Any]) -> dict[str, Any]:
    proximity = as_dict(thresholds.get("proximity_binding_thresholds"))
    collision = as_dict(thresholds.get("collision_thresholds"))
    result: dict[str, Any] = {
        "text_curve_collision": {"status": STATUS_NOT_RUN, "checks": []},
        "text_node_collision": {"status": STATUS_NOT_RUN, "checks": []},
        "text_texture_readability_risk": {"status": "manual_required"},
        "caption_crowded": {"status": STATUS_NOT_RUN, "checks": []},
        "claim_compressed": {"status": STATUS_NOT_RUN, "checks": []},
        "proof_label_anchor_detached": {"status": STATUS_NOT_RUN, "checks": []},
        "visual_congestion": {"status": "manual_required"},
    }

    text_collisions: list[dict[str, Any]] = []
    obj_bboxes = [(str(obj.get("object_id") or obj.get("id")), bbox_from_record(obj)) for obj in objects]
    obj_bboxes = [(object_id, bbox) for object_id, bbox in obj_bboxes if bbox]
    for index, (left_id, left_bbox) in enumerate(obj_bboxes):
        for right_id, right_bbox in obj_bboxes[index + 1 :]:
            clearance = bbox_clearance(left_bbox, right_bbox)
            if bboxes_overlap(left_bbox, right_bbox) or clearance < float(as_dict(collision.get("text_vs_text")).get("warning_if_below_inches_for_strategy_or_concept", 0.12)):
                text_collisions.append({"objects": [left_id, right_id], "clearance_inches": round(clearance, 4)})
    result["text_vs_text"] = {
        "status": STATUS_PARTIAL if text_collisions else STATUS_PASS,
        "checks": text_collisions,
    }

    proof_checks: list[dict[str, Any]] = []
    curve_checks: list[dict[str, Any]] = []
    node_checks: list[dict[str, Any]] = []
    title_checks: list[dict[str, Any]] = []
    for obj in objects:
        object_id = str(obj.get("object_id") or obj.get("id") or "unknown")
        role = normalize_role(str(obj.get("role") or ""), object_id)
        bbox = bbox_from_record(obj)
        if not bbox:
            continue
        bound_ids = as_list(obj.get("bound_element_ids"))
        if role == "proof_label":
            for bound_id in bound_ids:
                element = elements.get(str(bound_id))
                if not element:
                    continue
                if str(bound_id).startswith("path_anchor_dot"):
                    center = as_dict(as_dict(element.get("geometry")).get("center"))
                    if center:
                        distance = point_to_bbox_edge_distance(center, bbox)
                        fail_at = float(as_dict(proximity.get("proof_label_to_anchor_dot")).get("fail_if_greater_than_inches", 0.9))
                        warn_at = float(as_dict(proximity.get("proof_label_to_anchor_dot")).get("warning_if_greater_than_inches", 0.65))
                        status = STATUS_FAIL if distance > fail_at else STATUS_PARTIAL if distance > warn_at else STATUS_PASS
                        proof_checks.append({"object_id": object_id, "anchor_dot": bound_id, "distance_inches": round(distance, 4), "status": status})
                if str(bound_id).startswith("reasoning_curve"):
                    distance = bbox_center_to_curve_distance(bbox, element)
                    if distance is not None:
                        fail_at = float(as_dict(proximity.get("proof_label_to_curve")).get("fail_if_greater_than_inches", 0.65))
                        warn_at = float(as_dict(proximity.get("proof_label_to_curve")).get("warning_if_greater_than_inches", 0.45))
                        status = STATUS_FAIL if distance > fail_at else STATUS_PARTIAL if distance > warn_at else STATUS_PASS
                        curve_checks.append({"object_id": object_id, "curve": bound_id, "distance_inches": round(distance, 4), "status": status})
        if role == "claim":
            node = node_bbox(elements, "clinical_position_node")
            rings = node_bbox(elements, "coordinate_rings")
            for target_id, target_bbox in (("clinical_position_node", node), ("coordinate_rings", rings)):
                if target_bbox:
                    distance = bbox_to_bbox_edge_distance(bbox, target_bbox)
                    overlaps = bboxes_overlap(bbox, target_bbox)
                    fail_at = float(as_dict(proximity.get("claim_to_node_or_rings")).get("fail_if_greater_than_inches", 0.9))
                    warn_at = float(as_dict(proximity.get("claim_to_node_or_rings")).get("warning_if_greater_than_inches", 0.6))
                    status = STATUS_FAIL if overlaps or distance > fail_at else STATUS_PARTIAL if distance > warn_at else STATUS_PASS
                    node_checks.append({"object_id": object_id, "target": target_id, "edge_distance_inches": round(distance, 4), "overlap": overlaps, "status": status})
        if role == "title":
            axis = elements.get("map_entry_axis")
            points = as_dict(as_dict(axis or {}).get("geometry")).get("path_points")
            if isinstance(points, list) and points:
                axis_y = min(float(point["y"]) for point in points if isinstance(point, dict) and "y" in point)
                bottom = bbox["y"] + bbox["h"]
                distance = abs(axis_y - bottom)
                fail_at = float(as_dict(proximity.get("title_to_map_entry_axis")).get("fail_if_greater_than_inches", 0.85))
                warn_at = float(as_dict(proximity.get("title_to_map_entry_axis")).get("warning_if_greater_than_inches", 0.55))
                status = STATUS_FAIL if distance > fail_at else STATUS_PARTIAL if distance > warn_at else STATUS_PASS
                title_checks.append({"object_id": object_id, "axis": "map_entry_axis", "vertical_distance_inches": round(distance, 4), "status": status})

    result["proof_label_anchor_detached"] = {"status": combine_status([item["status"] for item in proof_checks] or [STATUS_NOT_RUN]), "checks": proof_checks}
    result["text_curve_collision"] = {"status": combine_status([item["status"] for item in curve_checks] or [STATUS_NOT_RUN]), "checks": curve_checks}
    result["text_node_collision"] = {"status": combine_status([item["status"] for item in node_checks] or [STATUS_NOT_RUN]), "checks": node_checks}
    result["title_axis_proximity"] = {"status": combine_status([item["status"] for item in title_checks] or [STATUS_NOT_RUN]), "checks": title_checks}
    return result


def element_weight_score(assembly_plan: Any, thresholds: dict[str, Any]) -> dict[str, Any]:
    plan = as_dict(assembly_plan)
    elements = collect_elements(plan)
    weights = as_dict(thresholds.get("element_weight_thresholds"))
    result: dict[str, Any] = {}

    local_assets = as_dict(plan.get("selected_local_assets"))
    if "left_complexity_field" in local_assets:
        opacity = local_assets["left_complexity_field"].get("opacity")
        cfg = as_dict(weights.get("left_complexity_field"))
        status = STATUS_PASS
        issues: list[str] = []
        if isinstance(opacity, (int, float)):
            if opacity < float(cfg.get("warning_if_below", -1)) or opacity > float(cfg.get("warning_if_above", 999)):
                status = STATUS_PARTIAL
                issues.append("opacity outside preferred planning range")
        else:
            status = STATUS_NOT_RUN
            issues.append("missing opacity")
        result["left_complexity_field"] = {"status": status, "opacity": opacity, "issues": issues}

    curve_statuses = []
    curve_checks = []
    cfg_curve = as_dict(weights.get("reasoning_curve"))
    for element_id, element in elements.items():
        if not element_id.startswith("reasoning_curve"):
            continue
        width = element.get("stroke_width_pt")
        opacity = element.get("opacity")
        status = STATUS_PASS
        issues: list[str] = []
        if isinstance(width, (int, float)) and width < float(cfg_curve.get("warning_if_width_below_pt", 1.0)):
            status = STATUS_PARTIAL
            issues.append("stroke width below warning threshold")
        if isinstance(opacity, (int, float)) and opacity < float(cfg_curve.get("warning_if_opacity_below", 0.55)):
            status = STATUS_PARTIAL
            issues.append("opacity below warning threshold")
        curve_statuses.append(status)
        curve_checks.append({"element_id": element_id, "stroke_width_pt": width, "opacity": opacity, "status": status, "issues": issues})
    result["reasoning_curves"] = {"status": combine_status(curve_statuses or [STATUS_NOT_RUN]), "checks": curve_checks}

    rings = elements.get("coordinate_rings")
    cfg_rings = as_dict(weights.get("coordinate_rings"))
    if rings:
        opacity = rings.get("opacity")
        width = rings.get("stroke_width_pt")
        status = STATUS_PASS
        issues = []
        if isinstance(opacity, (int, float)) and opacity > float(cfg_rings.get("warning_if_opacity_above", 0.42)):
            status = STATUS_PARTIAL
            issues.append("rings opacity above warning threshold")
        result["coordinate_rings"] = {"status": status, "opacity": opacity, "stroke_width_pt": width, "issues": issues}
    else:
        result["coordinate_rings"] = {"status": STATUS_NOT_RUN, "issues": ["coordinate_rings missing"]}

    node = elements.get("clinical_position_node")
    result["clinical_position_node"] = {
        "status": STATUS_PASS if node else STATUS_NOT_RUN,
        "notes": "Mechanical presence only; focal authority remains manual.",
    }

    dot_checks = []
    cfg_dot = as_dict(weights.get("anchor_dot"))
    for element_id, element in elements.items():
        if not element_id.startswith("path_anchor_dot"):
            continue
        radius = as_dict(element.get("geometry")).get("radius")
        status = STATUS_PASS
        issues = []
        if isinstance(radius, (int, float)):
            if radius < float(cfg_dot.get("warning_if_below_inches", 0.025)) or radius > float(cfg_dot.get("warning_if_above_inches", 0.075)):
                status = STATUS_PARTIAL
                issues.append("radius outside warning thresholds")
        else:
            status = STATUS_NOT_RUN
            issues.append("missing radius")
        dot_checks.append({"element_id": element_id, "radius": radius, "status": status, "issues": issues})
    result["anchor_dots"] = {"status": combine_status([item["status"] for item in dot_checks] or [STATUS_NOT_RUN]), "checks": dot_checks}
    result["editable_text"] = {"status": "manual_required", "notes": "Visual authority of editable text requires preview review."}
    return result


def route_asset_compliance(assembly_plan: Any, media_check: Any, package_inspection: Any, no_shadow_scan: Any) -> dict[str, Any]:
    route_info = extract_route(assembly_plan, strict=False)
    route_id = route_info.get("canonical_route")
    media = as_dict(media_check)
    checks: dict[str, Any] = {
        "route_id": route_id,
        "route_provenance": route_info,
        "element_first_route_status": STATUS_NOT_RUN,
        "media_asset_check": STATUS_NOT_RUN,
        "package_inspection": STATUS_NOT_RUN,
        "no_shadow_scan": STATUS_NOT_RUN,
    }
    if route_id == "element_asset_hybrid":
        no_16_9 = media.get("no_16_9_generated_background")
        if no_16_9 is True:
            checks["element_first_route_status"] = STATUS_PASS
            checks["media_asset_check"] = STATUS_PASS
        elif media:
            checks["element_first_route_status"] = STATUS_FAIL
            checks["media_asset_check"] = STATUS_FAIL
        else:
            checks["element_first_route_status"] = STATUS_NOT_RUN
    if media.get("media"):
        non_rgba = [item for item in media["media"] if item.get("mode") != "RGBA"]
        checks["local_assets_rgba"] = STATUS_FAIL if non_rgba else STATUS_PASS
        checks["non_rgba_assets"] = non_rgba
    else:
        checks["local_assets_rgba"] = STATUS_NOT_RUN

    pkg = as_dict(package_inspection)
    if pkg:
        checks["package_inspection"] = STATUS_PASS if pkg.get("result") == "PASS" and not pkg.get("errors") else STATUS_FAIL
        checks["package_errors"] = pkg.get("errors", [])
        checks["package_warnings"] = pkg.get("warnings", [])
    scan = as_dict(no_shadow_scan)
    if scan:
        checks["no_shadow_scan"] = STATUS_PASS if scan.get("pass") is True else STATUS_FAIL
        checks["ooxml_effect_counts"] = scan.get("counts", {})
    return checks


def build_canvas_composition(preview: str | None) -> dict[str, Any]:
    manual = {
        "status": "manual_required",
        "preview_path": preview,
        "notes": "Requires rendered preview review; not mechanically scored in Phase 1.",
    }
    return {
        "left_zone_function": manual,
        "middle_path_field": manual,
        "right_focus_zone": manual,
        "far_right_continuation_zone": manual,
        "bottom_caption_zone": manual,
        "visual_center_of_gravity": manual,
        "negative_space_function": manual,
    }


def overall_status(
    typography: dict[str, Any],
    visual_binding: dict[str, Any],
    collision_density: dict[str, Any],
    compliance: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    l1_inputs = [
        compliance.get("package_inspection"),
        compliance.get("no_shadow_scan"),
        compliance.get("media_asset_check"),
        compliance.get("local_assets_rgba"),
    ]
    l1 = STATUS_PASS if all(item == STATUS_PASS for item in l1_inputs if item != STATUS_NOT_RUN) else STATUS_PARTIAL
    if STATUS_FAIL in l1_inputs:
        l1 = STATUS_FAIL

    typography_statuses = [as_dict(item).get("status") for item in typography.values()]
    binding_statuses = [as_dict(item).get("metadata_binding") for item in visual_binding.values()]
    collision_statuses = [as_dict(item).get("status") for item in collision_density.values() if isinstance(item, dict)]
    l2_inputs = [status for status in typography_statuses + binding_statuses + collision_statuses if isinstance(status, str)]
    l2 = combine_status(l2_inputs)
    if l2 == STATUS_PASS:
        l2 = STATUS_PARTIAL
    if STATUS_FAIL in binding_statuses:
        l2 = STATUS_FAIL

    return {
        "l1_mechanical_status": l1,
        "element_first_route_status": compliance.get("element_first_route_status", STATUS_NOT_RUN),
        "l2_layout_status": l2,
        "l3_creative_readiness": "manual_required" if l2 != STATUS_FAIL else "not_ready",
        "can_continue_to_next_version": False,
        "reason": (
            f"Profile-aware mechanical scorecard using {profile.get('profile_id')}; "
            "rendered visual binding and composition remain manual."
        ),
        "selected_profile": profile.get("profile_id"),
        "profile_version": profile.get("profile_version"),
        "passthrough": compliance,
    }


def build_scorecard(args: argparse.Namespace) -> dict[str, Any]:
    thresholds, thresholds_status = load_json(args.thresholds, required=True)
    editability_metrics, metrics_status = load_json(args.editability_metrics)
    editability_map, editability_status = load_json(args.editability_map, required=not bool(args.editability_metrics))
    assembly_plan, assembly_status = load_json(args.assembly_plan, required=True)
    evc, evc_status = load_json(args.evc, required=True)
    media_check, media_status = load_json(args.media_check)
    package_inspection, package_status = load_json(args.package_inspection)
    no_shadow_scan, no_shadow_status = load_json(args.no_shadow_scan)
    human_notes = None
    human_notes_status = {"status": STATUS_NOT_RUN, "warning": "input path not provided"}
    if args.human_notes:
        path = Path(args.human_notes)
        if path.exists():
            human_notes = path.read_text(encoding="utf-8")
            human_notes_status = {"status": STATUS_PASS, "path": str(path)}
        else:
            human_notes_status = {"status": STATUS_NOT_RUN, "warning": f"input file does not exist: {path}"}

    thresholds = as_dict(thresholds)
    assembly_plan = as_dict(assembly_plan)
    editability_source = editability_metrics if editability_metrics is not None else editability_map
    objects = collect_editable_objects(editability_source, evc, assembly_plan)
    profile = select_profile(args.profile, assembly_plan, objects)
    elements = collect_elements(assembly_plan)
    typography = typography_score(objects, thresholds, profile)
    binding = binding_score(objects, elements, profile)
    collision_density = geometry_score(objects, elements, thresholds)
    element_weight = element_weight_score(assembly_plan, thresholds)
    compliance = route_asset_compliance(assembly_plan, media_check, package_inspection, no_shadow_scan)
    overall = overall_status(typography, binding, collision_density, compliance, profile)

    return {
        "metadata": {
            "page": as_dict(assembly_plan.get("route")).get("page"),
            "route": as_dict(assembly_plan.get("route")).get("route_id"),
            "threshold_profile": thresholds.get("threshold_profile"),
            "selected_profile": profile.get("profile_id"),
            "profile_reason": profile.get("profile_reason"),
            "profile_version": profile.get("profile_version"),
            "profile_requested": profile.get("profile_requested"),
            "profile_route_source": profile.get("profile_route_source"),
            "profile_route_raw": profile.get("profile_route_raw"),
            "profile_route_normalized": profile.get("profile_route_normalized"),
            "profile_selection_mode": profile.get("profile_selection_mode"),
            "profile_precedence_decision": profile.get("profile_precedence_decision"),
            "profile_conflict": profile.get("profile_conflict"),
            "profile_conflict_reason": profile.get("profile_conflict_reason"),
            "status": "generated_scorecard_only",
            "source_pptx": as_dict(package_inspection).get("pptx"),
            "preview_path": args.preview,
            "inputs": {
                "thresholds": thresholds_status,
                "editability_metrics": metrics_status,
                "editability_map": editability_status,
                "assembly_plan": assembly_status,
                "evc": evc_status,
                "media_check": media_status,
                "package_inspection": package_status,
                "no_shadow_scan": no_shadow_status,
                "human_notes": human_notes_status,
            },
        },
        "typography_scale": typography,
        "canvas_composition": build_canvas_composition(args.preview),
        "element_weight_budget": element_weight,
        "visual_binding": binding,
        "collision_density": collision_density,
        "overall": overall,
        "model_feedback": {
            "mechanized_checks": [
                "text box area",
                "weighted CJK character density",
                "explicit line count",
                "metadata element binding integrity",
                "proof label to anchor dot distance",
                "proof label to curve distance",
                "claim to node/rings distance",
                "title to map_entry_axis distance",
                "text bbox overlap",
                "element-first media compliance",
                "package/no-shadow passthrough",
            ],
            "manual_required_checks": [
                "rendered visual binding",
                "right-side negative-space function",
                "curves read as skeleton rather than flowchart",
                "node/rings read as coordinate lock rather than target UI",
                "title visual authority",
                "proposal-grade layout tension",
            ],
            "human_notes_present": human_notes is not None,
            "phase_boundary": "Independent assisted scorecard generator only; not validator integration and not a hard production gate.",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--editability-map", help="Fallback editability map JSON path.")
    parser.add_argument(
        "--editability-metrics",
        help="Editability metrics JSON path. When provided, this is preferred over --editability-map.",
    )
    parser.add_argument("--assembly-plan", required=True)
    parser.add_argument("--evc", required=True)
    parser.add_argument("--media-check")
    parser.add_argument("--package-inspection")
    parser.add_argument("--no-shadow-scan")
    parser.add_argument("--thresholds", required=True)
    parser.add_argument(
        "--profile",
        choices=PROFILE_CHOICES,
        default=PROFILE_AUTO,
        help="Layout Intelligence scoring profile. Use auto unless a calibrated route/page profile is known.",
    )
    parser.add_argument("--preview")
    parser.add_argument("--human-notes")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.editability_metrics:
        metrics_path = Path(args.editability_metrics)
        if not metrics_path.exists():
            parser.error(f"--editability-metrics file does not exist: {metrics_path}")
        try:
            json.loads(metrics_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - argparse should show a concise CLI error
            parser.error(f"--editability-metrics must be valid JSON: {metrics_path} ({exc})")

    return args


def main() -> int:
    args = parse_args()
    scorecard = build_scorecard(args)
    output = Path(args.output)
    write_json(output, scorecard)
    print(f"Wrote Layout Intelligence scorecard: {output}")
    print(f"L1: {scorecard['overall']['l1_mechanical_status']}")
    print(f"L2: {scorecard['overall']['l2_layout_status']}")
    print(f"L3: {scorecard['overall']['l3_creative_readiness']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
