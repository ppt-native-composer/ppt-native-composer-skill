from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_runtime_capability_manifest_has_complete_stable_contract() -> None:
    payload = json.loads((ROOT / "runtime_capability_manifest.json").read_text(encoding="utf-8"))
    statuses = set(payload["status_enum"])
    capabilities = payload["capabilities"]
    assert payload["manifest_version"].startswith("phase5_")
    assert len({item["capability_id"] for item in capabilities}) == len(capabilities)
    required = {"capability_id", "capability_group", "status", "supported_routes", "supported_object_types", "requested_field", "applied_behavior", "fallback_behavior", "warning_behavior", "unsupported_behavior", "evidence", "tests", "known_limitations", "version_introduced", "version_verified"}
    for capability in capabilities:
        assert capability["status"] in statuses
        assert required <= set(capability)
