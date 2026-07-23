#!/usr/bin/env python3
"""Trusted manifest-driven incremental runtime runner.

Every invocation creates immutable evidence in ``runs/<run_id>``. A cache hit
is allowed only after hash- and type-validating every prior stage artifact.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from artifact_integrity import sha256_file, validate_artifact

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from assembly_pipeline import AssemblyPipelineError, assemble_pipeline, resolve_route_input  # noqa: E402
from inspect_pptx_package import inspect  # noqa: E402
from runtime_stage_cache import StageCache, file_digest, sha256_json, toolchain_fingerprint, utc_now  # noqa: E402


STAGE_ORDER = ["validate_inputs", "resolve_source", "normalize_route", "assemble_pptx", "runtime_evidence", "package_inspection", "no_shadow_scan", "preview_render", "layout_intelligence_advisory", "final_summary"]
REQUIRED_STAGES = {"validate_inputs", "resolve_source", "normalize_route", "assemble_pptx", "runtime_evidence", "package_inspection", "no_shadow_scan"}


class RequiredStageError(RuntimeError):
    pass


class OptionalStageUnavailable(RuntimeError):
    pass


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RequiredStageError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def resolve_path(value: str | None, base: Path) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def tree_digest(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    if path.is_file():
        return file_digest(path)
    return sha256_json([(str(item.relative_to(path)), file_digest(item)) for item in sorted(path.rglob("*")) if item.is_file()])


def artifact_spec(path: Path, artifact_type: str, required_keys: list[str] | None = None) -> dict[str, Any]:
    result = validate_artifact(path, artifact_type, required_keys)
    if not result["valid"]:
        raise RequiredStageError(f"invalid stage artifact {path}: {'; '.join(result['errors'])}")
    return {"path": str(path), "artifact_type": artifact_type, "required_keys": required_keys or [], "sha256": result["sha256"], "metadata": result["metadata"], "validator": f"artifact_integrity.{artifact_type}", "validation": result}


def scan_no_shadow(pptx: Path) -> dict[str, Any]:
    import zipfile

    counts = {"outerShdw": 0, "innerShdw": 0, "effectDag": 0}
    with zipfile.ZipFile(pptx) as package:
        for name in package.namelist():
            if name.startswith("ppt/") and name.endswith(".xml"):
                data = package.read(name)
                for token in counts:
                    counts[token] += data.count(token.encode("utf-8"))
    return {"pptx": str(pptx), "counts": counts, "result": "PASS" if not any(counts.values()) else "FAIL"}


class RuntimeCaseRunner:
    def __init__(self, manifest_path: Path, *, resume: bool | None = None, force: bool = False, skip_preview: bool = False, skip_advisory: bool = False, hooks: dict[str, Callable[[], Any]] | None = None, inject_failure: str | None = None):
        self.manifest_path = manifest_path.resolve()
        self.manifest_dir = self.manifest_path.parent
        self.manifest = read_json(self.manifest_path)
        self.resume = bool(self.manifest.get("runtime_options", {}).get("resume", True) if resume is None else resume)
        self.force = force
        self.skip_preview = skip_preview
        self.skip_advisory = skip_advisory
        self.hooks = hooks or {}
        # Test-only seam retained for required-stage failure semantics. It is
        # intentionally not exposed by the production CLI or manifest.
        self.inject_failure = inject_failure
        self.case_root = resolve_path(str(self.manifest["output"]["root"]), self.manifest_dir)
        assert self.case_root is not None
        manifest_hash = file_digest(self.manifest_path) or "unknown"
        self.run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{manifest_hash[:8]}-{uuid.uuid4().hex[:6]}"
        self.run_root = self.case_root / "runs" / self.run_id
        self.work_root = self.run_root / "work"
        self.artifacts_root = self.run_root / "artifacts"
        self.logs_root = self.run_root / "logs"
        self.output_root = self.run_root  # legacy inspection alias
        self.artifacts = self.artifacts_root  # legacy inspection alias
        self.toolchain = toolchain_fingerprint(SKILL_ROOT)
        self.cache = StageCache(self.case_root / "cache_index.json", {"case_id": self.manifest.get("case_id"), "cache_version": "phase5x_r_v1"})
        self.stages: list[dict[str, Any]] = []
        self.failed = False
        self.consumption: list[dict[str, Any]] = []

    def dependency_graph(self) -> dict[str, list[str]]:
        return {"validate_inputs": [], "resolve_source": ["validate_inputs"], "normalize_route": ["resolve_source"], "assemble_pptx": ["normalize_route"], "runtime_evidence": ["assemble_pptx"], "package_inspection": ["assemble_pptx"], "no_shadow_scan": ["assemble_pptx"], "preview_render": ["assemble_pptx"], "layout_intelligence_advisory": ["preview_render"], "final_summary": STAGE_ORDER[:-1]}

    def _paths(self) -> dict[str, Path | None]:
        inputs = self.manifest.get("inputs", {})
        source = self.manifest.get("source", {})
        return {"blueprint": resolve_path(inputs.get("blueprint"), self.manifest_dir), "design_intent": resolve_path(inputs.get("design_intent"), self.manifest_dir), "route": resolve_path(inputs.get("route"), self.manifest_dir), "evc": resolve_path(inputs.get("evc"), self.manifest_dir), "asset_registry": resolve_path(inputs.get("asset_registry"), self.manifest_dir), "asset_plan": resolve_path(inputs.get("asset_plan"), self.manifest_dir), "assets_dir": resolve_path(inputs.get("assets_dir"), self.manifest_dir), "source_pptx": resolve_path(source.get("source_pptx"), self.manifest_dir), "template_pptx": resolve_path(source.get("template_pptx"), self.manifest_dir)}

    def _dependency_fingerprints(self, stage_id: str) -> dict[str, str]:
        wanted = set(self.dependency_graph().get(stage_id, []))
        return {record["stage_id"]: record.get("output_fingerprint", record["input_fingerprint"]) for record in self.stages if record["stage_id"] in wanted}

    def _fingerprint(self, stage_id: str, extra: Any = None) -> str:
        contents = {key: tree_digest(path) for key, path in self._paths().items()}
        options = self.manifest.get("runtime_options", {})
        stage_options: dict[str, Any] = {}
        if stage_id == "preview_render":
            stage_options["preview_dpi"] = options.get("preview_dpi", 120)
        if stage_id in {"assemble_pptx", "runtime_evidence"}:
            stage_options["fail_on_unsupported_required_field"] = options.get("fail_on_unsupported_required_field")
        return sha256_json({"stage_id": stage_id, "inputs": contents, "dependencies": self._dependency_fingerprints(stage_id), "toolchain": self.toolchain["fingerprint"], "stage_options": stage_options, "stage_enabled": self.manifest.get("stages", {}).get(stage_id), "cli": {"skip_preview": self.skip_preview if stage_id == "preview_render" else None, "skip_advisory": self.skip_advisory if stage_id == "layout_intelligence_advisory" else None}, "extra": extra})

    def _event(self, record: dict[str, Any]) -> None:
        self.stages.append(record)
        self.run_root.mkdir(parents=True, exist_ok=True)
        with (self.run_root / "stage_events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _stage_record(self, stage_id: str, status: str, reason: str, fingerprint: str, started: str, start_tick: float, *, required: bool, artifacts: list[dict[str, Any]] | None = None, warnings: list[str] | None = None, errors: list[str] | None = None, cache_decision: dict[str, Any] | None = None, callable_name: str | None = None, arguments: dict[str, Any] | None = None, exit_code: int | None = 0, stdout: Path | None = None, stderr: Path | None = None) -> dict[str, Any]:
        artifact_list = artifacts or []
        # Paths are intentionally excluded: immutable runs materialize cache
        # outputs under a new run id while preserving bytes and contract.
        output_fingerprint = sha256_json([{key: item.get(key) for key in ("artifact_type", "sha256", "metadata", "required_keys")} for item in artifact_list])
        return {"stage_id": stage_id, "status": status, "required": required, "reason": reason, "started_at": started, "finished_at": utc_now(), "duration_ms": round((time.perf_counter() - start_tick) * 1000, 3), "input_fingerprint": fingerprint, "dependency_fingerprints": self._dependency_fingerprints(stage_id), "callable": callable_name, "arguments": arguments or {}, "exit_code": exit_code, "stdout_path": str(stdout) if stdout else None, "stderr_path": str(stderr) if stderr else None, "outputs": [item["path"] for item in artifact_list], "artifacts": artifact_list, "output_fingerprint": output_fingerprint, "warnings": warnings or [], "errors": errors or [], "cache_decision": cache_decision or {"decision": "not_checked"}}

    def _stage_logs(self, stage_id: str) -> tuple[Path, Path]:
        self.logs_root.mkdir(parents=True, exist_ok=True)
        return self.logs_root / f"{stage_id}.stdout.log", self.logs_root / f"{stage_id}.stderr.log"

    def _materialize_cached_artifacts(self, artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Copy cache artifacts into this immutable run before downstream use.

        A cache record belongs to an older immutable run.  Downstream stages
        must never silently read that old run through a hard-coded current-run
        path, so materialize an exact hash-validated copy under this run root.
        """
        materialized: list[dict[str, Any]] = []
        runs_root = self.case_root / "runs"
        for artifact in artifacts:
            source = Path(str(artifact["path"]))
            try:
                relative = source.relative_to(runs_root)
                # Strip the old run id; preserve its work/artifacts location.
                destination = self.run_root / Path(*relative.parts[1:])
            except ValueError:
                destination = self.artifacts_root / "cache_materialized" / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and file_digest(destination) != artifact.get("sha256"):
                destination.unlink()
            if not destination.exists():
                shutil.copy2(source, destination)
            copied = artifact_spec(destination, str(artifact["artifact_type"]), list(artifact.get("required_keys") or []))
            if copied["sha256"] != artifact.get("sha256"):
                raise RequiredStageError(f"cache materialization hash mismatch: {source}")
            materialized.append(copied)
        return materialized

    def _run_stage(self, stage_id: str, action: Callable[[], tuple[list[dict[str, Any]], list[str]]], *, enabled: bool = True, optional: bool = False, extra: Any = None, callable_name: str | None = None, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        fingerprint = self._fingerprint(stage_id, extra)
        started, tick = utc_now(), time.perf_counter()
        stdout, stderr = self._stage_logs(stage_id)
        if self.failed and stage_id != "final_summary":
            record = self._stage_record(stage_id, "skipped", "blocked by required upstream failure", fingerprint, started, tick, required=not optional, cache_decision={"decision": "blocked"}, callable_name=callable_name, arguments=arguments, stdout=stdout, stderr=stderr)
            self._event(record)
            return record
        if not enabled:
            record = self._stage_record(stage_id, "skipped", "disabled by manifest or CLI option", fingerprint, started, tick, required=not optional, cache_decision={"decision": "disabled"}, callable_name=callable_name, arguments=arguments, stdout=stdout, stderr=stderr)
            self._event(record)
            return record
        if self.resume and not self.force:
            hit, reason, diagnostics = self.cache.cached(stage_id, fingerprint, self._dependency_fingerprints(stage_id))
            if hit:
                cached = self.cache.state["stages"][stage_id]
                stdout.write_text("cache hit\n", encoding="utf-8")
                stderr.write_text("", encoding="utf-8")
                artifacts = self._materialize_cached_artifacts(cached["artifacts"])
                record = self._stage_record(stage_id, "skipped", reason, fingerprint, started, tick, required=not optional, artifacts=artifacts, warnings=cached.get("warnings", []), cache_decision={"decision": "hit", "reason": reason, "artifact_validation": diagnostics}, callable_name=callable_name, arguments=arguments, stdout=stdout, stderr=stderr)
                self._event(record)
                return record
            invalidation = {"decision": "miss", "reason": reason, "artifact_validation": diagnostics}
        else:
            invalidation = {"decision": "force" if self.force else "resume_disabled"}
        try:
            if self.inject_failure == stage_id:
                raise RequiredStageError(f"test-only injected failure: {stage_id}")
            if stage_id in self.hooks:
                result = self.hooks[stage_id]()
                artifacts, warnings = result if isinstance(result, tuple) else ([], [])
            else:
                artifacts, warnings = action()
            artifacts = [artifact_spec(item, "text") if isinstance(item, Path) else item for item in artifacts]
            if not stdout.exists():
                stdout.write_text("stage executed\n", encoding="utf-8")
            if not stderr.exists():
                stderr.write_text("", encoding="utf-8")
            record = self._stage_record(stage_id, "executed", "cache miss or forced run", fingerprint, started, tick, required=not optional, artifacts=artifacts, warnings=warnings, cache_decision=invalidation, callable_name=callable_name, arguments=arguments, stdout=stdout, stderr=stderr)
            self.cache.record(record)
        except OptionalStageUnavailable as exc:
            stdout.write_text("", encoding="utf-8")
            stderr.write_text(str(exc), encoding="utf-8")
            record = self._stage_record(stage_id, "unavailable", "optional stage unavailable", fingerprint, started, tick, required=False, errors=[str(exc)], cache_decision=invalidation, callable_name=callable_name, arguments=arguments, exit_code=1, stdout=stdout, stderr=stderr)
        except BaseException as exc:  # SystemExit is normalized into stage semantics.
            stdout.write_text("", encoding="utf-8")
            stderr.write_text(f"{type(exc).__name__}: {exc}", encoding="utf-8")
            status = "unavailable" if optional else "failed"
            record = self._stage_record(stage_id, status, "optional stage unavailable" if optional else "required stage failed", fingerprint, started, tick, required=not optional, errors=[f"{type(exc).__name__}: {exc}"], cache_decision=invalidation, callable_name=callable_name, arguments=arguments, exit_code=1, stdout=stdout, stderr=stderr)
            if not optional:
                self.failed = True
        self._event(record)
        return record

    def validate_inputs(self) -> tuple[list[dict[str, Any]], list[str]]:
        schema = read_json(SKILL_ROOT / "schemas" / "runtime_case_manifest.schema.json")
        errors = sorted(Draft202012Validator(schema).iter_errors(self.manifest), key=lambda item: item.json_path)
        if errors:
            raise RequiredStageError("manifest schema invalid: " + "; ".join(f"{item.json_path}: {item.message}" for item in errors))
        for key in ("blueprint", "design_intent", "route", "evc"):
            path = self._paths()[key]
            if path is None or not path.exists():
                raise RequiredStageError(f"missing required manifest input: {key}")
        # The current invocation creates its immutable run directory before this
        # stage.  Only foreign content is an output-root collision.
        allowed = {"runs", "cache_index.json", "latest_success.json"}
        foreign_entries = [item for item in self.case_root.iterdir() if item.name not in allowed] if self.case_root.exists() else []
        if foreign_entries and not self.manifest["output"].get("allow_overwrite"):
            raise RequiredStageError("output.root is non-empty and allow_overwrite=false")
        output = self.artifacts_root / "input_validation.json"
        write_json(output, {"result": "PASS", "manifest": str(self.manifest_path), "schema": str(SKILL_ROOT / "schemas" / "runtime_case_manifest.schema.json")})
        return [artifact_spec(output, "json", ["result", "manifest"])], []

    def _consume(self, field: str, declared: Any, resolved: Path | None, stage: str, status: str, evidence: str) -> None:
        self.consumption.append({"manifest_field": field, "declared_value": declared, "resolved_value": str(resolved) if resolved else None, "consumer_stage": stage, "consumed": status == "consumed", "status": status, "evidence": evidence})

    def resolve_source(self) -> tuple[list[dict[str, Any]], list[str]]:
        self.work_root.mkdir(parents=True, exist_ok=True)
        paths = self._paths()
        blueprint = read_json(paths["blueprint"])
        evc_target = self.work_root / "evc.json"
        shutil.copy2(paths["evc"], evc_target)
        for slide in blueprint.get("slides", []) or []:
            if isinstance(slide, dict):
                slide.pop("editable_visual_composition", None)
                slide["editable_visual_composition_ref"] = evc_target.name
        blueprint_target = self.work_root / "blueprint.json"
        write_json(blueprint_target, blueprint)
        outputs = [artifact_spec(blueprint_target, "json", ["slides"]), artifact_spec(evc_target, "json")]
        for key, filename in (("design_intent", "design_intent.json"), ("route", "route.json"), ("source_pptx", "source.pptx"), ("template_pptx", "template.pptx"), ("asset_plan", "asset_plan.json")):
            source = paths[key]
            declared = self.manifest.get("source", {}).get(key) if key.endswith("pptx") else self.manifest.get("inputs", {}).get(key)
            if source is None:
                self._consume(f"source.{key}" if key.endswith("pptx") else f"inputs.{key}", declared, None, "resolve_source", "unavailable" if key in {"source_pptx", "template_pptx", "asset_plan"} else "invalid", "optional input omitted")
                continue
            if not source.exists():
                raise RequiredStageError(f"declared input missing: {key}: {source}")
            target = self.work_root / filename
            shutil.copy2(source, target)
            kind = "pptx" if key.endswith("pptx") else "json"
            outputs.append(artifact_spec(target, kind))
            self._consume(f"source.{key}" if key.endswith("pptx") else f"inputs.{key}", declared, target, "resolve_source", "consumed", f"snapshotted as {target.name}")
        assets_source = paths["assets_dir"]
        if assets_source and assets_source.exists():
            target = self.work_root / "assets"
            shutil.copytree(assets_source, target, dirs_exist_ok=True)
            slots = target / "asset_slots.json"
            if not slots.exists():
                raise RequiredStageError("assets_dir does not contain asset_slots.json")
            copied_registry_hash = file_digest(slots)
            # Slot registries frequently carry absolute paths from the project
            # that produced them. Rebind every in-tree asset to this run's
            # immutable copy so a manifest cannot silently consume a baseline
            # asset outside the evidence root.
            slot_payload = read_json(slots)
            rewritten = False
            for slot in slot_payload.get("slots", []) or []:
                if not isinstance(slot, dict) or not slot.get("path"):
                    continue
                declared_asset = Path(str(slot["path"]))
                source_asset = declared_asset if declared_asset.is_absolute() else assets_source / declared_asset
                try:
                    relative_asset = source_asset.resolve().relative_to(assets_source.resolve())
                except ValueError:
                    # Legacy registries may retain an absolute path from a
                    # prior fixture copy. Accept it only when the same
                    # basename exists in the declared local asset tree; never
                    # consume the escaped external path itself.
                    relative_asset = Path(source_asset.name)
                rebound = target / relative_asset
                if not rebound.exists():
                    raise RequiredStageError(f"asset slot target missing after snapshot: {rebound}")
                slot["path"] = str(rebound)
                rewritten = True
            if rewritten:
                write_json(slots, slot_payload)
            declared_registry = paths["asset_registry"]
            if declared_registry is not None:
                if not declared_registry.exists():
                    raise RequiredStageError(f"declared asset_registry missing: {declared_registry}")
                # The registry is a first-class manifest input.  A conflicting
                # registry is rejected rather than silently ignored in favour
                # of a convenient asset-tree copy.
                if file_digest(declared_registry) != copied_registry_hash:
                    raise RequiredStageError("asset_registry conflicts with assets_dir/asset_slots.json")
            outputs.append(artifact_spec(slots, "json", ["slots"]))
            for asset_file in sorted(item for item in target.rglob("*") if item.is_file() and item != slots):
                suffix = asset_file.suffix.lower()
                artifact_type = "image" if suffix in {".png", ".jpg", ".jpeg", ".webp"} else "text"
                outputs.append(artifact_spec(asset_file, artifact_type))
            self._consume("inputs.assets_dir", self.manifest["inputs"].get("assets_dir"), target, "resolve_source", "consumed", "asset tree copied")
            self._consume("inputs.asset_registry", self.manifest["inputs"].get("asset_registry"), slots, "resolve_source", "consumed", "registry hash verified against copied asset tree")
        elif paths["asset_registry"]:
            target = self.work_root / "assets"
            target.mkdir(exist_ok=True)
            registry = target / "asset_slots.json"
            shutil.copy2(paths["asset_registry"], registry)
            outputs.append(artifact_spec(registry, "json", ["slots"]))
            self._consume("inputs.asset_registry", self.manifest["inputs"].get("asset_registry"), registry, "resolve_source", "consumed", "registry copied")
        else:
            raise RequiredStageError("asset registry or assets_dir is required")
        self._consume("inputs.blueprint", self.manifest["inputs"].get("blueprint"), blueprint_target, "resolve_source", "consumed", "blueprint snapshotted")
        self._consume("inputs.evc", self.manifest["inputs"].get("evc"), evc_target, "resolve_source", "consumed", "EVC snapshotted and referenced by blueprint")
        self._consume("output.root", self.manifest["output"].get("root"), self.case_root, "runner", "consumed", "immutable run directory created below output root")
        self._consume("runtime_options", self.manifest.get("runtime_options"), None, "runner", "consumed", "included in stage fingerprints and runtime behavior")
        report = self.run_root / "manifest_consumption_report.json"
        write_json(report, {"run_id": self.run_id, "entries": self.consumption})
        outputs.append(artifact_spec(report, "json", ["run_id", "entries"]))
        return outputs, []

    def normalize_route(self) -> tuple[list[dict[str, Any]], list[str]]:
        blueprint = read_json(self.work_root / "blueprint.json")
        route = resolve_route_input(blueprint, self.work_root / "route.json")
        output = self.artifacts_root / "route_normalization_result.json"
        write_json(output, route)
        return [artifact_spec(output, "json", ["canonical_route"])], []

    def assemble(self) -> tuple[list[dict[str, Any]], list[str]]:
        output = self.artifacts_root / f"{self.manifest['case_id']}.pptx"
        result = assemble_pipeline(self.work_root / "blueprint.json", output, self.work_root, source_pptx=(self.work_root / "source.pptx") if (self.work_root / "source.pptx").exists() else None, template_path=(self.work_root / "template.pptx") if (self.work_root / "template.pptx").exists() else None, route_input=self.work_root / "route.json", design_intent_input=self.work_root / "design_intent.json")
        result_path = self.artifacts_root / "assembly_result.json"
        write_json(result_path, result)
        return [artifact_spec(output, "pptx"), artifact_spec(result_path, "json", ["output", "route_provenance"]), artifact_spec(self.work_root / "editability_map_v2.json", "json", ["objects"]), artifact_spec(self.work_root / "composition_runtime_report.json", "json", ["slides"])], []

    def runtime_evidence(self) -> tuple[list[dict[str, Any]], list[str]]:
        records = [artifact_spec(self.work_root / "editability_map_v2.json", "json", ["objects"]), artifact_spec(self.work_root / "composition_runtime_report.json", "json", ["slides"]), artifact_spec(self.work_root / "runtime_capability_manifest.json", "json", ["capabilities"])]
        report = read_json(self.work_root / "composition_runtime_report.json")
        unsupported = [item for slide in report.get("slides", []) or [] for item in slide.get("unsupported_fields", []) or []]
        if unsupported and self.manifest["runtime_options"].get("fail_on_unsupported_required_field"):
            raise RequiredStageError(f"unsupported required runtime fields: {unsupported}")
        return records, []

    def package_inspection(self) -> tuple[list[dict[str, Any]], list[str]]:
        pptx = self.artifacts_root / f"{self.manifest['case_id']}.pptx"
        errors, warnings, slides = inspect(str(pptx))
        output = self.artifacts_root / "package_inspection.json"
        write_json(output, {"pptx": str(pptx), "slides": slides, "errors": errors, "warnings": warnings, "result": "FAIL" if errors else "PASS"})
        if errors:
            raise RequiredStageError("package inspection failed: " + "; ".join(errors))
        return [artifact_spec(output, "json", ["result", "slides"])], warnings

    def no_shadow_scan(self) -> tuple[list[dict[str, Any]], list[str]]:
        output = self.artifacts_root / "no_shadow_scan.json"
        result = scan_no_shadow(self.artifacts_root / f"{self.manifest['case_id']}.pptx")
        write_json(output, result)
        if result["result"] != "PASS":
            raise RequiredStageError("no-shadow scan failed")
        return [artifact_spec(output, "json", ["result", "counts"])], []

    def preview(self) -> tuple[list[dict[str, Any]], list[str]]:
        output_dir = self.artifacts_root / "preview"
        command = [sys.executable, str(SCRIPT_DIR / "render_preview.py"), str(self.artifacts_root / f"{self.manifest['case_id']}.pptx"), "--outdir", str(output_dir), "--dpi", str(self.manifest["runtime_options"].get("preview_dpi", 120))]
        completed = subprocess.run(command, cwd=SCRIPT_DIR, text=True, capture_output=True, timeout=90)
        stdout, stderr = self._stage_logs("preview_render")
        stdout.write_text(completed.stdout, encoding="utf-8")
        stderr.write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise OptionalStageUnavailable(f"preview subprocess failed with exit code {completed.returncode}: {completed.stderr.strip()}")
        contact = output_dir / "contact-sheet.png"
        if not contact.exists():
            raise OptionalStageUnavailable("preview subprocess completed without contact-sheet.png")
        return [artifact_spec(contact, "image")], []

    def advisory(self) -> tuple[list[dict[str, Any]], list[str]]:
        plan = self.work_root / "asset_plan.json"
        if not plan.exists():
            raise OptionalStageUnavailable("asset_plan is required for Layout Intelligence advisory")
        output = self.artifacts_root / "layout_intelligence_advisory.json"
        write_json(output, {"status": "manual_required", "enforcement": False, "readiness_unchanged": True, "asset_plan": str(plan)})
        return [artifact_spec(output, "json", ["enforcement", "readiness_unchanged"])], []

    def _write_run_prelude(self) -> None:
        self.run_root.mkdir(parents=True, exist_ok=True)
        write_json(self.run_root / "resolved_manifest.json", self.manifest)
        write_json(self.run_root / "toolchain_fingerprint.json", self.toolchain)
        write_json(self.run_root / "dependency_graph.json", self.dependency_graph())

    def final_summary(self) -> tuple[list[dict[str, Any]], list[str]]:
        statuses = {name: [record for record in self.stages if record["status"] == name] for name in ("executed", "skipped", "failed", "unavailable")}
        overall = "failed" if statuses["failed"] else "partial" if statuses["unavailable"] else "success"
        case_id = self.manifest.get("case_id", "invalid_manifest")
        case_kind = self.manifest.get("case_kind", "invalid_manifest")
        summary = {"run_id": self.run_id, "case_id": case_id, "case_kind": case_kind, "overall_status": overall, "stages": self.stages, "executed_stages": [x["stage_id"] for x in statuses["executed"]], "skipped_stages": [x["stage_id"] for x in statuses["skipped"]], "failed_stages": [x["stage_id"] for x in statuses["failed"]], "unavailable_stages": [x["stage_id"] for x in statuses["unavailable"]], "total_duration_ms": round(sum(float(item["duration_ms"]) for item in self.stages), 3), "cache_hit_count": len([x for x in self.stages if x.get("cache_decision", {}).get("decision") == "hit"]), "cache_miss_count": len([x for x in self.stages if x.get("cache_decision", {}).get("decision") == "miss"]), "enforcement": False, "readiness_unchanged": True}
        summary_path = self.run_root / "run_summary.json"
        write_json(summary_path, summary)
        markdown = self.run_root / "run_summary.md"
        atomic_write(markdown, f"# Runtime Run Summary\n\nRun: `{self.run_id}`\n\nCase: `{case_id}`\n\nOverall: `{overall}`\n")
        artifact_manifest = self.run_root / "artifact_hash_manifest.json"
        write_json(artifact_manifest, {"run_id": self.run_id, "stages": [{"stage_id": record["stage_id"], "artifacts": record["artifacts"]} for record in self.stages]})
        state = {"run_id": self.run_id, "case_id": case_id, "manifest_hash": file_digest(self.manifest_path), "toolchain_fingerprint": self.toolchain, "last_successful_state": self.stages[-1]["stage_id"] if self.stages else None, "stages": self.stages}
        state_path = self.run_root / "run_state.json"
        write_json(state_path, state)
        if overall == "success":
            write_json(self.case_root / "latest_success.json", {"run_id": self.run_id, "run_root": str(self.run_root), "summary": str(summary_path)})
        return [artifact_spec(summary_path, "json", ["run_id", "stages"]), artifact_spec(markdown, "text"), artifact_spec(artifact_manifest, "json", ["run_id", "stages"]), artifact_spec(state_path, "json", ["run_id", "stages"])], []

    def run(self, dry_plan: bool = False) -> dict[str, Any]:
        if dry_plan:
            plan = []
            for stage in STAGE_ORDER[:-1]:
                fingerprint = self._fingerprint(stage)
                hit, reason, _ = self.cache.cached(stage, fingerprint, self._dependency_fingerprints(stage)) if self.resume and not self.force else (False, "force or resume disabled", [])
                plan.append({"stage_id": stage, "planned_status": "skipped" if hit else "executed", "reason": reason})
            return {"run_id": self.run_id, "dry_plan": True, "stages": plan}
        self._write_run_prelude()
        specs = [
            ("validate_inputs", self.validate_inputs, True, False, "run_runtime_case.validate_inputs", {}),
            ("resolve_source", self.resolve_source, True, False, "run_runtime_case.resolve_source", {}),
            ("normalize_route", self.normalize_route, True, False, "assembly_pipeline.resolve_route_input", {}),
            ("assemble_pptx", self.assemble, bool(self.manifest["stages"]["assemble"]), False, "assembly_pipeline.assemble_pipeline", {}),
            ("runtime_evidence", self.runtime_evidence, bool(self.manifest["stages"]["assemble"]), False, "run_runtime_case.runtime_evidence", {}),
            ("package_inspection", self.package_inspection, bool(self.manifest["stages"]["package_inspection"]), False, "inspect_pptx_package.inspect", {}),
            ("no_shadow_scan", self.no_shadow_scan, bool(self.manifest["stages"]["no_shadow_scan"]), False, "run_runtime_case.scan_no_shadow", {}),
            ("preview_render", self.preview, bool(self.manifest["stages"]["preview"]) and not self.skip_preview, True, "subprocess.render_preview", {"dpi": self.manifest["runtime_options"].get("preview_dpi", 120)}),
            ("layout_intelligence_advisory", self.advisory, bool(self.manifest["stages"]["layout_intelligence_advisory"]) and not self.skip_advisory, True, "run_runtime_case.advisory", {}),
        ]
        for stage_id, action, enabled, optional, callable_name, arguments in specs:
            self._run_stage(stage_id, action, enabled=enabled, optional=optional, callable_name=callable_name, arguments=arguments)
        # A summary is per immutable run, never a reusable cache artifact.
        self._run_stage("final_summary", self.final_summary, enabled=True, optional=False, extra={"run_id": self.run_id}, callable_name="run_runtime_case.final_summary")
        return read_json(self.run_root / "run_summary.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-preview", action="store_true")
    parser.add_argument("--skip-advisory", action="store_true")
    parser.add_argument("--dry-plan", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    try:
        result = RuntimeCaseRunner(Path(args.manifest), resume=True if args.resume else None, force=args.force, skip_preview=args.skip_preview, skip_advisory=args.skip_advisory).run(dry_plan=args.dry_plan)
    except BaseException as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if args.json_summary or args.dry_plan:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Run: {result['run_id']}\nCase: {result.get('case_id')}\nOverall: {result.get('overall_status')}")
    return 1 if result.get("overall_status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
