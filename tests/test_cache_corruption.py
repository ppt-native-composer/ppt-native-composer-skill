from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_runtime_case import RuntimeCaseRunner
from runtime_test_support import create_runtime_case


def test_corrupted_cached_pptx_forces_reassembly(tmp_path: Path) -> None:
    _, manifest = create_runtime_case(tmp_path)
    cold = RuntimeCaseRunner(manifest).run()
    assembly = next(stage for stage in cold["stages"] if stage["stage_id"] == "assemble_pptx")
    pptx = Path(assembly["artifacts"][0]["path"])
    pptx.write_bytes(b"corrupt")
    resumed = RuntimeCaseRunner(manifest).run()
    stage = next(item for item in resumed["stages"] if item["stage_id"] == "assemble_pptx")
    assert stage["status"] == "executed"
    assert "cached artifact" in stage["cache_decision"]["reason"]
