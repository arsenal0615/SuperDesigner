---
name: superdesigner-index-assets
description: 扫描 Unity 或 UE 项目的资产目录，生成 asset-index.yaml 供后续 /resolve-assets 使用。首次使用 SuperDesigner 时、或资产有大量新增/删除后运行。
---

# Index Assets

扫描引擎资产目录，建立资产索引供后续匹配使用。

## 何时使用

- 首次使用 SuperDesigner 时（必须先建立索引）
- 资产目录有大量新增或删除后
- `/resolve-assets` 报告"asset-index.yaml 不存在"时

## 执行

**Unity 项目：**
```bash
python scripts/index_assets.py --engine unity --path <Unity项目路径>/Assets
```

**UE 项目：**
```bash
python scripts/index_assets.py --engine ue --path <UE项目路径>/Content
```

完成后 `.superdesigner/asset-index.yaml` 将被创建或覆盖更新。

## 输出格式

```yaml
sprites:
  - path: Assets/UI/Common/btn_confirm.png
    name: btn_confirm
    tags: [button, confirm, common]
fonts:
  - path: Assets/Fonts/AlibabaPuHuiTi-Bold.ttf
    name: AlibabaPuHuiTi-Bold
particles:
  - path: Assets/FX/UI/fx_levelup.prefab
    name: fx_levelup
    tags: [level]
audio:
  - path: Assets/Audio/UI/btn_click.wav
    name: btn_click
    tags: [button]
```

## 注意

- 索引是快照，不会自动更新
- 标签（tags）从文件名和路径自动推断，可手动编辑 asset-index.yaml 补充
- 大型项目扫描可能需要几秒钟
