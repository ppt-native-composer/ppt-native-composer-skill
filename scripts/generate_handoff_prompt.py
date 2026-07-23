#!/usr/bin/env python3
"""Generate a GPT reverse prompt for PPT Native Composer handoff."""

from __future__ import annotations

import argparse
from pathlib import Path


TYPE_NOTES = {
    "creative-strategy": "重点补全创意概念、情绪递进、视觉隐喻、强视觉页位置，以及哪些短句可作为视觉化文字资产。",
    "strategy-logic": "重点补全策略推导链路、每页论点、证据/洞察、逻辑递进，以及哪些页面需要更强视觉说服力。",
    "execution-detail": "重点补全活动机制、流程、权益、时间、分工、预算、物料等可编辑执行字段，并为每个信息页指定视觉设计角色。",
    "event-plan": "重点补全参与者路径、现场区域、互动机制、传播节奏、运营节点，以及空间/路线/场景类视觉隐喻。",
    "data-report": "重点补全数据来源、图表类型、可编辑数字、关键结论、表格/图表视觉皮肤，以及需要保留的数据字段。",
    "template-native": "重点补全可复用版式、组件类型、信息槽位、可编辑占位符、设计 token 和结构化页面规则。",
    "auto": "根据方案内容自行判断页面类型，但必须输出可生产的结构化脚本，不要继续创意发散。",
}


def build_prompt(project_type: str, project_name: str, notes: str) -> str:
    type_note = TYPE_NOTES[project_type]
    name_line = f"项目名称：{project_name}\n" if project_name else ""
    notes_line = f"补充要求：{notes}\n" if notes else ""

    return f"""请把我们已经定稿的创意方案整理成可交付 Codex 使用 $ppt-native-composer 制作 PPT 的生产脚本。

{name_line}{notes_line}项目脚本类型：{project_type}
本类型整理重点：{type_note}

总原则：
1. 不要重新发散创意，不要提出新方向，只整理已经定稿的方案。
2. 输出必须是可生产脚本，不是说明文或继续讨论。
3. 页面标题和页码必须始终可编辑，不能建议生图。
4. 正文、数字、时间、机制、权益、流程、预算、执行信息默认可编辑。
5. 只有重要创意表达、短 slogan、概念词，才可以标注为 visual_text_assets。
6. 每个 hybrid_native / template_native 执行页都必须说明视觉资产如何和文字排版、信息结构结合，不能只是背景图。
7. 如果缺少视觉参考，请明确列出建议的 mood board 方向，但不要替我改创意。
8. 字体方案必须前置说明：中文字体、英文字体、fallback、标题/正文层级、哪些展示字可 raster。

请输出一个 JSON 结构，字段如下：

{{
  "deck_brief": {{
    "project_name": "",
    "deck_type": "",
    "audience": "",
    "objective": "",
    "creative_summary": "",
    "production_notes": ""
  }},
  "visual_bible": {{
    "moodboard_reference": "",
    "style_direction": "",
    "design_tokens": {{
      "colors": [],
      "typography_tone": "",
      "shape_language": "",
      "texture": "",
      "lighting": "",
      "layout_density": ""
    }},
    "visual_motifs": [],
    "page_family_map": {{
      "strategy_pages": "",
      "execution_pages": "",
      "data_pages": "",
      "chapter_pages": ""
    }},
    "asset_prompt_kit": {{
      "shared_rendering_language": "",
      "transparent_png_rules": "",
      "visual_text_rules": "",
      "negative_prompt": ""
    }},
    "native_component_style": "",
    "do_not_use": []
  }},
  "style_pack": {{
    "name": "",
    "reference_summary": "",
    "quality_bar": "",
    "palette": {{
      "background": "",
      "surface": "",
      "ink": "",
      "accent": "",
      "secondary_accent": "",
      "muted": ""
    }},
    "typography": {{
      "title_character": "",
      "body_character": "",
      "label_character": "",
      "data_character": ""
    }},
    "composition_grammar": {{
      "grid": "",
      "image_scale": "",
      "margin_system": "",
      "density_rule": "",
      "contrast_rule": ""
    }},
    "image_language": {{
      "photography": "",
      "generated_assets": "",
      "lighting": "",
      "crop": "",
      "texture": ""
    }},
    "native_component_skin": {{
      "cards": "",
      "tables": "",
      "timelines": "",
      "labels": "",
      "charts": ""
    }},
    "page_families": {{
      "cover": "",
      "strategy": "",
      "execution": "",
      "data": "",
      "summary": ""
    }},
    "visual_motifs": [],
    "asset_prompt_base": "",
    "do_not_use": []
  }},
  "font_plan": {{
    "cjk": "",
    "latin": "",
    "fallback": [],
    "hierarchy": {{
      "title": "",
      "subtitle": "",
      "body": "",
      "caption": "",
      "data": ""
    }},
    "display_text_policy": ""
  }},
  "slides": [
    {{
      "slide_number": 1,
      "title": "",
      "page_purpose": "",
      "content_type": "",
      "page_mode": "full_image | hybrid_native | template_native",
      "core_message": "",
      "editable_text": [
        {{"id": "title", "text": "", "role": "page title"}},
        {{"id": "body_1", "text": "", "role": "body"}}
      ],
      "visual_text_assets": [
        {{"text": "", "reason": "", "style_note": ""}}
      ],
      "image_assets": [
        {{"id": "", "type": "ai_png | web | user | icon | texture | placeholder", "purpose": "", "transparency": true, "style_note": ""}}
      ],
      "locked_raster": [
        {{"area": "", "reason": ""}}
      ],
      "visual_design_role": "Hero Accent | Atmosphere Layer | Structural Metaphor | Icon System | Data Visual Skin | Object-Based Layout | none",
      "visual_anchors": [],
      "native_structure": "",
      "component_preset": "impact_cover | strategy_argument_cards | execution_ticket_steps | execution_timeline | benefit_matrix | data_capsules",
      "layout_notes": "",
      "speaker_notes": ""
    }}
  ]
}}

页面模式判断：
- full_image：封面、KV、章节页、情绪页、强创意概念页。
- hybrid_native：默认，适合既要设计感又要可编辑的提案页。
- template_native：流程、表格、时间线、权益、预算、分工、机制、数据等结构型页面。

组件 preset 判断：
- impact_cover：封面、KV、章节页。
- strategy_argument_cards：策略论点、洞察链路、概念推导。
- execution_ticket_steps：机制、流程、步骤、玩法。
- execution_timeline：排期、节奏、里程碑。
- benefit_matrix：权益、价值交换、套餐、对比。
- data_capsules：KPI、数据结论、关键数字。

请直接输出 JSON，不要 Markdown 解释。"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--type", choices=sorted(TYPE_NOTES), default="auto", help="Project/script type.")
    parser.add_argument("--project-name", default="", help="Optional project name.")
    parser.add_argument("--notes", default="", help="Additional handoff requirements.")
    parser.add_argument("-o", "--output", help="Write prompt to a file instead of stdout.")
    args = parser.parse_args()

    prompt = build_prompt(args.type, args.project_name, args.notes)
    if args.output:
        Path(args.output).write_text(prompt, encoding="utf-8")
    else:
        print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
