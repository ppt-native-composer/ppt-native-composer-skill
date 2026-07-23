#!/usr/bin/env python3
"""Small, audited OOXML helpers for capabilities not exposed by python-pptx.

Only DrawingML alpha on an existing solid RGB/scheme color is supported here.
Every helper removes prior alpha nodes before writing one canonical node so a
PPTX never accumulates conflicting transparency instructions.
"""

from __future__ import annotations

from typing import Any

from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement


ALPHA_MIN = 0
ALPHA_MAX = 100000


class OoxmlCapabilityError(ValueError):
    """Raised when a requested OOXML capability cannot be applied safely."""


def alpha_value(opacity: Any) -> int:
    try:
        value = float(opacity)
    except (TypeError, ValueError) as exc:
        raise OoxmlCapabilityError(f"opacity must be numeric, got {opacity!r}") from exc
    if not 0.0 <= value <= 1.0:
        raise OoxmlCapabilityError(f"opacity must be within [0, 1], got {value}")
    return int(round(value * ALPHA_MAX))


def _solid_color(fill_parent):
    solid_fill = fill_parent.find(qn("a:solidFill"))
    if solid_fill is None:
        raise OoxmlCapabilityError("solidFill is required before alpha can be applied")
    for child in solid_fill:
        if child.tag in {qn("a:srgbClr"), qn("a:schemeClr"), qn("a:sysClr")}:
            return child
    raise OoxmlCapabilityError("solidFill does not contain a supported color node")


def set_alpha_on_fill_parent(fill_parent, opacity: Any) -> int:
    """Set exactly one DrawingML alpha node on an existing solid fill."""
    color = _solid_color(fill_parent)
    for child in list(color):
        if child.tag == qn("a:alpha"):
            color.remove(child)
    alpha = OxmlElement("a:alpha")
    value = alpha_value(opacity)
    alpha.set("val", str(value))
    color.append(alpha)
    return value


def set_shape_fill_opacity(shape, opacity: Any) -> int:
    return set_alpha_on_fill_parent(shape.fill._xPr, opacity)


def set_shape_line_opacity(shape, opacity: Any) -> int:
    line = shape.line._ln
    if line is None:
        raise OoxmlCapabilityError("line must exist before alpha can be applied")
    return set_alpha_on_fill_parent(line, opacity)


def set_font_opacity(run, opacity: Any) -> int:
    r_pr = run._r.get_or_add_rPr()
    return set_alpha_on_fill_parent(r_pr, opacity)


def alpha_nodes(xml: bytes) -> list[int]:
    """Inspection helper used by tests and round-trip evidence."""
    import re

    return [int(value) for value in re.findall(rb"<a:alpha val=\"(\d+)\"", xml)]
