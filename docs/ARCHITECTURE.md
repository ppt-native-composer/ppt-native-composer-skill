# Architecture

The toolchain accepts structured deck input, validates production contracts, then assembles an editable PowerPoint package. The principal contracts are:

1. `deck_blueprint` and `slide_blueprint` define source-backed editable content.
2. `design_intent`, `page_production_route` and `composition_archetype` define approved production intent.
3. `editable_visual_composition` maps source text to editable, placed presentation objects.
4. `assembly_pipeline` and `assemble_pptx` create the package and evidence.
5. `artifact_integrity`, `runtime_stage_cache` and `run_runtime_case` support reproducible staged runs.
6. Layout Intelligence produces advisory diagnostics; it does not replace visual review or act as a default hard gate.

The project deliberately separates mechanical validity from design quality. A valid PPTX, editable text and passing package checks do not prove that a page is visually mature.
