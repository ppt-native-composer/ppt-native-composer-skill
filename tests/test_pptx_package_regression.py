from __future__ import annotations

import zipfile

from assemble_pptx import assemble
from test_assembly_integration import prepare_project


def test_package_contains_expected_editable_shapes_and_no_depth_effects(tmp_path) -> None:
    project, blueprint = prepare_project(tmp_path)
    output = project / "package.pptx"
    assemble(blueprint, output, project)
    with zipfile.ZipFile(output) as package:
        names = set(package.namelist())
        assert "ppt/slides/slide1.xml" in names
        xml = package.read("ppt/slides/slide1.xml")
        assert b"s01_title" in xml
        assert b"outerShdw" not in xml
        assert b"innerShdw" not in xml
        assert b"effectDag" not in xml
