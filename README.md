# ppt-native-composer

`ppt-native-composer` is a Python toolchain for building editable PowerPoint decks from structured page contracts. It focuses on reliable assembly, provenance, editable-text preservation, asset validation, immutable runtime evidence, and human-reviewable production gates.

中文说明请见 [README.zh-CN.md](README.zh-CN.md)。

It is not an autonomous art-direction engine. Client-grade visual direction requires a human-approved reference, flat comp, Figma/Photoshop source, or separately licensed/commissioned artwork.

Status: **experimental engineering alpha**. Development is limited to reconstruction, installation, reproducibility and safety, not autonomous design. See the [current assessment](docs/PROJECT_ASSESSMENT.md).

## Included

- deck, slide, design-intent, route, composition-archetype and EVC schemas;
- native PPTX assembly and package inspection;
- route normalisation, artifact integrity and stage-cache utilities;
- layout-intelligence diagnostics as advisory output;
- deck planning, orchestration and human-review data contracts;
- pytest coverage for contracts and runtime behavior;
- generic templates and a non-client fixture.

## Not Included

- client scripts, client data, names or project outputs;
- external images, visual references, licensed stock assets or customer artwork;
- PPTX/PDF/PNG production evidence and prior benchmark decks;
- machine-local paths, runtime caches, handoff notes and internal review records.

## Quick Start

Requires Python 3.11+.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest tests -q
ppt-native-example --output-dir outputs/first-example
```

On Windows, use `py -3 -m venv .venv` then `.venv\Scripts\Activate.ps1`, followed by the same `python`/`ppt-native-*` commands. If shell activation is restricted, invoke `.venv\Scripts\python.exe` directly and use `-m ppt_native_composer.scripts.run_example` instead of the console command.

The example is self-contained: it reconstructs one fixed page using four neutral editable text objects and an original solid-color test swatch. It never downloads artwork, uses client files, or imports test helpers. It writes `example.pptx`, editability/runtime evidence and `example_result.json`. It refuses any existing output directory. Its fixture approvals apply only to this example, **not** to customer work. This is an installation check, not a visual design sample.

Validate an existing approved blueprint before assembly (the paths below are placeholders for your own project):

```sh
python scripts/validate_blueprint.py project/deck_blueprint.json --mode assembly
ppt-native-assemble project/deck_blueprint.json --project-dir project -o project/output.pptx
ppt-native-inspect project/output.pptx --json
```

The original `python scripts/assemble_pptx.py ...` CLI still works. For each revision, use a new project/output directory so the legacy assembler's named evidence files do not overwrite previous reports.

### Optional Rendering

LibreOffice (`soffice`) and Poppler (`pdftoppm`) must already be on PATH; they are not Python dependencies. Ensure your chosen fonts are installed. Use a dedicated **new or empty** preview directory:

```sh
python scripts/render_preview.py outputs/first-example/example.pptx --outdir outputs/first-example-preview
```

Missing tools mean rendering was not run. The example's `visual_qa: not_run` is never automatically promoted to pass; inspect the images and record human review separately. Python reopen and editable text do not prove correct CJK rendering.

### Skill and Wheel

The checkout includes [SKILL.md](SKILL.md) for Codex. Installing the Python package does not install a skill into Codex or change your existing skill catalog. Managed personal-skill installations should be updated through their canonical source and reviewed deployment flow.

`python -m pip wheel --no-deps --wheel-dir dist .` builds a wheel with the runtime, schemas, templates and example data. It excludes client outputs, tests, caches and environments. The stable entrypoints for this alpha are `ppt-native-assemble`, `ppt-native-inspect`, and `ppt-native-example`; internal Python functions are not a stable API.

GitHub Actions is configured for source tests on Linux/Windows and an isolated wheel-only installation check. A workflow definition is not a claim that hosted CI or PowerPoint rendering has passed.

## Production Boundary

Use this project to translate an approved direction into a hybrid editable PPTX. Keep titles, claims, labels, data and page numbers native/editable; use only approved, licensed or client-cleared source artwork for complex visual layers. Do not place a screenshot with baked text into a deck and call it editable.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/PRODUCTION_BOUNDARIES.md](docs/PRODUCTION_BOUNDARIES.md).

## License

MIT. See [LICENSE](LICENSE).

## Before Publishing

Confirm that the publishing account owns or is authorised to publish the code in this repository. Do not add client material, public-portfolio imagery, paid assets, generated artwork, or credentials without appropriate rights and review.
