from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import apply_style_pack  # noqa: E402
import generate_editable_visual_composition as evc_prompt_builder  # noqa: E402
import generate_asset_prompts  # noqa: E402
import validate_blueprint  # noqa: E402


def type_scale() -> dict:
    def item(size: int, weight: str = "regular", min_contrast: float = 4.5) -> dict:
        return {
            "cjk_size_pt": size,
            "latin_size_pt": size,
            "weight": weight,
            "line_height": 1.18,
            "min_contrast": min_contrast,
        }

    return {
        "display": item(44, "semibold"),
        "title": item(30, "semibold"),
        "claim": item(22, "semibold"),
        "section": item(15, "medium"),
        "body": item(12),
        "label": item(11, "medium"),
        "caption": item(9),
        "page_number": item(8),
    }


def evc_object(source_id: str, role: str, text: str, x: float, y: float) -> dict:
    zone = {"x": x, "y": y, "w": 3.2, "h": 0.42}
    return {
        "id": source_id,
        "source_id": source_id,
        "role": role,
        "text": text,
        "editable": True,
        "visual_behavior": "coordinate_label",
        "hierarchy_level": 2,
        "zone": zone,
        "typographic_treatment": {
            "hierarchy_level": 2,
            "weight": "medium",
            "weight_token": "medium",
            "cjk_size_pt": 11,
            "latin_size_pt": 11,
            "line_height": 1.12,
            "color": "#151515",
            "background_color": "#F6F0E6",
            "min_contrast": 4.5,
        },
        "relationship_to_asset": {
            "anchor_type": "floating_in_quiet_field",
            "asset_reference": "s01_focus",
            "quiet_fields": [zone],
            "why_this_position": "It labels the focus structure without becoming a separate bullet stack.",
        },
        "must_not_be": ["plain bullet list", "ordinary paragraph stack"],
    }


