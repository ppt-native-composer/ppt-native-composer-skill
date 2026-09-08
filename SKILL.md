---
name: ppt-native-composer
description: Reconstruct approved layouts and artwork as editable PowerPoint text and shapes, with package inspection and runtime evidence. Use for contract-driven PPT engineering, not autonomous visual design.
---

# PPT Native Composer

Use this skill when approved artwork, approved copy and a layout contract exist,
or when maintaining the editable-PPT runtime itself. It is a reconstruction and
inspection tool, not an art director or a replacement for a designer.

## Inputs and boundaries

- Resolve the approved artwork, copy source and layout/EVC from the current
  project. Do not treat example approvals as approval of another project.
- Keep official text and revision-prone information as native PowerPoint text.
  Complex licensed artwork can remain raster/vector assets. A full-page image
  containing baked copy is not editable reconstruction.
- Preserve the approved crop, hierarchy, colors and page roles. Do not replace
  artwork with generated geometry or invent a new visual direction.
- If artwork or layout approval is missing, identify that gap. Do not run the
  legacy storyboard, art-direction or asset-prompt generators as a substitute.
- This workflow is industry-neutral. Do not introduce medical-launch concepts,
  old example metaphors or client-specific copy into unrelated projects.

## Run

Resolve commands relative to this skill directory. From a source checkout,
install dependencies as described in [README.md](README.md). The self-contained
`ppt-native-example --output-dir <new-directory>` checks the installation; its
synthetic swatch is a technical fixture, not artwork or a visual benchmark.

For an existing approved blueprint:

```sh
python scripts/validate_blueprint.py <blueprint.json> --mode assembly
python scripts/assemble_pptx.py <blueprint.json> --project-dir <project> -o <new-output.pptx> --json
python scripts/inspect_pptx_package.py <new-output.pptx> --json
```

Keep each reconstruction in a new output/evidence directory. Do not overwrite
previous PPTX files or the project's frozen evidence.

For existing manifest-driven work, use `scripts/run_runtime_case.py --manifest
<case.json> --resume` or `scripts/run_deck.py --manifest <deck.json> --resume`.
Do not bypass typed artifact validation, dependency hashes or immutable runs.

## Verify

- Reopen the actual PPTX and reconcile native text with the approved copy.
- Inspect package relationships, editability/runtime reports and OOXML effects.
  A shadow scan does not inspect shadows baked into raster artwork.
- Render with `scripts/render_preview.py` only to a **new, dedicated** preview
  directory. Nonempty output directories are rejected without deleting files.
  It requires LibreOffice and Poppler on PATH. Inspect the resulting images,
  including CJK glyphs, crop, text placement and final-size readability.
- Unavailable rendering means visual QA is `not_run`, never `pass`.
- Layout Intelligence is advisory. Geometry proximity is not rendered binding;
  a passing package is not client-grade visual approval.

Read [docs/PRODUCTION_BOUNDARIES.md](docs/PRODUCTION_BOUNDARIES.md) for scope and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the existing contracts. Internal
functions and legacy creative generators are not a stable public API. A real
template-native production acceptance is still unverified.
