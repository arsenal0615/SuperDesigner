---
name: superdesigner-map-interactions
description: 分析同一系统内多个 UI 界面之间的交互关系（跳转、弹窗、Tab切换、生命周期事件等），补充到各 UI Spec 的 interactions 字段。在 analyze-ui 生成 spec 后使用，尤其是系统有多个界面时。
---

# Map Interactions

分析多界面之间的交互关系并写入各 spec 文件的 `interactions` 块。

## 执行前：读取配置和现有 spec

必须先读取：
1. `.superdesigner/knowledge/interaction-patterns.yaml` — 项目约定的交互模式（转场、时长等）
2. `.superdesigner/specs/` 目录下属于同一 system 的所有 spec 文件

询问用户需要处理哪个 system（如 `CitySystem`），或列出当前所有 spec 文件让用户选择。

## 三种交互来源

本 skill 支持同时处理三种来源的交互信息：

### 来源 A：策划案文字描述
从策划提供的文字中识别导航描述，例如：
- "点击 X 按钮打开 Y 界面"
- "关闭弹窗后返回主城"
- "Tab 切换时显示对应内容"

识别后转化为标准 interactions 格式。

### 来源 B：spec 内已有 events 字段
spec 中控件已有 `events.on_click: open_screen(BagScreen)` 类型的内容 → 提取并转化为 interactions 块标准格式，同时保留 events 字段不变（两者可并存）。

### 来源C：AI 推断
根据控件名称、类型和位置推断合理的交互，例如：
- 控件 id 含 `Close` 且父级是 Modal → 推断 `close_screen`
- 控件 id 含 `Back` → 推断返回上一界面
- Tab 组件 → 推断 `toggle_visible`

AI 推断的条目必须标记 `_confidence: low`，等人工确认。

## 执行步骤

### Step 1：收集所有相关 spec
列出同一 system 的所有 spec 文件，读取各文件的 `meta`、`components`（含 events）和现有 `interactions`。

### Step 2：建立界面清单
列出所有 screen 名称，作为 `target` 的有效值集合。对于 `target` 填写了不在清单中的值，标记 `_confidence: low`。

### Step 3：应用知识库模式
读取 `interaction-patterns.yaml`，对匹配 `trigger` 条件的交互条目，将知识库中的 `transition`、`duration` 等字段作为默认值填入（优先级低于策划显式指定）。

### Step 4：生成 interactions 条目

标准格式：
```yaml
interactions:
  - trigger: "Btn_OpenBag.on_click"
    action: open_screen            # open_screen|close_screen|call|toggle_visible
    target: BagScreen
    transition: slide_up           # 来自知识库或策划案
    duration: 0.25                 # 来自知识库或策划案
    _confidence: low               # 如果是 AI 推断，必须添加
```

### Step 5：写入各 spec 文件
将生成的 interactions 条目追加（或合并）到对应 spec 文件的 `interactions` 块：
- 已存在相同 trigger 的条目：跳过（不覆盖），告知用户
- 新条目：追加
- 保留原有条目的 `_confidence` 标记

### Step 6：输出交互关系摘要

生成并打印全系统的交互关系图（文字版）：

```
=== 交互关系图：CitySystem ===

MainCity
  ├── Btn_OpenBag.on_click → BagScreen (slide_up, 0.25s)
  ├── Btn_Shop.on_click → ShopScreen (slide_right, 0.25s) [_confidence: low]
  └── Btn_Settings.on_click → SettingsModal (fade, 0.15s)

BagScreen
  └── Btn_Close.on_click → [close_screen] (fade, 0.15s)
```

## 注意事项

- 只处理同一 system 内的界面跳转，跨 system 的跳转写 target 但不建立双向关系
- 不确定的跳转目标填 `TBD`，标记 `_confidence: low`
- `lifecycle.on_show` / `lifecycle.on_hide` 等生命周期事件也要捕获（来自策划案说明）
- 不生成业务逻辑代码，只描述导航关系

## 后续

完成后告知用户：
> interactions 已写入各 spec 文件
> 下一步：运行 `/resolve-assets` 匹配图素资产