def base_blueprint() -> dict:
    editable_layer = {
        "title": {"id": "s01_title", "role": "title", "text": "策略判断页", "editable": True},
        "page_number": {"id": "s01_page", "role": "page_number", "text": "01", "editable": True},
        "body": [
            {"id": "s01_claim", "role": "main_claim", "text": "建立新的认知位置。", "editable": True},
            {"id": "s01_proof_1", "role": "argument_label", "text": "从信息转向位置。", "editable": True},
        ],
    }
    return {
        "final_script_source": {"confirmed": True},
        "deck_brief": {"project_name": "Contract Test"},
        "visual_bible": {
            "asset_prompt_base": "Project-specific visual language.",
            "do_not_use": ["shadow", "card", "fake depth"],
            "design_tokens": {
                "colors": {
                    "paper": "#F6F0E6",
                    "background": "#F6F0E6",
                    "ink": "#151515",
                    "muted": "#70675D",
                    "accent": "#FF5A3D",
                    "secondary_accent": "#276EF1",
                    "line": "#DDD5CA",
                }
            },
        },
        "page_family_map": {},
        "asset_generation_policy": {},
        "editability_policy": {"title_must_be_editable": True, "page_number_must_be_editable": True},
        "validation_policy": {
            "no_svg_shadow": True,
            "no_container_shadow": True,
            "no_card_shadow": True,
            "no_fake_depth": True,
        },
        "font_plan": {"type_scale": type_scale()},
        "slides": [
            {
                "slide_number": 1,
                "title": "策略判断页",
                "page_function": "strategy_judgment",
                "page_mode": "hybrid_native",
                "core_message": "这页说明要建立新的认知位置。",
                "audience_takeaway": "客户理解页面主张。",
                "visual_idea": "复杂路径连接并锚定一个清晰位置，形成从复杂到清晰的视觉动作。",
                "composition_plan": {
                    "type": "element_asset_hybrid",
                    "asset_zone": {"x": 4, "y": 1, "w": 4, "h": 4},
                    "text_safe_zone": {"x": 0.8, "y": 0.8, "w": 5, "h": 5},
                    "integration_logic": "Editable labels align with the asset focus.",
                    "approved": True,
                },
                "page_production_route": {
                    "slide_number": 1,
                    "selected_route": "element_asset_hybrid",
                    "composition_archetype_id": "focal_convergence",
                    "approval": {"approved": True, "approved_by": "test", "approval_notes": "approved"},
                },
                "composition_archetype": {
                    "archetype_id": "focal_convergence",
                    "approval": {"approved": True, "approved_by": "test", "approval_notes": "approved"},
                },
                "design_intent": {
                    "design_problem": "The page needs a clear visual argument.",
                    "desired_perception": "The argument feels structured and deliberate.",
                    "core_design_argument": "The page must show a movement from complexity to position.",
                    "main_visual_move": "复杂路径连接并锚定一个清晰位置",
                    "text_image_relationship": {"relationship_type": "interlocked"},
                    "editable_strategy": {"must_remain_editable": ["s01_title", "s01_page", "s01_claim", "s01_proof_1"]},
                    "asset_intent": {"what_breaks_if_removed": "The convergence logic disappears."},
                    "layout_intent": {"native_support_role": "minimal alignment support"},
                    "rejected_directions": [
                        {"direction": "ordinary bullet list", "reason": "It loses the visual argument."},
                        {"direction": "decorative background", "reason": "It makes the asset non-structural."},
                    ],
                    "visual_qa_expectations": [
                        "design intent is visible",
                        "text participates in visual logic",
                        "asset is structural, not decorative",
                        "editable text remains editable",
                    ],
                    "do_not_do": ["ordinary text stack"],
                    "approved": True,
                },
                "editable_layer": editable_layer,
                "generated_layer": [
                    {
                        "asset_id": "s01_focus",
                        "asset_type": "transparent_png_element",
                        "visual_role": "primary focal convergence asset",
                        "prompt": "No text, no logo, no slide title, no page number.",
                        "status": "ready",
                        "asset_visual_map": {
                            "coordinate_space": "slide_inches",
                            "focus_point": {"x": 7.2, "y": 3.1},
                            "primary_axis": [{"x": 1.0, "y": 3.0}, {"x": 7.2, "y": 3.1}],
                            "quiet_fields": [{"x": 0.8, "y": 0.8, "w": 3.8, "h": 2.0}],
                            "path_points": [{"x": 1.2, "y": 3.4}, {"x": 4.2, "y": 3.2}, {"x": 7.2, "y": 3.1}],
                        },
                    }
                ],
                "sourced_asset_layer": [],
                "native_graphic_layer": [],
                "visual_text_layer": [],
                "editable_visual_composition": {
                    "slide_number": 1,
                    "title": "策略判断页",
                    "composition_version": "v1",
                    "text_layer_concept": "Editable labels are visual anchors.",
                    "why_text_is_visual": "Text sits on the convergence logic rather than in a detached stack.",
                    "editable_objects": [
                        evc_object("s01_title", "title", "策略判断页", 0.8, 0.8),
                        evc_object("s01_page", "page_number", "01", 0.8, 6.8),
                        evc_object("s01_claim", "main_claim", "建立新的认知位置。", 1.4, 2.0),
                        evc_object("s01_proof_1", "argument_label", "从信息转向位置。", 1.6, 3.2),
                    ],
                    "native_support": [
                        {
                            "id": "s01_tick",
                            "type": "tick",
                            "purpose": "A small alignment tick for the claim label.",
                            "must_not_be_decorative": True,
                            "zone": {"x": 1.2, "y": 2.12, "w": 0.12, "h": 0.12},
                        }
                    ],
                    "anti_patterns": ["plain bullet list", "ordinary paragraph stack", "card stack"],
                    "approval": {"approved": True, "approved_by": "test", "approval_notes": "approved"},
                },
                "validation_checks": {"visual_qa_passed": False},
            }
        ],
    }


def validate(data: dict) -> tuple[list[str], list[str]]:
    return validate_blueprint.validate(data, mode="assembly", project_dir=None, pptx_path=None)


def assert_has_error(errors: list[str], needle: str) -> None:
    assert any(needle in error for error in errors), errors


def test_base_contract_passes_without_errors() -> None:
    errors, _warnings = validate(base_blueprint())
    assert errors == []


def test_route_and_archetype_missing_fail() -> None:
    data = base_blueprint()
    slide = data["slides"][0]
    del slide["page_production_route"]
    del slide["composition_archetype"]
    errors, _warnings = validate(data)
    assert_has_error(errors, "page_production_route or page_production_route_ref is required")
    assert_has_error(errors, "composition_archetype or composition_archetype_ref is required")


