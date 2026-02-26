---
name: superdesigner-resolve-assets
description: 将 UI Spec 中的 TBD 资产路径匹配到项目实际资产库，无匹配时调用 Gemini Imagen 生图兜底。在 map-interactions 之后、validate-spec 之前使用。
---

# Resolve Assets

将 spec 中的 `source: TBD` 字段匹配到实际资产，找不到时生图兜底。

## 前置条件

- 已有 `.superdesigner/asset-index.yaml`（如没有，先运行 `/index-assets`）
- 已完成 `/analyze` 和 `/map`
- 设置 `GEMINI_API_KEY` 环境变量（仅生图时需要）

## Step 1：运行资产匹配

```bash
python scripts/resolve_assets.py .superdesigner/specs/<ScreenName>.spec.yaml
```

**输出：**
- 更新 spec 文件，将匹配到的 `source: TBD` 替换为实际路径（含 confidence 标记）
- 如有未匹配项，生成 `.superdesigner/specs/<ScreenName>.unresolved.yaml`

## Step 2：如有未匹配资产，运行生图

```bash
# 设置 API Key
export GEMINI_API_KEY="your-api-key-here"

# 生图（默认每个资产生成 2 个变体）
python scripts/generate_image.py .superdesigner/specs/<ScreenName>.spec.yaml

# 生成 3 个变体
python scripts/generate_image.py .superdesigner/specs/<ScreenName>.spec.yaml --variants 3
```

生成的图片存入 `.superdesigner/generated-assets/pending/`。

## Step 3：审查生成图片

运行 `/approve-assets` 选择满意的变体并入库，入库后重新运行 Step 1 使 spec 拾取新资产。

## 匹配逻辑说明

| 匹配结果 | confidence | score 范围 |
|---|---|---|
| 高置信匹配 | high | ≥ 0.70 |
| 中等匹配 | medium | 0.40 ~ 0.69 |
| 低置信匹配 | low | 0.30 ~ 0.39 |
| 无匹配 → 生图 | — | < 0.30 |

- 匹配基于控件 id 的语义部分（去掉前缀）+ label 字段
- 同时对比资产 name 和 tags

## 注意

- 匹配成功但 confidence 为 low 的资产，在 `/validate` 时会产生警告
- 未设置 GEMINI_API_KEY 时，Step 2 会报错退出，但 Step 1 仍可正常运行
