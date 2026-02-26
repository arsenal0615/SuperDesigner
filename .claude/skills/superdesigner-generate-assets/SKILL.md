---
name: superdesigner-generate-assets
description: 调用引擎 MCP 将 UI Spec YAML 生成为引擎预设（Unity Prefab / UE Widget Blueprint）。在 validate-spec 通过后使用。
---

# Generate Assets

将通过校验的 UI Spec 转化为引擎可用的预设。

## 前置条件

- `/validate` 已通过（无 ❌ 命名错误）
- 引擎 MCP Server 已启动并连接

## Unity

### Step 1：生成 MCP 调用序列

```bash
python scripts/adapters/unity_adapter.py .superdesigner/specs/<ScreenName>.spec.yaml
```

输出 JSON 格式的调用序列到标准输出。

### Step 2：发送到 Unity MCP

将 Step 1 的 JSON 输出提交给已连接的 Unity Editor MCP Server 执行。

MCP Server 将在 Unity 项目中创建：
- Canvas 根对象
- 完整的控件层级结构（含 RectTransform、组件、属性）
- TBD 字段的控件：正常创建，Inspector 中有 `[SuperDesigner] 待填写` 注释

### Step 3：保存 Prefab

在 Unity Editor 中，将生成的 Canvas 拖入 Assets/UI/<SystemName>/ 保存为 Prefab。

## UE（Unreal Engine）

UE 适配层（ue_adapter.py）将在后续版本中提供。目前可以参考 unity_adapter.py 的结构，手动为 UE 的 UMG Widget Blueprint 创建对应调用。

## TBD 字段说明

| 字段 | 引擎中的处理 |
|---|---|
| `source: TBD` | 控件创建，sprite 留空，Inspector 注释"待填写" |
| `font.family: TBD` | 使用 Unity 默认字体，Inspector 注释"待填写" |
| `data_binding: TBD` | 不生成绑定代码，Inspector 注释"待填写" |

## 后续

生成完成后，告知 UI/UE 团队哪些控件有 TBD 字段需要手动补充，更新 `animation-registry.yaml` 记录新界面的动画信息。