def test_design_intent_unapproved_fails() -> None:
    data = base_blueprint()
    data["slides"][0]["design_intent"]["approved"] = False
    errors, _warnings = validate(data)
    assert_has_error(errors, "design_intent.approval.approved must be true")


def test_placeholder_design_intent_fails() -> None:
    data = base_blueprint()
    data["slides"][0]["design_intent"]["main_visual_move"] = "Turn the page argument into an integrated visual structure."
    errors, _warnings = validate(data)
    assert_has_error(errors, "design_intent contains generic placeholder phrase")


def test_asset_prompt_generation_requires_approved_design_intent() -> None:
    data = base_blueprint()
    data["slides"][0]["design_intent"]["approved"] = False
    try:
        generate_asset_prompts.build_manifest(data)
    except SystemExit as exc:
        assert "design_intent.approval.approved must be true" in str(exc)
    else:
        raise AssertionError("build_manifest should reject unapproved design_intent")


def test_asset_prompt_generation_rejects_placeholder_design_intent() -> None:
    data = base_blueprint()
    data["slides"][0]["design_intent"]["main_visual_move"] = "Project-specific metaphor to be derived..."
    try:
        generate_asset_prompts.build_manifest(data)
    except SystemExit as exc:
        assert "generic placeholder phrase" in str(exc)
    else:
        raise AssertionError("build_manifest should reject placeholder design_intent")


def test_style_pack_colors_are_canonical_and_not_shifted() -> None:
    library = apply_style_pack.load_library(SKILL_DIR / "templates" / "style_packs" / "style_packs.json")
    output = apply_style_pack.apply_pack({"visual_bible": {}, "deck_brief": {"project_name": "T"}}, "editorial_event_signal", library["editorial_event_signal"])
    colors = output["visual_bible"]["design_tokens"]["colors"]
    assert isinstance(colors, dict)
    assert colors["paper"] == "#F6F0E6"
    assert colors["background"] == "#F6F0E6"
    assert colors["ink"] == "#151515"
    assert colors["muted"] == "#70675D"
    assert colors["accent"] == "#FF5A3D"
    assert "shadow" not in colors


def test_native_support_missing_zone_fails() -> None:
    data = base_blueprint()
    del data["slides"][0]["editable_visual_composition"]["native_support"][0]["zone"]
    errors, _warnings = validate(data)
    assert_has_error(errors, "editable_visual_composition.native_support[1].zone is required")


def test_evc_missing_source_text_id_fails() -> None:
    data = base_blueprint()
    objects = data["slides"][0]["editable_visual_composition"]["editable_objects"]
    data["slides"][0]["editable_visual_composition"]["editable_objects"] = [item for item in objects if item["source_id"] != "s01_proof_1"]
    errors, _warnings = validate(data)
    assert_has_error(errors, "missing source editable_layer text id s01_proof_1")


def test_evc_editable_object_missing_source_id_fails() -> None:
    data = base_blueprint()
    data["slides"][0]["editable_visual_composition"]["editable_objects"][0].pop("source_id")
    errors, warnings = validate(data)
    assert_has_error(errors, "source_id is required")
    assert any("id fallback is allowed only for migration" in warning for warning in warnings)


def test_evc_text_rewrite_without_approval_fails() -> None:
    data = base_blueprint()
    data["slides"][0]["editable_visual_composition"]["editable_objects"][2]["text"] = "改写后的主张"
    errors, _warnings = validate(data)
    assert_has_error(errors, "differs from editable_layer without text_revision_approved=true")


def test_accent_small_body_text_with_low_contrast_fails() -> None:
    data = base_blueprint()
    treatment = data["slides"][0]["editable_visual_composition"]["editable_objects"][3]["typographic_treatment"]
    treatment["color_token"] = "accent"
    treatment["color"] = "#FF5A3D"
    treatment["background_color"] = "#F6F0E6"
    treatment["min_contrast"] = 4.5
    errors, _warnings = validate(data)
    assert_has_error(errors, "accent is reserved for decorative graphics")


def test_asset_relationship_coordinate_mismatch_fails() -> None:
    data = base_blueprint()
    rel = data["slides"][0]["editable_visual_composition"]["editable_objects"][0]["relationship_to_asset"]
    rel["anchor_type"] = "near_focus"
    rel["focus_point"] = {"x": 12.0, "y": 7.0}
    rel.pop("quiet_fields", None)
    errors, _warnings = validate(data)
    assert_has_error(errors, "focus_point is too far from the editable object zone")


