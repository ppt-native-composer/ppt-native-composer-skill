from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from route_normalization import (  # noqa: E402
    CANONICAL_ROUTES,
    RouteNormalizationError,
    extract_route,
    normalize_route,
    normalize_route_record,
)


def test_legacy_element_first_normalizes_to_canonical() -> None:
    result = normalize_route("element_first_composition")
    assert result["canonical_route"] == "element_asset_hybrid"
    assert result["legacy_alias_used"] is True


def test_canonical_routes_round_trip() -> None:
    for route in CANONICAL_ROUTES:
        assert normalize_route(route)["canonical_route"] == route


def test_unknown_route_fails_in_strict_mode() -> None:
    with pytest.raises(RouteNormalizationError):
        normalize_route("s01_magic_route")


def test_unknown_and_missing_route_are_reported_without_throwing_in_audit_mode() -> None:
    unknown = normalize_route("future_route", strict=False)
    assert unknown["normalization_source"] == "unknown"
    missing = extract_route({}, strict=False)
    assert missing["normalization_source"] == "missing"
    assert missing["canonical_route"] is None


def test_extract_route_uses_document_fields_not_object_prefixes() -> None:
    result = extract_route({"route": {"route_id": "element_first_composition"}, "objects": [{"id": "s03_fake"}]})
    assert result["canonical_route"] == "element_asset_hybrid"
    assert result["source_path"] == "route.route_id"


def test_new_route_record_writes_canonical_value() -> None:
    record = normalize_route_record({"selected_route": "full_substrate"})
    assert record["selected_route"] == "full_substrate_hybrid"
    assert record["route_provenance"]["raw_route"] == "full_substrate"
