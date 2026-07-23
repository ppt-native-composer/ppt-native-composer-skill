from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_runtime_case import RuntimeCaseRunner
from runtime_test_support import create_runtime_case


def test_runs_are_immutable_and_have_required_evidence(tmp_path: Path) -> None:
    project, manifest = create_runtime_case(tmp_path)
    first = RuntimeCaseRunner(manifest).run()
    second = RuntimeCaseRunner(manifest).run()
    assert first["run_id"] != second["run_id"]
    roots = sorted((project / "runtime_case" / "runs").iterdir())
    assert len(roots) == 2
    for root in roots:
        for name in ("resolved_manifest.json", "manifest_consumption_report.json", "toolchain_fingerprint.json", "dependency_graph.json", "run_state.json", "run_summary.json", "artifact_hash_manifest.json", "stage_events.jsonl"):
            assert (root / name).exists(), name