def test_asset_visual_map_missing_coordinate_space_warns_without_geometry_fail() -> None:
    data = base_blueprint()
    data["slides"][0]["generated_layer"][0]["asset_visual_map"].pop("coordinate_space")
    rel = data["slides"][0]["editable_visual_composition"]["editable_objects"][0]["relationship_to_asset"]
    rel["anchor_type"] = "near_focus"
    rel["focus_point"] = {"x": 12.0, "y": 7.0}
    rel.pop("quiet_fields", None)
    errors, warnings = validate(data)
    assert not any("focus_point is too far" in error for error in errors)
    assert any("coordinate_space is missing" in warning for warning in warnings)


def test_title_overflow_uses_type_scale_and_fails() -> None:
    data = base_blueprint()
    long_title = "上市会不是一次发布，而是一次临床认知的建立与延展"
    data["slides"][0]["editable_layer"]["title"]["text"] = long_title
    title_obj = data["slides"][0]["editable_visual_composition"]["editable_objects"][0]
    title_obj["text"] = long_title
    title_obj["role"] = "title"
    title_obj["zone"] = {"x": 0.8, "y": 0.8, "w": 1.0, "h": 0.16}
    title_obj["relationship_to_asset"]["quiet_fields"] = [{"x": 0.8, "y": 0.8, "w": 1.0, "h": 0.16}]
    title_obj["typographic_treatment"].pop("cjk_size_pt", None)
    title_obj["typographic_treatment"].pop("latin_size_pt", None)
    errors, _warnings = validate(data)
    assert_has_error(errors, "estimated text overflow is severe")


def test_assembly_weight_migration_contract_is_present() -> None:
    script = (SCRIPTS_DIR / "assemble_pptx.py").read_text(encoding="utf-8")
    assert "weight_token" in script
    assert "legacy natural-language weight" in script
    assert "CANONICAL_WEIGHT_TOKENS" in script


def test_invalid_weight_token_fails() -> None:
    data = base_blueprint()
    data["slides"][0]["editable_visual_composition"]["editable_objects"][0]["typographic_treatment"]["weight_token"] = "heavy"
    errors, _warnings = validate(data)
    assert_has_error(errors, "weight_token must be one of")


def test_generate_evc_script_has_no_new_slide_number_branches() -> None:
    script = (SCRIPTS_DIR / "generate_editable_visual_composition.py").read_text(encoding="utf-8")
    assert "elif slide_number == 3" not in script
    assert "elif slide_number == 4" not in script
    assert "elif slide_number == 5" not in script
    assert "page02_composition" not in script


def test_evc_fewshot_fixture_is_schema_shaped() -> None:
    fixture = SKILL_DIR / "fixtures" / "examples" / "evc_page02_fewshot.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    assert payload["approval"]["approved"] is True
    assert all("source_id" in item for item in payload["editable_objects"])
    assert all("zone" in item for item in payload.get("native_support", []))
    assert all("hierarchy_level" in item.get("typographic_treatment", {}) for item in payload["editable_objects"])


def test_evc_prompt_builder_prompt_only_contract() -> None:
    data = base_blueprint()
    slide = data["slides"][0]
    prompt = evc_prompt_builder.prompt_for(
        slide=slide,
        design_intent=slide["design_intent"],
        visual_bible=data["visual_bible"],
        route=slide["page_production_route"],
        archetype=slide["composition_archetype"],
        assets=[],
    )
    assert "Return JSON only" in prompt
    assert "Every source editable text object must appear exactly once" in prompt
    assert '"approved": false' in prompt


def test_evc_validate_output_contract() -> None:
    data = base_blueprint()
    slide = data["slides"][0]
    evc = copy.deepcopy(slide["editable_visual_composition"])
    errors, _warnings = evc_prompt_builder.validate_evc_output(evc, slide)
    assert errors == []
    evc["editable_objects"][0].pop("zone")
    errors, _warnings = evc_prompt_builder.validate_evc_output(evc, slide)
    assert any("missing zone" in error for error in errors)
    evc = copy.deepcopy(slide["editable_visual_composition"])
    evc["editable_objects"][0].pop("source_id")
    errors, _warnings = evc_prompt_builder.validate_evc_output(evc, slide)
    assert any("missing source_id" in error for error in errors)
