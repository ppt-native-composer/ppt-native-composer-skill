from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from assembly_pipeline import assemble_pipeline
from runtime_test_support import create_runtime_case


def test_pipeline_writes_atomic_reopenable_presentation(tmp_path: Path) -> None:
    project, manifest = create_runtime_case(tmp_path)
    del manifest
    output = project / "pipeline.pptx"
    result = assemble_pipeline(
        project / "blueprint.json", output, project,
        route_input=project / "route.json", design_intent_input=project / "design_intent.json",
    )
    assert output.exists()
    assert result["saved_presentation"]["slide_count"] == 1
    assert not output.with_suffix(".pptx.tmp").exists()
