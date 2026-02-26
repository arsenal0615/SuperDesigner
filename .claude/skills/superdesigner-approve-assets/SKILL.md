---
name: superdesigner-approve-assets
description: 审查 AI 生成的图素变体，选择满意的版本入库，更新 asset-index.yaml 和对应 spec 文件。在 /resolve-assets 生图后使用。
---

# Approve Assets

审查生成图片，确认入库。

## 执行流程

### Step 1：查看待审查图片

```bash
# 列出 pending 目录
ls .superdesigner/generated-assets/pending/
```

每个控件有 2-3 个变体（`Btn_OpenBag_v1.png`, `Btn_OpenBag_v2.png` 等）。

### Step 2：选择满意的变体

将满意的变体复制到 `approved/` 目录（去掉版本号）：

```bash
# 选择 v2
cp .superdesigner/generated-assets/pending/Btn_OpenBag_v2.png \
   .superdesigner/generated-assets/approved/Btn_OpenBag.png
```

### Step 3：复制到引擎资产目录

将 `approved/` 中的图片复制到引擎项目对应目录：

```bash
# Unity 示例
cp .superdesigner/generated-assets/approved/Btn_OpenBag.png \
   <Unity项目>/Assets/UI/<SystemName>/Btn_OpenBag.png
```

### Step 4：更新资产索引

重新运行资产索引（或手动追加到 asset-index.yaml）：

```bash
python scripts/index_assets.py --engine unity --path <Unity项目>/Assets
```

### Step 5：重新匹配 spec

```bash
python scripts/resolve_assets.py .superdesigner/specs/<ScreenName>.spec.yaml
```

此时之前 TBD 的资产应能匹配到刚入库的图片。

## 对不满意的变体

- 丢弃所有变体，调整 style-guide.yaml 中的 prompt_keywords，重新运行 /resolve-assets 生图
- 或手动制作资产，放入 `approved/` 目录后执行 Step 4-5

## 注意

- `pending/` 目录中的图片不会自动清理，确认后手动删除旧变体
- AI 生成图片仅作为起点，正式上线前建议 UI 美术进行二次打磨
