---
name: superdesigner-validate-spec
description: 校验 UI Spec YAML 的命名规则、完整性和 TBD 字段，生成校验报告。在 resolve-assets 之后、generate-assets 之前使用。
---

# Validate Spec

校验 spec 文件，确保可以安全运行 /generate。

## 执行

```bash
python scripts/validate_spec.py .superdesigner/specs/<ScreenName>.spec.yaml
```

## 校验内容

| 类别 | 说明 | 阻断 /generate？ |
|---|---|---|
| ❌ 命名错误 | 控件 id 不符合前缀规则或含禁用词 | 是 |
| ⚠️ TBD 字段 | source/font.family/data_binding 等未填 | 否（引擎中留空并注释） |
| ⚠️ 低置信度 | `_confidence: low` 的字段需人工确认 | 否 |
| ⚠️ Modal 关闭按钮 | Modal 控件缺少 Btn_Close 类按钮 | 否 |

## 处理流程

```
校验通过（0 个 ❌） → 可以运行 /generate
校验失败（有 ❌）  → 修复命名错误后重新运行 validate
```

对于 ⚠️ 警告：
- TBD 字段：引擎侧控件会正常创建，但属性留空并在 Inspector 中注释"[SuperDesigner] 待填写"
- 低置信度：建议人工确认后删除 `_confidence: low` 标记，但不影响生成

## 批量校验（一个 system 的所有 spec）

```bash
for f in .superdesigner/specs/*.spec.yaml; do
    python scripts/validate_spec.py "$f"
done
```

## 后续

- 无 ❌ 错误 → 运行 `/generate`
- 有 ❌ 错误 → 修复后重新运行 `/validate`
