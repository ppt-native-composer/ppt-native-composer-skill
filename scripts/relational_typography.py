#!/usr/bin/env python3
"""Resolve relational text bindings into deterministic native PPT geometry."""

from __future__ import annotations

import math
from typing import Any

SUPPORTED_BINDINGS = {"visual_focus", "path", "node", "asset_region", "asset_edge", "composition_axis", "free"}
ATTACHMENTS = {"start", "middle", "end", "before", "after", "inside", "outside", "tangent", "normal"}
ORIENTATIONS = {"horizontal", "tangent", "normal", "fixed_angle"}


def _point(value: Any) -> dict[str, float]:
    if not isinstance(value, dict) or "x" not in value or "y" not in value:
        raise ValueError("relational target point requires x/y")
    return {"x": float(value["x"]), "y": float(value["y"])}


def _box(value: Any) -> dict[str, float]:
    if not isinstance(value, dict) or not all(key in value for key in ("x", "y", "w", "h")):
        raise ValueError("relational target geometry requires x/y/w/h")
    return {key: float(value[key]) for key in ("x", "y", "w", "h")}


def _lerp(a: dict[str, float], b: dict[str, float], t: float) -> dict[str, float]:
    return {"x": a["x"] + (b["x"] - a["x"]) * t, "y": a["y"] + (b["y"] - a["y"]) * t}


def _sample_path(points: list[Any], t: float) -> tuple[dict[str, float], dict[str, float]]:
    clean = [_point(item) for item in points]
    if len(clean) < 2:
        raise ValueError("path binding requires at least two path points")
    t = max(0.0, min(1.0, float(t)))
    scaled = t * (len(clean) - 1)
    index = min(len(clean) - 2, int(math.floor(scaled)))
    local = scaled - index
    anchor = _lerp(clean[index], clean[index + 1], local)
    tangent = {"x": clean[index + 1]["x"] - clean[index]["x"], "y": clean[index + 1]["y"] - clean[index]["y"]}
    length = math.hypot(tangent["x"], tangent["y"]) or 1.0
    return anchor, {"x": tangent["x"] / length, "y": tangent["y"] / length}


def _target_geometry(target: dict[str, Any]) -> dict[str, float]:
    geometry = target.get("geometry") or target.get("bbox")
    if geometry:
        return _box(geometry)
    center = target.get("center")
    if center:
        point = _point(center)
        size = target.get("size") or {"w": 0.1, "h": 0.1}
        width, height = float(size.get("w", 0.1)), float(size.get("h", 0.1))
        return {"x": point["x"] - width / 2, "y": point["y"] - height / 2, "w": width, "h": height}
    points = target.get("path_points") or target.get("bezier_points")
    if points:
        clean = [_point(item) for item in points]
        xs, ys = [point["x"] for point in clean], [point["y"] for point in clean]
        return {"x": min(xs), "y": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys)}
    raise ValueError("relational target requires geometry, bbox, or center")


