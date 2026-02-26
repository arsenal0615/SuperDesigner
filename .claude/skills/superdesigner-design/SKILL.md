---
name: superdesigner-design
description: 一键运行 SuperDesigner 完整流水线，从图文输入到引擎预设，适合快速原型或首次生成。依次执行 analyze→map→resolve-assets→validate→generate，每步完成后等待用户确认继续。
---

# /design 一键流水线

从策划图文输入到引擎预设的完整流程。

## 适用场景

- 首次生成某个界面
- 快速原型验证
- 对流程熟悉后的高效模式

## 执行顺序

按以下顺序调用各技能，每步完成后**告知用户结果并询问是否继续**：

```
Step 1: /analyze       → 生成 .spec.yaml
Step 2: /map           → 补充交互关系
Step 3: /resolve-assets → 资产匹配 + 生图
Step 4: /validate      → 校验
Step 5: /generate      → 生成引擎预设
```

## 暂停条件

以下情况暂停，等待用户处理：
- `/validate` 发现 ❌ 命名错误 → 修复后继续
- `/resolve-assets` 生成了待审查图片 → 运行 `/approve-assets` 后继续
- 任意步骤报错 → 告知错误信息，等待指示

## 提示

- 对于有多个界面的系统，逐界面运行，不要一次性处理所有界面
- 如果某个步骤需要单独调整，可以直接调用对应的单独命令
