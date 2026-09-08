"""Run with a fresh wheel-only interpreter, not the editable source environment."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tempfile

import ppt_native_composer


def main() -> None:
    root = Path(ppt_native_composer.__file__).resolve().parent
    checkout = Path(__file__).resolve().parents[1]
    assert not root.is_relative_to(checkout), "Must test the wheel, not the checkout."
    for resource in (
        "schemas/runtime_case_manifest.schema.json",
        "templates/style_packs/style_packs.json",
        "templates/layout_intelligence/default_thresholds.json",
        "runtime_capability_manifest.json",
        "fixtures/examples/approved_artwork/blueprint.json",
    ):
        json.loads((root / resource).read_text(encoding="utf-8"))
    assert not (root / "tests").exists(), "Do not package tests or private evidence."
    scripts = Path(sysconfig.get_path("scripts"))
    suffix = ".exe" if os.name == "nt" else ""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="ppt-wheel-check-") as directory:
        cwd = Path(directory)
        output = cwd / "example"
        result = subprocess.run(
            [str(scripts / f"ppt-native-example{suffix}"), "--output-dir", str(output)],
            cwd=cwd, env=env, text=True, capture_output=True, check=True, timeout=60,
        )
        report = json.loads(result.stdout)
        assert report["status"] == "mechanical_pass"
        assert report["editable_text_count"] == 4 and report["text_preserved"]
        assert report["visual_qa"] == "not_run" and not report["client_grade"]
        inspected = subprocess.run(
            [str(scripts / f"ppt-native-inspect{suffix}"), str(output / "example.pptx"), "--json"],
            cwd=cwd, env=env, text=True, capture_output=True, check=True, timeout=60,
        )
        assert json.loads(inspected.stdout)["result"] == "PASS"
        subprocess.run(
            [str(scripts / f"ppt-native-assemble{suffix}"), "--help"],
            cwd=cwd, env=env, capture_output=True, check=True, timeout=30,
        )
    print("Wheel-only install: bundled resources, CLI, assembly, native text and package checks passed.")


if __name__ == "__main__":
    main()
