# Project Assessment

Date: 2026-09-08. Decision: **retain as a narrow engineering backend**.

## 结论

不删除工程内核，也不继续自主设计研发。它有价值的部分是将已批准素材、准确
文案和显式版式合同转换为可编辑 PPTX，并提供来源、绑定、缓存和运行证据。
普通一次性改字不需要这套完整合同；复杂重复生产与可追溯重建才是它的适用范围。
它不应与上层设计工具重复承担 art direction。

English summary: retain approved-artwork reconstruction, editable-text integrity
and reproducible runtime tooling. Stop autonomous art-direction development.
The current work is an engineering alpha, not a client-ready design product.

## 本次实查

| 问题 | 证据与处理 |
| --- | --- |
| README 安装命令无法执行 | 新虚拟环境执行 editable install，setuptools 因多个顶层目录自动发现报错。增加显式 package mapping 与 build backend，源码安装和 wheel-only 安装复验通过。 |
| 公开仓库缺 skill 入口 | 原仓库只有 agents metadata，没有 SKILL.md；现补齐批准稿还原边界，移除 default prompt 中的 high-design 承诺。 |
| 没有可独立运行的示例 | 旧 fixture 只是一段 EVC 且引用不存在的资产。新增完整匿名 blueprint、copy、色样定义、素材清单和运行入口，不依赖 tests。 |
| 预览脚本会删除 outdir 现有文件 | 原代码逐项 unlink。现改为拒绝非空目录，新增文件、子目录、参数和工具缺失验证。 |
| 历史设计生成器仍含固定叙事 | legacy storyboard 仍写死特定项目式隐喻，asset prompt builder 仍有 medical-launch 分支。保留作兼容研究材料，但明确不进入受支持的 reconstruction 流程。本轮没有把它们包装为已泛化的设计能力。 |
| 工程能力仍有复用价值 | 原 132 项测试在新 Python 环境通过；包含绑定目标变化、缓存损坏、required/optional stage 和合同检查。本次增加真实示例重开、文字修改、锚点移动与输出保护验证。 |

本机 skill 的 installed、canonical 和公开仓库是不同维护对象。个人规范源的入口
已收口，旧入口移入历史 reference；本次未直接覆盖安装副本，也未执行统一目录
发布。规范源独立补入相同的安装、安全性与兼容性修复，没有从公开目录整体
覆盖私人 runtime，也没有重新发布私人 fixtures 或历史 evidence。

## 已完成的开发目标

**让无客户资料的使用者能安装、运行并验证一次 PPT 工程链路。**

- 源码 editable install；带 schemas、模板和示例数据的 wheel；三项 CLI 入口。
- 四段原生文字 + 一个原创测试色样的端到端示例，保留 package/runtime/editability evidence。
- 真实 PPTX 重开验证：文字完整；改文案不替换图片；移动声明锚点后标签随动。
- 旧 CLI 保留；预览拒绝覆盖已有内容；不改变 validator、resolver 或 cache 合同。
- 中英文使用说明和独立 Codex skill 入口；配置持续测试。

## 当前验证结果

- Python 3.13/macOS：`python -m pytest tests -q`，**146 passed**。
- `python -m compileall -q scripts`：通过。
- `pip install -e '.[test]'`：通过。
- `pip wheel --no-deps ...`：通过；wheel 约 172 KiB，不含 tests 或客户产出。
- 第二个全新虚拟环境只安装 wheel，在仓库之外运行：入口、bundled resources、组装与 package 检查通过。
- 匿名示例：1 页、4 个 editable text、文字一致、Python reopen PASS、package PASS、OOXML no-shadow PASS。
- LibreOffice 导出 PDF、Poppler 渲染 PNG 成功，实际检查页图：四段英文及色样可见，无截断。这不是 CJK 或 PowerPoint 跨环境验收。
- public/canonical `SKILL.md` 均通过 quick_validate；`git diff --check` 通过。
- 示例程序继续输出 `visual_qa: not_run`、`client_grade: false`；人工观察不由程序自动提升为视觉批准。
- 收口复验：公开版 146 项、私人规范源 138 项测试通过；sdist 构建后再构建 wheel、在全新环境独立安装并运行通过。
- [GitHub hosted CI](https://github.com/ppt-native-composer/ppt-native-composer-skill/actions/runs/34177317590) 已在代码提交 `4ed1546` 上通过：Linux/Windows x Python 3.11/3.13 四组源码测试与匿名示例，以及独立 wheel 安装检查。
- 首轮 CI 真实发现 Python 3.11 不支持的同引号嵌套 f-string，以及 Windows 测试读取中文 JSON 时使用默认编码的问题；已分别改为等价字符串拼接和显式 UTF-8，没有跳过测试或放宽合同。

复现入口见 README。额外安装检查可用全新 wheel 环境执行
`python tests/check_installed_distribution.py`，该检查明确拒绝加载源码 checkout。
本地生成的技术证据在 `outputs/readiness-check/`，被 gitignore 排除。

## 不宣称完成的部分

- GitHub 工程 CI 已通过，但它不渲染页面，不等于 Windows 字体或 PowerPoint 视觉验收。
- 本机受管 skill 的 scoped update plan 已生成，仍须按目录合同确认精确 plan_id 后事务部署；Python 包提交不等于本机 skill 已升级。
- 本轮没有验证 Microsoft PowerPoint、Keynote、中文跨环境排版或真实 template-native 生产。
- 没有做全仓库版权、供应链或完整历史秘密审计；开源法律与安全认证不在本次结论中。
- 旧 assembler 的固定名称 evidence 仍需使用独立 revision 目录，或使用 immutable manifest runner。
- 本轮没有删除历史 evidence，没有恢复已终止设计路线，没有制作客户页面。
- 本地行为元数据仅为抽样，不证明无人使用：初次扫描最多 50 个近期会话，跳过 35 个过大文件及 29 行过大记录；未命中本 skill 的显式读取不能作为删除依据。

## 后续投入条件

只接受来自真实 reconstruction 用户的可复现缺陷或可移植性问题。
不主动追加设计模块、更多 pattern、审美打分或大型 deck 实验。
下一项外部验证应是使用者在实际 PowerPoint/字体环境中，提供有使用权的真实
分层稿进行一次受限还原。CI 已覆盖第二种 OS 的机械安装运行，但不替代这个
视觉与使用验收；没有该证据前，不升级为 production-ready。
