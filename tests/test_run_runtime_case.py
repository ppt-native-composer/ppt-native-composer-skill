from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_runtime_case as runner_module  # noqa: E402
from run_runtime_case import RequiredStageError, RuntimeCaseRunner, read_json  # noqa: E402
from test_assembly_integration import prepare_project, runtime_blueprint  # noqa: E402


def make_manifest(tmp_path: Path, *, preview: bool = False, advisory: bool = False) -> Path:
    project, blueprint_path = prepare_project(tmp_path)
    blueprint = runtime_blueprint()
    evc = blueprint["slides"][0].pop("editable_visual_composition")
    blueprint_path.write_text(json.dumps(blueprint, ensure_ascii=False), encoding="utf-8")
    evc_path = project / "evc.json"
    evc_path.write_text(json.dumps(evc, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "manifest_version": "1.0", "case_id": "synthetic_case", "case_kind": "synthetic_test", "source": {"source_pptx": None, "template_pptx": None},
        "inputs": {"blueprint": str(blueprint_path), "design_intent": str(blueprint_path), "route": str(blueprint_path), "evc": str(evc_path), "asset_registry": str(project / "assets" / "asset_slots.json"), "asset_plan": None, "assets_dir": str(project / "assets")},
        "output": {"root": str(project / "case_output"), "allow_overwrite": False},
        "stages": {"assemble": True, "package_inspection": True, "no_shadow_scan": True, "preview": preview, "layout_intelligence_advisory": advisory},
        "runtime_options": {"resume": True, "fail_on_unsupported_required_field": True, "preview_dpi": 120},
    }
    path = project / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return path


def test_first_run_resume_evc_invalidation_and_preview_option_change(tmp_path: Path) -> None:
    manifest_path = make_manifest(tmp_path, preview=True)
    preview_file = tmp_path / "preview.png"
    def preview_hook():
        preview_file.write_bytes(b"png")
        return [preview_file], []
    first = RuntimeCaseRunner(manifest_path, hooks={"preview_render": preview_hook}).run()
    assert first["overall_status"] == "success"
    assert "assemble_pptx" in first["executed_stages"]
    second = RuntimeCaseRunner(manifest_path, hooks={"preview_render": preview_hook}).run()
    assert "assemble_pptx" in second["skipped_stages"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime_options"]["preview_dpi"] = 144
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    changed_preview = RuntimeCaseRunner(manifest_path, hooks={"preview_render": preview_hook}).run()
    assert "assemble_pptx" in changed_preview["skipped_stages"]
    assert "preview_render" in changed_preview["executed_stages"]
    evc_path = Path(manifest["inputs"]["evc"])
    evc = json.loads(evc_path.read_text(encoding="utf-8"))
    evc["editable_objects"][0]["typographic_treatment"]["weight_note"] = "cache invalidation test"
    evc_path.write_text(json.dumps(evc, ensure_ascii=False), encoding="utf-8")
    changed_evc = RuntimeCaseRunner(manifest_path, hooks={"preview_render": preview_hook}).run()
    assert "assemble_pptx" in changed_evc["executed_stages"]
    assert "package_inspection" in changed_evc["executed_stages"]


@pytest.mark.parametrize("stage_id", ["validate_inputs", "resolve_source", "normalize_route", "assemble_pptx", "runtime_evidence", "package_inspection", "no_shadow_scan", "preview_render"])
def test_failure_injection_never_allows_required_downstream_success(tmp_path: Path, stage_id: str) -> None:
    manifest_path = make_manifest(tmp_path / stage_id, preview=True)
    runner = RuntimeCaseRunner(manifest_path, force=True, inject_failure=stage_id)
    summary = runner.run()
    if stage_id == "preview_render":
        assert "preview_render" in summary["unavailable_stages"]
        assert summary["overall_status"] == "partial"
    else:
        assert stage_id in summary["failed_stages"]
        stage_index = [item["stage_id"] for item in summary["stages"]].index(stage_id)
        assert all(item["status"] == "skipped" for item in summary["stages"][stage_index + 1:-1])
        assert summary["overall_status"] == "failed"


def test_dry_plan_writes_no_outputs_and_optional_advisory_is_not_fake_pass(tmp_path: Path) -> None:
    manifest_path = make_manifest(tmp_path, advisory=True)
    runner = RuntimeCaseRunner(manifest_path)
    plan = runner.run(dry_plan=True)
    assert plan["dry_plan"] is True
    assert not (Path(json.loads(manifest_path.read_text())["output"]["root"]) / "run_state.json").exists()
    summary = RuntimeCaseRunner(manifest_path).run()
    assert "layout_intelligence_advisory" in summary["unavailable_stages"]
    assert summary["enforcement"] is False
    assert summary["readiness_unchanged"] is True


def test_force_run_uses_an_isolated_output_root(tmp_path: Path) -> None:
    manifest_path = make_manifest(tmp_path)
    runner = RuntimeCaseRunner(manifest_path, force=True)
    configured = Path(json.loads(manifest_path.read_text())["output"]["root"])
    assert runner.output_root.parent.parent == configured
    assert "runs" in runner.output_root.parts


def test_runtime_helper_error_paths_and_preview_advisory_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    non_object = tmp_path / "array.json"
    non_object.write_text("[]", encoding="utf-8")
    with pytest.raises(RequiredStageError):
        read_json(non_object)

    manifest_path = make_manifest(tmp_path, preview=True, advisory=True)
    data = json.loads(manifest_path.read_text())
    plan = tmp_path / "asset_plan.json"
    plan.write_text("{}", encoding="utf-8")
    data["inputs"]["asset_plan"] = str(plan)
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    runner = RuntimeCaseRunner(manifest_path)
    runner.output_root.mkdir(parents=True)
    runner.work_root.mkdir()
    (runner.artifacts).mkdir()
    pptx = runner.artifacts / "synthetic_case.pptx"
    pptx.write_bytes(b"not-needed-for-fake-preview")
    (runner.work_root / "asset_plan.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(runner_module.subprocess, "run", lambda *args, **kwargs: type("Completed", (), {"returncode": 1, "stdout": "", "stderr": "unavailable"})())
    with pytest.raises(runner_module.OptionalStageUnavailable):
        runner.preview()
    assert Path(runner.advisory()[0][0]["path"]).exists()
    monkeypatch.setattr(runner_module, "inspect", lambda _: (["broken"], [], 1))
    with pytest.raises(RequiredStageError):
        runner.package_inspection()
    monkeypatch.setattr(runner_module, "scan_no_shadow", lambda _: {"result": "FAIL"})
    with pytest.raises(RequiredStageError):
        runner.no_shadow_scan()


def test_invalid_manifest_and_missing_runtime_evidence_fail_required_stages(tmp_path: Path) -> None:
    manifest_path = make_manifest(tmp_path)
    data = json.loads(manifest_path.read_text())
    data["inputs"]["evc"] = str(tmp_path / "missing.json")
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    summary = RuntimeCaseRunner(manifest_path).run()
    assert "validate_inputs" in summary["failed_stages"]

    manifest_path = make_manifest(tmp_path / "second")
    runner = RuntimeCaseRunner(manifest_path)
    runner.output_root.mkdir(parents=True)
    runner.work_root.mkdir()
    with pytest.raises(RequiredStageError):
        runner.runtime_evidence()


def test_cli_main_reports_json_and_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    manifest = make_manifest(tmp_path)
    monkeypatch.setattr(sys, "argv", ["run_runtime_case.py", "--manifest", str(manifest), "--dry-plan", "--json-summary"])
    assert runner_module.main() == 0
    assert '"dry_plan": true' in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["run_runtime_case.py", "--manifest", str(tmp_path / "missing.json")])
    assert runner_module.main() == 1
    assert "ERROR:" in capsys.readouterr().err


def test_cli_main_human_summary_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    manifest = make_manifest(tmp_path)
    monkeypatch.setattr(sys, "argv", ["run_runtime_case.py", "--manifest", str(manifest), "--skip-preview"])
    assert runner_module.main() == 0
    assert "Overall: success" in capsys.readouterr().out


def test_preview_success_without_contact_sheet_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = RuntimeCaseRunner(make_manifest(tmp_path, preview=True))
    runner.artifacts.mkdir(parents=True)
    monkeypatch.setattr(runner_module.subprocess, "run", lambda *args, **kwargs: type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})())
    with pytest.raises(runner_module.OptionalStageUnavailable):
        runner.preview()
