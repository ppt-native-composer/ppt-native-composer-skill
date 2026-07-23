from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from assembly_pipeline import assemble_pipeline  # noqa: E402
from test_assembly_integration import prepare_project  # noqa: E402


def test_pipeline_boundary_preserves_legacy_assembly_behavior(tmp_path: Path) -> None:
    project, blueprint = prepare_project(tmp_path)
    output = project / "pipeline.pptx"
    result = assemble_pipeline(blueprint, output, project)
    assert output.exists()
    assert Path(result["editability_map_v2"]).exists()