def resolve_binding(item: dict[str, Any], visual_targets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Resolve one text object and return geometry plus binding evidence.

    A declared ``fallback_behavior=use_declared_zone`` is the only permitted
    fallback. Missing or unsupported target data otherwise raises.
    """
    binding = item.get("relational_binding")
    declared = item.get("zone") or item.get("geometry")
    if not isinstance(binding, dict):
        geometry = _box(declared)
        return {"geometry": geometry, "evidence": {"requested_binding": None, "resolved_target": None, "resolved_anchor": None, "applied_geometry": geometry, "deviation": {"x": 0.0, "y": 0.0}, "fallback": None, "warning": "no relational_binding declared; legacy free geometry used", "unsupported_behavior": None}}
    binding_type = str(binding.get("binding_type") or "").strip()
    target_id = str(binding.get("binding_target_id") or "").strip()
    attachment = str(binding.get("attachment") or "middle").strip()
    orientation = str(binding.get("orientation") or "horizontal").strip()
    if binding_type not in SUPPORTED_BINDINGS:
        raise ValueError(f"unsupported relational binding_type: {binding_type}")
    if attachment not in ATTACHMENTS:
        raise ValueError(f"unsupported relational attachment: {attachment}")
    if orientation not in ORIENTATIONS:
        raise ValueError(f"unsupported relational orientation: {orientation}")
    if binding_type == "free":
        geometry = _box(declared)
        return {"geometry": geometry, "evidence": {"requested_binding": binding, "resolved_target": None, "resolved_anchor": None, "applied_geometry": geometry, "deviation": {"x": 0.0, "y": 0.0}, "fallback": None, "warning": None, "unsupported_behavior": None}}
    targets = {str(target.get("id")): target for target in (visual_targets or []) if isinstance(target, dict) and target.get("id")}
    target = targets.get(target_id)
    if target is None:
        if binding.get("fallback_behavior") == "use_declared_zone" and declared:
            geometry = _box(declared)
            return {"geometry": geometry, "evidence": {"requested_binding": binding, "resolved_target": None, "resolved_anchor": None, "applied_geometry": geometry, "deviation": {"x": 0.0, "y": 0.0}, "fallback": "use_declared_zone", "warning": f"binding target missing; explicit fallback used: {target_id}", "unsupported_behavior": None}}
        raise ValueError(f"relational binding target not found: {target_id}")
    box = _target_geometry(target)
    text_box = _box(declared)
    offset = binding.get("offset") or {}
    offset_x, offset_y = float(offset.get("x", 0.0)), float(offset.get("y", 0.0))
    t_value = binding.get("path_position")
    if t_value is None:
        t_value = {"start": 0.0, "middle": 0.5, "end": 1.0}.get(attachment, 0.5)
    t_value = max(0.0, min(1.0, float(t_value)))
    path_points = target.get("path_points") or target.get("bezier_points")
    if binding_type in {"path", "composition_axis"}:
        if not path_points:
            raise ValueError(f"binding target {target_id} has no path_points")
        anchor, tangent = _sample_path(path_points, t_value)
        normal = {"x": -tangent["y"], "y": tangent["x"]}
        if attachment in {"before", "after", "outside", "normal"}:
            direction = normal if attachment in {"before", "normal"} else {"x": -normal["x"], "y": -normal["y"]}
            distance = max(0.08, text_box["h"] / 2)
            anchor = {"x": anchor["x"] + direction["x"] * distance, "y": anchor["y"] + direction["y"] * distance}
        if attachment == "start":
            geometry = {"x": anchor["x"] + offset_x, "y": anchor["y"] - text_box["h"] * 0.5 + offset_y, "w": text_box["w"], "h": text_box["h"]}
        else:
            geometry = {"x": anchor["x"] - text_box["w"] / 2 + offset_x, "y": anchor["y"] - text_box["h"] / 2 + offset_y, "w": text_box["w"], "h": text_box["h"]}
        rotation = math.degrees(math.atan2(tangent["y"], tangent["x"])) if orientation == "tangent" else math.degrees(math.atan2(normal["y"], normal["x"])) if orientation == "normal" else float(binding.get("fixed_angle") or 0.0)
    else:
        anchor = {"x": box["x"] + box["w"] / 2, "y": box["y"] + box["h"] / 2}
        side = str(binding.get("preferred_side") or ("right" if attachment in {"after", "outside"} else "left" if attachment == "before" else "above" if attachment == "start" else "below" if attachment == "end" else "right"))
        gap = float(binding.get("minimum_clearance") or 0.12)
        if side == "left":
            x, y = box["x"] - gap - text_box["w"], anchor["y"] - text_box["h"] / 2
        elif side == "above":
            x, y = anchor["x"] - text_box["w"] / 2, box["y"] - gap - text_box["h"]
        elif side == "below":
            x, y = anchor["x"] - text_box["w"] / 2, box["y"] + box["h"] + gap
        else:
            x, y = box["x"] + box["w"] + gap, anchor["y"] - text_box["h"] / 2
        if attachment == "inside":
            x, y = anchor["x"] - text_box["w"] / 2, anchor["y"] - text_box["h"] / 2
        geometry = {"x": x + offset_x, "y": y + offset_y, "w": text_box["w"], "h": text_box["h"]}
        rotation = float(binding.get("fixed_angle") or 0.0)
    return {"geometry": geometry, "rotation": rotation, "evidence": {"requested_binding": binding, "resolved_target": {"id": target_id, "type": target.get("type"), "geometry": box}, "resolved_anchor": {"x": anchor["x"], "y": anchor["y"], "path_position": t_value, "orientation": orientation}, "applied_geometry": geometry, "deviation": {"x": round(geometry["x"] - text_box["x"], 4), "y": round(geometry["y"] - text_box["y"], 4)}, "fallback": None, "warning": None, "unsupported_behavior": None}}
