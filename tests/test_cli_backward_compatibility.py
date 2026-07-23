from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from runtime_test_support import create_runtime_case


def test_assemble_cli_remains_backwards_compatible(tmp_path: Path) -> None:
    project, _ = create_runtime_case(tmp_path)
    output = project / "cli.pptx"
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "assemble_pptx.py"), str(project / "blueprint.json"), "--output", str(output), "--project-dir", str(project)]
    completed = subprocess.run(command, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    assert output.exists()
