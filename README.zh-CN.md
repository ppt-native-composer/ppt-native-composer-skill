# ppt-native-composer

`ppt-native-composer` 是一个将结构化页面合同转译为可编辑 PowerPoint 的 Python 工具链。它关注可靠组装、来源追溯、可编辑文字保真、素材校验、不可变运行证据和可由人工审阅的生产门槛。

English version: [README.md](README.md)

它不是自主 art direction 引擎。客户级视觉方向必须来自人工批准的参考、flat comp、Figma/Photoshop 源文件，或另行授权/委托的视觉资产。

当前定位：**实验性 PPT 工程工具**。只继续还原、安装、可复现与安全性开发，不恢复自主设计。详见[当前评估](docs/PROJECT_ASSESSMENT.md)。

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
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest tests -q
ppt-native-example --output-dir outputs/first-example
```

Windows 使用 `py -3 -m venv .venv`，再运行 `.venv\Scripts\Activate.ps1`，之后使用相同的 `python` 和 `ppt-native-*` 命令。如果不便激活环境，可直接运行 `.venv\Scripts\python.exe -m ppt_native_composer.scripts.run_example --output-dir outputs/first-example`。

示例自带四段匿名文字和原创纯色色样，使用固定合同还原一页 PPT。它不下载图片、不使用客户资料，也不导入测试辅助函数。输出包括 `example.pptx`、可编辑性及运行报告、`example_result.json`。输出目录已经存在时会拒绝运行，不覆盖旧文件。示例中的批准仅适用于这个技术用例，不代表真实项目获批。它不是设计样稿。

处理已有批准项目时，在组装前校验 blueprint（以下路径需替换为自己的项目路径）：

```sh
python scripts/validate_blueprint.py project/deck_blueprint.json --mode assembly
ppt-native-assemble project/deck_blueprint.json --project-dir project -o project/output.pptx
ppt-native-inspect project/output.pptx --json
```

原有 `python scripts/assemble_pptx.py ...` 调用仍兼容。每次修订应使用新的项目/产出目录，避免旧组装器按固定名称写入的 evidence 覆盖上一版。

### 可选预览

需自行准备 PATH 上可用的 LibreOffice（`soffice`）、Poppler（`pdftoppm`）及所选字体；这些不是 Python 依赖。预览只能写入专用的新目录或空目录：

```sh
python scripts/render_preview.py outputs/first-example/example.pptx --outdir outputs/first-example-preview
```

缺少工具意味着未渲染，不能算通过。示例的 `visual_qa: not_run` 不会被自动改为通过；必须另行查看图片并记录人工审阅。Python reopen 或文字可编辑都不等于中文渲染正确。

### Skill 与发布包

源码包含 Codex [SKILL.md](SKILL.md)。安装 Python 包不会自动安装 Codex skill，也不会修改已有技能目录。受统一目录管理的个人 skill 仍需经规范源和受审部署流程更新。

`python -m pip wheel --no-deps --wheel-dir dist .` 可构建含运行时、schemas、模板和示例数据的 wheel，不包含客户产出、测试、缓存或虚拟环境。本 alpha 的公开入口为 `ppt-native-assemble`、`ppt-native-inspect`、`ppt-native-example`；内部 Python 函数尚不是稳定 API。

GitHub Actions 已配置 Linux/Windows 源码测试及隔离的 wheel 安装检查。配置文件存在不等于远端 CI 或真实 PowerPoint 渲染已经通过。

## 生产边界

该项目用于将已批准的视觉方向转译为 hybrid editable PPTX。标题、claim、标签、数据和页码应保持为原生可编辑文字；复杂视觉层只能使用已批准、已授权或客户明确提供的 artwork。

不要把带有最终文字的页面截图放进 PPT 后称为“可编辑交付”。

详细说明见：[架构](docs/ARCHITECTURE.md) 和 [生产边界](docs/PRODUCTION_BOUNDARIES.md)。

## 许可证

MIT，见 [LICENSE](LICENSE)。

## 发布前检查

请在公开发布前确认 GitHub 账户对仓库中代码拥有公开授权。不要加入客户材料、公开作品集图片、付费素材、生成 artwork 或任何凭据，除非已经完成相应权利审查。
