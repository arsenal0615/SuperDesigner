#!/usr/bin/env python3
"""
validate_spec.py — 校验 UI Spec YAML 文件
用法: python scripts/validate_spec.py .superdesigner/specs/MainCity.spec.yaml
退出码: 0=通过, 1=有错误
"""
import sys
import io
import yaml
from pathlib import Path

# Force UTF-8 output on Windows to support emoji/CJK characters
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def load_naming_rules() -> dict:
    config_path = Path(".superdesigner/naming-rules.config.yaml")
    if not config_path.exists():
        print("⚠️  naming-rules.config.yaml 不存在，跳过命名校验")
        return {}
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_interaction_knowledge() -> list:
    path = Path(".superdesigner/knowledge/interaction-patterns.yaml")
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("patterns", [])


def check_naming(node: dict, rules: dict, errors: list, warnings: list) -> None:
    node_id = node.get("id", "")
    node_type = node.get("type", "")
    if not node_id or not node_type:
        return

    prefix_map = rules.get("prefixes", {})
    expected_prefix = prefix_map.get(node_type, "")
    if expected_prefix and not node_id.startswith(expected_prefix):
        errors.append(
            f"[命名错误] '{node_id}' 类型为 {node_type}，"
            f"应以 '{expected_prefix}' 开头"
        )

    fmt = rules.get("format", {})
    case = fmt.get("case", "PascalCase")
    semantic = node_id.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")
    # Strip known prefix
    for prefix in prefix_map.values():
        if node_id.startswith(prefix):
            semantic = node_id[len(prefix):]
            break

    if case == "PascalCase" and semantic and not semantic[0].isupper():
        warnings.append(
            f"[命名建议] '{node_id}' 语义部分 '{semantic}' 建议首字母大写 (PascalCase)"
        )

    forbidden = rules.get("forbidden_words", [])
    for word in forbidden:
        if word.lower() in node_id.lower():
            errors.append(
                f"[命名错误] '{node_id}' 包含禁用词 '{word}'"
            )


def check_tbd(node: dict, warnings: list) -> None:
    """递归检查字段值为 TBD 的情况"""
    node_id = node.get("id", "?")
    tbd_fields = []

    def _scan(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.startswith("_"):
                    continue
                full_key = f"{prefix}.{k}" if prefix else k
                if v == "TBD":
                    tbd_fields.append(full_key)
                elif isinstance(v, (dict, list)):
                    _scan(v, full_key)
        elif isinstance(obj, list):
            for item in obj:
                _scan(item, prefix)

    _scan({k: v for k, v in node.items() if k not in ("children", "id", "type")})
    if tbd_fields:
        warnings.append(
            f"[待填写] '{node_id}' 以下字段待确认: {', '.join(tbd_fields)}"
        )


def check_confidence(node: dict, warnings: list) -> None:
    if node.get("_confidence") == "low":
        warnings.append(
            f"[低置信度] '{node.get('id', '?')}' 有低置信度推断字段，请人工确认后删除 _confidence 标记"
        )


def traverse(
    nodes: list,
    rules: dict,
    errors: list,
    warnings: list,
    depth: int = 0
) -> None:
    for node in nodes:
        check_naming(node, rules, errors, warnings)
        check_tbd(node, warnings)
        check_confidence(node, warnings)

        # Modal 关闭按钮检查
        if node.get("type") == "Modal":
            children = node.get("children", [])
            has_close = any(
                c.get("type") == "Button" and "close" in c.get("id", "").lower()
                for c in children
            )
            if not has_close:
                warnings.append(
                    f"[交互规范] Modal '{node.get('id', '?')}' 建议包含关闭按钮 (Btn_Close 或类似命名)"
                )

        # 递归子节点
        children = node.get("children", [])
        if children:
            traverse(children, rules, errors, warnings, depth + 1)


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python scripts/validate_spec.py <spec.yaml>")
        print("      python scripts/validate_spec.py .superdesigner/specs/MainCity.spec.yaml")
        sys.exit(1)

    spec_path = Path(sys.argv[1])
    if not spec_path.exists():
        print(f"错误：文件不存在 {spec_path}")
        sys.exit(1)

    with open(spec_path, encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    if not spec:
        print("错误：spec 文件为空或格式错误")
        sys.exit(1)

    rules = load_naming_rules()
    errors: list = []
    warnings: list = []

    components = spec.get("components", [])
    traverse(components, rules, errors, warnings)

    # 汇总输出
    screen = spec.get("meta", {}).get("screen", spec_path.stem)
    print(f"\n{'='*50}")
    print(f" 校验报告: {screen}")
    print(f"{'='*50}")

    if errors:
        print(f"\n❌ 错误 ({len(errors)}) — 必须修复后才能运行 /generate:")
        for e in errors:
            print(f"   {e}")

    if warnings:
        print(f"\n⚠️  警告 ({len(warnings)}) — 建议处理:")
        for w in warnings:
            print(f"   {w}")

    if not errors and not warnings:
        print("\n✅ 校验通过，无错误无警告")
    elif not errors:
        print(f"\n✅ 无命名错误，可以运行 /generate（但有 {len(warnings)} 条警告建议处理）")

    print()
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
