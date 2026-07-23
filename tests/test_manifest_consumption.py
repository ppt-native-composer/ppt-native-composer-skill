from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_runtime_case import RuntimeCaseRunner
from runtime_test_support import create_runtime_case


def test_manifest_inputs_are_snapshotted_and_reported(tmp_path: Path) -> None:
    _, manifest = create_runtime_case(tmp_path)
    summary = RuntimeCaseRunner(manifest).run()
    assert summary["overall_status"] == "success"
    report = Path(summary["stages"][1]["artifacts"][-1]["path"])
    entries = json.loads(report.read_text(encoding="utf-8"))["entries"]
    fields = {entry["manifest_field"] for entry in entries if entry["consumed"]}
    assert {"inputs.blueprint", "inputs.design_intent", "inputs.route", "inputs.evc", "inputs.asset_registry", "inputs.assets_dir", "output.root", "runtime_options"} <= fields
