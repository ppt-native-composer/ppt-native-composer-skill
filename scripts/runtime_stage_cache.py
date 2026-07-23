#!/usr/bin/env python3
"""Content-addressed state for the incremental runtime case runner."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from artifact_integrity import validate_artifact


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_json(payload: Any) -> str:
    return sha256_bytes(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def file_digest(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    return sha256_bytes(path.read_bytes())


def paths_digest(paths: Iterable[Path | None]) -> dict[str, str | None]:
    return {str(path): file_digest(path) for path in paths if path is not None}


def toolchain_fingerprint(skill_root: Path, extra_paths: Iterable[Path] = ()) -> dict[str, Any]:
    scripts = skill_root / "scripts"
    schemas = skill_root / "schemas"
    tracked = [
        scripts / "assemble_pptx.py",
        scripts / "assembly_pipeline.py",
        scripts / "run_runtime_case.py",
        scripts / "runtime_stage_cache.py",
        scripts / "artifact_integrity.py",
        scripts / "evc_runtime.py",
        scripts / "pptx_primitives.py",
        scripts / "ooxml_capabilities.py",
        scripts / "route_normalization.py",
        scripts / "render_preview.py",
        scripts / "inspect_pptx_package.py",
        schemas / "runtime_case_manifest.schema.json",
        schemas / "deck_blueprint.schema.json",
        schemas / "slide_blueprint.schema.json",
        schemas / "editable_visual_composition.schema.json",
        skill_root / "runtime_capability_manifest.json",
        *extra_paths,
    ]
    try:
        import pptx  # type: ignore

        pptx_version = getattr(pptx, "__version__", "unknown")
    except Exception:  # noqa: BLE001
        pptx_version = "unavailable"
    payload = {
        "python": sys.version,
        "platform": platform.platform(),
        "python_pptx": pptx_version,
        "files": paths_digest(tracked),
    }
    return {"fingerprint": sha256_json(payload), "details": payload}


class StageCache:
    """Hash- and type-validated cache index for immutable run artifacts."""

    def __init__(self, state_path: Path, seed: dict[str, Any]):
        self.path = state_path
        self.state = self._load(seed)

    def _load(self, seed: dict[str, Any]) -> dict[str, Any]:
        if self.path.exists():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        return {**seed, "stages": {}, "last_successful_state": None}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def cached(self, stage_id: str, fingerprint: str, dependency_fingerprints: dict[str, str] | None = None) -> tuple[bool, str, list[dict[str, Any]]]:
        record = self.state.get("stages", {}).get(stage_id)
        if not isinstance(record, dict):
            return False, "no cached stage state", []
        if record.get("status") not in {"executed", "skipped"}:
            return False, "previous stage did not succeed", []
        if record.get("input_fingerprint") != fingerprint:
            return False, "input or toolchain fingerprint changed", []
        if dependency_fingerprints is not None and record.get("dependency_fingerprints") != dependency_fingerprints:
            return False, "dependency fingerprint changed", []
        artifacts = record.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return False, "cached artifact manifest is missing", []
        diagnostics: list[dict[str, Any]] = []
        for expected in artifacts:
            if not isinstance(expected, dict):
                return False, "cached artifact manifest is malformed", diagnostics
            actual = validate_artifact(Path(str(expected.get("path") or "")), str(expected.get("artifact_type") or "text"), expected.get("required_keys"))
            diagnostics.append(actual)
            if not actual.get("valid"):
                return False, f"cached artifact invalid: {expected.get('path')}", diagnostics
            if actual.get("sha256") != expected.get("sha256"):
                return False, f"cached artifact hash changed: {expected.get('path')}", diagnostics
            expected_metadata = expected.get("metadata") or {}
            if expected_metadata and actual.get("metadata") != expected_metadata:
                return False, f"cached artifact metadata changed: {expected.get('path')}", diagnostics
        return True, "content hash, dependency fingerprints, and artifact integrity match", diagnostics

    def record(self, stage: dict[str, Any]) -> None:
        self.state.setdefault("stages", {})[stage["stage_id"]] = stage
        if stage.get("status") in {"executed", "skipped"}:
            self.state["last_successful_state"] = stage["stage_id"]
        self.save()
