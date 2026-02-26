---
name: superdesigner-knowledge
description: 管理 SuperDesigner 知识库，查看、禁用、启用知识条目，沉淀 UI/UE 工程师的调整经验。在 /update 检测到人工调整时自动提示沉淀；也可手动运行管理条目。
---

# Knowledge Base

知识库沉淀了 UI/UE 的调整经验，在 /generate 和 /update 时自动应用，减少人工校正量。

## 查看知识库

```bash
# 查看全部
python scripts/knowledge_manager.py list

# 查看特定类别
python scripts/knowledge_manager.py list --category visual
python scripts/knowledge_manager.py list --category interaction
python scripts/knowledge_manager.py list --category layout
```

## 临时禁用（本次生成不应用）

```bash
python scripts/knowledge_manager.py disable --id vp_001
```

## 重新启用

```bash
python scripts/knowledge_manager.py enable --id vp_001
```

## 手动添加新知识条目

直接编辑对应 YAML 文件：
- `.superdesigner/knowledge/visual-patterns.yaml`
- `.superdesigner/knowledge/interaction-patterns.yaml`
- `.superdesigner/knowledge/layout-patterns.yaml`
- `.superdesigner/knowledge/naming-patterns.yaml`

条目结构参考文件顶部注释。

## 自动沉淀流程（/update 触发）

当 `/update` 检测到 UI/UE 的调整 diff 时：
1. AI 分析 diff，判断是否是可复用的规律
2. 提示：「检测到新的调整模式，是否沉淀为知识条目？」
3. 用户确认后，AI 生成草稿条目（confidence: low，disabled: false）
4. 草稿写入对应 knowledge yaml，usage_count 从 0 开始积累
5. 积累足够使用次数后，人工将 confidence 升级为 medium 或 high

## 知识应用优先级

```
AI 推断默认值  <  知识库默认值（confidence: high）  <  策划 spec 显式指定值
```

disabled: true 的条目在生成时跳过。
