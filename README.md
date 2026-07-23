# ppt-native-composer

`ppt-native-composer` is a Python toolchain for building editable PowerPoint decks from structured page contracts. It focuses on reliable assembly, provenance, editable-text preservation, asset validation, immutable runtime evidence, and human-reviewable production gates.

It is not an autonomous art-direction engine. Client-grade visual direction requires a human-approved reference, flat comp, Figma/Photoshop source, or separately licensed/commissioned artwork.

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
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest tests -q
```

Validate a structured deck blueprint before assembly:

```sh
python3 scripts/validate_blueprint.py project/deck_blueprint.json --mode assembly
python3 scripts/assemble_pptx.py project/deck_blueprint.json --project-dir project -o project/output.pptx
python3 scripts/inspect_pptx_package.py project/output.pptx
```

## Production Boundary

Use this project to translate an approved direction into a hybrid editable PPTX. Keep titles, claims, labels, data and page numbers native/editable; use only approved, licensed or client-cleared source artwork for complex visual layers. Do not place a screenshot with baked text into a deck and call it editable.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/PRODUCTION_BOUNDARIES.md](docs/PRODUCTION_BOUNDARIES.md).

## License

MIT. See [LICENSE](LICENSE).

## Before Publishing

Confirm that the publishing account owns or is authorised to publish the code in this repository. Do not add client material, public-portfolio imagery, paid assets, generated artwork, or credentials without appropriate rights and review.
