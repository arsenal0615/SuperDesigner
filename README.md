# SuperDesigner

Cursor / Claude Code 插件：游戏策划 UI 图文 → 引擎预设（Unity / UE）的完整自动化流水线。

## 功能

- 分析 UI 参考图和策划案，生成引擎无关的 UI Spec YAML
- 支持 Unity（uGUI）和 Unreal Engine（UMG）
- 资产自动匹配，找不到时调用 Gemini Imagen 生图兜底
- 多工种协作：UI/UE 的调整成果通过所有权标记保留
- 动画安全：删除或修改控件前检查动画绑定
- 知识库：沉淀 UI/UE 经验，下次生成自动应用

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 初始化项目配置

编辑 `.superdesigner/naming-rules.config.yaml`，填写项目的控件命名规则。

编辑 `.superdesigner/style/style-guide.yaml`，填写项目 UI 风格描述（用于生图）。

### 3. 建立资产索引

```bash
# Unity
python scripts/index_assets.py --engine unity --path <Unity项目>/Assets

# UE
python scripts/index_assets.py --engine ue --path <UE项目>/Content
```

### 4. 生成界面

在 Cursor 中，粘贴 UI 参考图和/或策划案文字，运行：

```
/design
```

或分步执行：

```
/analyze      → 生成 UI Spec
/map          → 补充交互关系
/resolve-assets → 资产匹配 + 生图
/validate     → 校验
/generate     → 生成引擎预设
```

## 命令一览

| 命令 | 说明 |
|---|---|
| `/design` | 一键运行完整流水线 |
| `/analyze` | 图文 → UI Spec YAML |
| `/map` | 补充多界面交互关系 |
| `/resolve-assets` | 资产匹配 + 生图兜底 |
| `/validate` | 校验命名和完整性 |
| `/generate` | 生成引擎预设 |
| `/update` | 策划改需求后智能合并更新 |
| `/index-assets` | 重建资产索引 |
| `/approve-assets` | 审查并入库 AI 生成图素 |
| `/knowledge list` | 查看知识库 |

## 项目结构

```
.superdesigner/
├── naming-rules.config.yaml   # 命名规则配置
├── ui-spec.schema.yaml        # UI Spec 字段参考
├── animation-registry.yaml    # 动画绑定注册表
├── asset-index.yaml           # 资产索引（自动生成）
├── style/
│   ├── style-guide.yaml       # 项目 UI 风格（美术维护）
│   └── references/            # 参考图
├── specs/                     # 生成的 UI Spec 文件
├── generated-assets/
│   ├── pending/               # AI 生成待审查
│   └── approved/              # 审查通过入库
└── knowledge/                 # 知识库
    ├── visual-patterns.yaml
    ├── interaction-patterns.yaml
    ├── layout-patterns.yaml
    └── naming-patterns.yaml

scripts/
├── validate_spec.py           # 规格校验
├── index_assets.py            # 资产索引扫描
├── resolve_assets.py          # 资产匹配
├── generate_image.py          # Gemini 生图
├── update_spec.py             # 变更分析
├── knowledge_manager.py       # 知识库管理
└── adapters/
    └── unity_adapter.py       # Unity MCP 适配器
```

## 环境变量

| 变量 | 用途 |
|---|---|
| `GEMINI_API_KEY` | Gemini Imagen API 密钥（生图时需要） |

## 设计文档

详见 `docs/plans/2026-02-24-superdesigner-plugin-design.md`
