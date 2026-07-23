from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_runtime_case import RuntimeCaseRunner
from runtime_test_support import create_runtime_case


def test_invalid_source_fails_before_publish_and_blocks_downstream(tmp_path: Path) -> None:
    project, manifest = create_runtime_case(tmp_path)
    invalid = project / "invalid.pptx"
    invalid.write_text("not a presentation", encoding="utf-8")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["source"]["source_pptx"] = str(invalid)
    manifest.write_text(json.dumps(data), encoding="utf-8")
    summary = RuntimeCaseRunner(manifest).run()
    assert summary["overall_status"] == "failed"
    assert "resolve_source" in summary["failed_stages"]
    assert not list((project / "runtime_case" / "runs" / summary["run_id"] / "artifacts").glob("*.pptx"))
    after = [item for item in summary["stages"] if item["stage_id"] in {"runtime_evidence", "package_inspection", "no_shadow_scan"}]
    assert all(item["status"] == "skipped" for item in after)
