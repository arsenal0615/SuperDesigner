---
name: superdesigner-update
description: 当策划修改 UI 需求时，智能合并更新 UI Spec 并生成变更报告，同时检查动画安全性。在策划提供新的需求图文或文字描述后使用，替代重新运行 /design 全流程。
---

# Update

策划改需求后，智能更新 spec 并保留 UI/UE 已有调整成果。

## 核心原则

- **节点 ID 稳定**：尽量保留原有 node id，避免动画绑定断裂
- **所有权保护**：UI/UE 修改过的字段不被 AI 覆盖
- **动画安全**：删除有动画绑定的节点前必须人工确认

## 执行流程

### Step 1：分析新需求

使用 `/analyze` 技能分析新的需求图文，但**不直接保存**，先生成临时 spec 到 `.superdesigner/specs/<ScreenName>.spec.new.yaml`。

### Step 2：运行变更分析脚本

```bash
python scripts/update_spec.py \
    .superdesigner/specs/<ScreenName>.spec.yaml \
    .superdesigner/specs/<ScreenName>.spec.new.yaml
```

生成变更报告 `.superdesigner/change-report-<date>.yaml`。

### Step 3：审查变更报告

变更报告包含：

```yaml
summary:
  added: 3        # 新增控件数
  modified: 5     # 修改的控件数
  deleted: 1      # 删除的控件数
  animation_warnings: 2   # 有动画绑定的控件被删除/重命名
  locked_skipped: 1       # 被锁定（locked: true）跳过的控件

changes:
  - node_id: Btn_OpenBag
    type: modified
    changed_fields: [label, size]
    ownership: ui            # 该控件被 UI 改过
    action: partial_update   # 只更新 label，size 因有 UI override 跳过

  - node_id: Panel_OldHUD
    type: deleted
    action: blocked_by_animation   # 有动画绑定，阻断删除

  - node_id: Btn_NewFeature
    type: added
    action: inserted
```

### Step 4：处理动画警告

对 `action: blocked_by_animation` 的节点：
1. 告知 UE 工程师节点被删除，动画需要迁移
2. 人工确认后，手动删除节点并在 Unity/UE 中更新动画绑定
3. 更新 `animation-registry.yaml` 移除对应条目

### Step 5：应用变更

确认变更报告后，将 `.spec.new.yaml` 的变更按报告中的 action 合并到原 `.spec.yaml`：
- `action: overwrite` → 用新值替换
- `action: partial_update` → 只更新 changed_fields 中非 _overrides 的字段
- `action: skip_locked` → 不修改
- `action: blocked_by_animation` → 等人工处理

### Step 6：清理临时文件

```bash
# 确认合并完成后删除临时文件
rm .superdesigner/specs/<ScreenName>.spec.new.yaml
```

## 所有权说明

| `_ownership.last_modified_by` | /update 时的策略 |
|---|---|
| `ai` | 正常覆盖 |
| `ui` 或 `ue` | 只更新策划改动的字段，保留 `_overrides` |
| `designer` | 只更新策划改动的字段 |
| `locked: true` | 完全跳过 |
