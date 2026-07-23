# Public Release Manifest

Prepared: 2026-07-23

## Source Baseline

The public copy was prepared from the local `ppt-native-composer` engineering baseline at commit `7cd84266fca3060a21f63099030829dda5bfe87f`.

## Included

- Python runtime and assembly scripts;
- schemas, templates and generic fixture data;
- automated tests;
- generic architecture and production-boundary documentation;
- package metadata, an OpenAI skill descriptor and the MIT licence.

## Excluded

- all client names, copy, source files, visual assets and production outputs;
- all PPTX, PDF, PNG/JPEG/WebP, ZIP and runtime-run evidence;
- all handoff notes, private review records, local paths and cached environments;
- public-portfolio references and any material whose reuse rights are not established.

## Publication Checklist

1. Create an empty GitHub repository without auto-generated files.
2. Add that remote to this directory.
3. Confirm the MIT licence and copyright ownership before pushing.
4. Run `python -m pytest tests -q` in a fresh environment before making a release tag.
