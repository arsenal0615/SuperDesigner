---
name: superdesigner-analyze-ui
description: 分析游戏UI参考图或策划案文字，生成引擎无关的 UI Spec YAML 文件，保存到 .superdesigner/specs/。当用户提供UI截图、手绘稿、Figma导出图、或策划案文字描述界面时使用。
---

# Analyze UI

将图片和/或策划案文字转化为标准 UI Spec YAML 文件。

## 执行前：读取项目配置

必须先读取以下文件，作为生成的依据：

1. `.superdesigner/naming-rules.config.yaml` — 控件命名规则和前缀
2. `.superdesigner/ui-spec.schema.yaml` — 所有可用字段的参考
3. `.superdesigner/knowledge/visual-patterns.yaml` — 视觉规律知识库
4. `.superdesigner/knowledge/layout-patterns.yaml` — 布局规律知识库

## 输入处理

接受以下任意组合：
- **图片**：UI 截图、手绘稿、Figma 导出，直接贴入对话
- **文字**：策划案描述，界面功能说明，交互文字描述
- **两者结合**：图片提供布局，文字补充交互逻辑和命名意图

如果输入包含多个界面，询问用户先处理哪一个。每次只生成一个 screen 的 spec。

## 分析步骤

### Step 1：识别 meta 信息
- `screen`：界面名（从图片内容或策划案推断，使用 PascalCase 英文）
- `system`：所属系统（如能推断）
- `size`：设计分辨率（从策划案读取，默认 [1920, 1080]）
- `engine`：从项目上下文判断，或询问用户

### Step 2：识别控件层级结构
从外到内，从上到下分析：
1. 最外层容器（通常是 Panel 或 Modal）
2. 功能区域划分（HUD、内容区、操作区等）
3. 具体控件（Button、Text、Image 等）
4. **重复结构识别**：看到多个结构相同的元素 → 识别为 List 或 Grid，提取 item_template

### Step 3：为每个控件分配属性

**置信度规则（必须严格遵守）：**

| 可以直接填值（高置信度） | 必须标记 _confidence: low | 必须填 TBD |
|---|---|---|
| type（从外观推断） | anchor（位置方向可见但不精确） | source（图片资产路径） |
| label/content（文字可读） | size（估算尺寸） | data_binding |
| List/Grid 识别 | padding/gap | sfx |
| item_template 抽取 | opacity | localize_key |
| visible: true/false | slice_type/slice_border | font.family |
| events.on_click（策划案有说明） | states（推测样式） | asset（粒子/RenderTexture）|

### Step 4：应用知识库默认值

对每个控件，检查 visual-patterns 和 layout-patterns 中的 patterns：
- 查找 `trigger.component_type` 匹配当前 type 的条目
- 将匹配条目的 `apply` 字段注入为默认值
- 知识库值优先级高于 AI 推断，但低于策划显式指定
- 在生成报告中说明哪些字段来自知识库

### Step 5：命名控件

按 `naming-rules.config.yaml` 规则命名每个控件：
- 使用对应 type 的前缀（Btn_、Txt_、Img_ 等）
- 语义名用英文 PascalCase
- item_template 内部控件加 Item 前缀（如 `Txt_ItemName`）
- 禁用 forbidden_words 中的词

### Step 6：处理交互关系（初步）

将策划案中明确描述的交互写入 events 或 interactions 块：
- 简单跳转写入控件的 `events.on_click`
- 复杂交互（条件、生命周期）写入顶层 `interactions` 块
- 不确定的交互：写注释说明，等待 /map 阶段处理

## 输出

**文件路径**：`.superdesigner/specs/<ScreenName>.spec.yaml`

**同时输出待确认清单**（打印在对话中，不写入文件）：

```
=== 待确认清单：<ScreenName> ===

📌 TBD 字段（需美术/策划补充）：
  - Btn_OpenBag.source: 图片资产路径
  - Txt_PlayerName.font.family: 字体名称
  - ...

🟡 低置信度字段（请人工确认）：
  - Panel_HUD.anchor: top-left（从图位置估算）
  - Btn_OpenBag.size: [200, 80]（估算）
  - ...

💡 来自知识库的默认值：
  - Btn_OpenBag.padding: [16, 32, 16, 32]（from vp_001）
  - ...
```

## 注意事项

- **不生成业务逻辑代码**，data_binding 统一填 TBD
- **不猜测资产路径**，source 统一填 TBD，等 /resolve-assets 处理
- **一次只处理一个 screen**
- 生成完毕后，提示用户运行 `/map` 处理多界面交互关系

## 后续

生成完成后，告知用户：
> spec 已保存到 `.superdesigner/specs/<ScreenName>.spec.yaml`
> 下一步：运行 `/map` 补充多界面交互关系，或直接运行 `/resolve-assets` 匹配资产
