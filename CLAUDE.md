# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指引。

## 项目概述

SuperDesigner 是一个面向游戏团队的 **AI 编码助手插件**（兼容 Claude Code / Cursor / OpenCode），自动化从 UI 设计参考（图片 + 策划案）到引擎预设（Unity uGUI / UE UMG）的完整流水线。项目以中文为主 — README、注释和校验提示均使用中文。

插件由一组 **Agent Skills**（`.claude/skills/superdesigner-*/`）和 **Python CLI 脚本**（`scripts/`）组成。它生成引擎无关的中间格式 **UI Spec YAML**，再通过适配器转换为引擎 MCP 命令。

### Skills 兼容性

Skills 遵循 [Agent Skills 开放标准](https://agentskills.io)，存放在 `.claude/skills/` 目录下，三个工具均可发现：

| 工具 | 发现方式 | 斜杠命令 |
|------|---------|---------|
| **Claude Code** | 原生读取 `.claude/skills/` | `/superdesigner-*` |
| **Cursor** | 交叉兼容读取 `.claude/skills/` | `/superdesigner-*` |
| **OpenCode** | 交叉兼容读取 `.claude/skills/` + `.opencode/commands/` 提供斜杠命令 | `/superdesigner-*` |

### 本仓库是什么
- 一个安装到其他游戏工程中使用的插件
- `.superdesigner/` 是插件在目标工程中的工作目录
- `specs/` 存放为目标工程各界面生成的 spec（不是本仓库自身的数据）
- `example.spec.yaml` 是模板；真实 spec 由各项目按需生成

### 本仓库不是什么
- 不是独立应用
- 不是游戏工程本身（不应包含 PreBattleLoadout、MainCity 等具体项目界面数据）

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 建立资产索引（在项目根目录执行）
python scripts/index_assets.py --engine unity --path <Unity>/Assets
python scripts/index_assets.py --engine ue --path <UE>/Content

# 校验 spec
python scripts/validate_spec.py .superdesigner/specs/SomeScreen.spec.yaml

# 资产匹配（将 TBD source 匹配到实际资产路径）
python scripts/resolve_assets.py .superdesigner/specs/SomeScreen.spec.yaml

# 为未匹配资产生图（需要 GEMINI_API_KEY）
python scripts/generate_image.py .superdesigner/specs/SomeScreen.spec.yaml --variants 2

# 对比新旧 spec，检查动画安全性
python scripts/update_spec.py old.spec.yaml new.spec.yaml

# 将 spec 转换为 Unity MCP 命令（v2 协议）
python scripts/adapters/unity_adapter.py <spec.yaml> [--output v2|legacy]

# 知识库管理
python scripts/knowledge_manager.py list [--category visual|interaction|layout|naming]
python scripts/knowledge_manager.py disable --id vp_001
```

无正式构建系统、测试框架或 lint 工具。

## 架构

### 流水线

```
图片/策划案 → /superdesigner-analyze-ui → UI Spec YAML
                                            ↓
                        /superdesigner-map-interactions（补充交互关系）
                                            ↓
                        /superdesigner-resolve-assets（资产匹配 + 生图兜底）
                                            ↓
                        /superdesigner-validate-spec（命名、完整性校验）
                                            ↓
                        /superdesigner-generate-assets（通过 MCP 生成引擎预设）
```

一键模式：`/superdesigner-design` 运行完整流水线。更新模式：`/superdesigner-update` 对比新旧 spec，尊重所有权和动画安全。

### 协作模型

三个角色参与 spec 的生命周期：
- **策划**：提供输入，触发流水线
- **UI 美术**：调整视觉属性，标记 `_ownership.last_modified_by: ui`
- **UE 工程师**：调整布局/交互，标记 `_ownership.last_modified_by: ue`

`/superdesigner-update` 尊重所有权：AI 生成的字段可覆盖，人工修改的字段仅局部更新并保留 `_overrides`，锁定字段完全跳过。

### 置信度与 TBD 机制

AI 分析阶段为生成的属性分配置信度：
- 直接填值 — 高置信度（控件类型、层级结构、文字内容）
- `_confidence: low` — 不确定（九宫格边距、透明度、z-order）
- `source: TBD` — 无法推断（资产路径、本地化 key、音效、数据绑定）

`/superdesigner-validate-spec` 扫描所有 TBD 和低置信度字段，汇总为待确认清单。

### 脚本

`scripts/` 下的独立 Python 3 CLI 工具。所有脚本假设从项目根目录执行，路径相对于 `.superdesigner/` 解析。

### 适配器

`scripts/adapters/` 下的引擎特定转换器。`unity_adapter.py` 生成 Unity MCP v2 `batch_execute` 命令，功能包括：
- 语义锚点/轴心解析（如 `top-left`、`stretch`）
- 同级碰撞检测与布局归一化
- 语义尺寸兜底（`wrap`/`fill` → 具体值 + 诊断信息）
- `--output legacy` 提供迁移期间的向后兼容

### 配置（`.superdesigner/`）

- `naming-rules.config.yaml` — 命名规范（PascalCase，类型前缀如 `Btn_`、`Txt_`、`Img_`）
- `ui-spec.schema.yaml` — UI Spec 格式完整字段参考
- `animation-registry.yaml` — 节点与动画的绑定关系；`update_spec.py` 阻断删除有动画绑定的节点
- `style/style-guide.yaml` — Gemini Imagen 生图的美术风格描述
- `knowledge/` — 4 个 YAML 文件（视觉、交互、布局、命名模式），从 UI/UE 调整中学习积累
- `tmp/` — 流水线中间产物（unresolved 清单、change-report、unity-report），全部 gitignore

## 开发规约

- **命名**：控件 ID 必须遵循 `naming-rules.config.yaml` — PascalCase + 类型前缀（如 `Btn_OpenBag`、`Panel_Root`、`Txt_Title`）。禁用词：Temp、Test、New、Copy。
- **Windows UTF-8**：脚本在 Windows 上强制 UTF-8 stdout 以支持 emoji/CJK 输出。新增脚本时保持此模式。
- **所有权模型**：`_ownership.locked: true` 的字段禁止被 AI 覆盖。修改 spec 组件前必须检查 `_ownership`。
- **动画安全**：删除或重命名节点前必须检查 `animation-registry.yaml`，该文件记录节点 ID 到动画的绑定关系。
- **环境变量**：`GEMINI_API_KEY` 为生图必需。可选：`GEMINI_TIMEOUT_MS`、`GEMINI_MAX_RETRIES`、`GEMINI_RETRY_BACKOFF_MS`。
- **知识库优先级**：`AI 推断默认值 < 知识库默认值 < spec 显式指定值`。
