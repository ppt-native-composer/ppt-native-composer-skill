from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from score_layout_intelligence import (  # noqa: E402
    PROFILE_ELEMENT_FIRST,
    PROFILE_EXECUTION_PATH,
    PROFILE_FULL_SUBSTRATE,
    select_profile,
)


def test_profile_selection_uses_normalized_route_not_object_prefix() -> None:
    element = select_profile("auto", {"route": {"route_id": "element_first_composition"}}, [{"object_id": "s03_fake"}])
    assert element["profile_id"] == PROFILE_ELEMENT_FIRST
    execution = select_profile("auto", {"route": {"route_id": "template_native_plus_skin"}}, [{"object_id": "s01_fake"}])
    assert execution["profile_id"] == PROFILE_EXECUTION_PATH
    substrate = select_profile("auto", {"route": {"route_id": "full_substrate"}}, [{"object_id": "s02_fake"}])
    assert substrate["profile_id"] == PROFILE_FULL_SUBSTRATE
