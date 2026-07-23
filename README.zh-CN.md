# ppt-native-composer

`ppt-native-composer` 是一个将结构化页面合同转译为可编辑 PowerPoint 的 Python 工具链。它关注可靠组装、来源追溯、可编辑文字保真、素材校验、不可变运行证据和可由人工审阅的生产门槛。

English version: [README.md](README.md)

它不是自主 art direction 引擎。客户级视觉方向必须来自人工批准的参考、flat comp、Figma/Photoshop 源文件，或另行授权/委托的视觉资产。

## 包含内容

- deck、slide、Design Intent、production route、composition archetype 和 EVC schemas；
- 原生 PPTX 组装与 package inspection；
- route normalisation、artifact integrity 和 stage-cache 工具；
- Layout Intelligence advisory diagnostics；
- deck planning、orchestration 和 human-review 数据合同；
- 用于合同与运行行为的 pytest 测试；
- 通用模板与不含客户内容的 fixture。

## 不包含内容

- 客户脚本、客户数据、客户名称或项目输出；
- 外部图片、视觉参考、授权图库素材或客户 artwork；
- PPTX、PDF、PNG 交付物、生产 evidence 与历史 benchmark；
- 本机路径、缓存环境、内部 handoff 与审阅记录。

## 快速开始

需要 Python 3.11+。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest tests -q
```

在组装前校验结构化 deck blueprint：

```sh
python3 scripts/validate_blueprint.py project/deck_blueprint.json --mode assembly
python3 scripts/assemble_pptx.py project/deck_blueprint.json --project-dir project -o project/output.pptx
python3 scripts/inspect_pptx_package.py project/output.pptx
```

## 生产边界

该项目用于将已批准的视觉方向转译为 hybrid editable PPTX。标题、claim、标签、数据和页码应保持为原生可编辑文字；复杂视觉层只能使用已批准、已授权或客户明确提供的 artwork。

不要把带有最终文字的页面截图放进 PPT 后称为“可编辑交付”。

详细说明见：[架构](docs/ARCHITECTURE.md) 和 [生产边界](docs/PRODUCTION_BOUNDARIES.md)。

## 许可证

MIT，见 [LICENSE](LICENSE)。

## 发布前检查

请在公开发布前确认 GitHub 账户对仓库中代码拥有公开授权。不要加入客户材料、公开作品集图片、付费素材、生成 artwork 或任何凭据，除非已经完成相应权利审查。
