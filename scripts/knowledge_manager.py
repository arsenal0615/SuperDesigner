#!/usr/bin/env python3
"""
knowledge_manager.py — 查看、禁用知识库条目
用法:
  python scripts/knowledge_manager.py list [--category visual|interaction|layout|naming]
  python scripts/knowledge_manager.py disable --id vp_001
  python scripts/knowledge_manager.py enable  --id vp_001
"""
import sys
import yaml
import argparse
from pathlib import Path

KNOWLEDGE_DIR = Path(".superdesigner/knowledge")
CATEGORY_FILES = {
    "visual":      "visual-patterns.yaml",
    "interaction": "interaction-patterns.yaml",
    "layout":      "layout-patterns.yaml",
    "naming":      "naming-patterns.yaml",
}


def load_patterns(category: str) -> list:
    path = KNOWLEDGE_DIR / CATEGORY_FILES[category]
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("patterns", [])


def save_patterns(category: str, patterns: list) -> None:
    path = KNOWLEDGE_DIR / CATEGORY_FILES[category]
    # Preserve existing file header comments is not possible with yaml.dump,
    # but we keep the structure consistent.
    existing = ""
    if path.exists():
        with open(path, encoding="utf-8") as f:
            existing = f.read()
        # Extract leading comment lines
        header_lines = []
        for line in existing.splitlines():
            if line.startswith("#"):
                header_lines.append(line)
            else:
                break
        header = "\n".join(header_lines) + "\n" if header_lines else ""
    else:
        header = ""

    body = yaml.dump({"patterns": patterns}, allow_unicode=True,
                     default_flow_style=False, sort_keys=False)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + body)


def cmd_list(args) -> None:
    categories = [args.category] if args.category else list(CATEGORY_FILES.keys())
    total = 0
    for cat in categories:
        patterns = load_patterns(cat)
        total += len(patterns)
        print(f"\n[{cat}] {len(patterns)} 条:")
        if not patterns:
            print("  （空）")
            continue
        for p in patterns:
            disabled = p.get("disabled", False)
            status = "禁用" if disabled else "启用"
            pid = p.get("id", "?")
            name = p.get("name", "")
            confidence = p.get("confidence", "?")
            usage = p.get("usage_count", 0)
            print(f"  [{status}] {pid} — {name}  (confidence={confidence}, 使用={usage}次)")
    print(f"\n共 {total} 条知识")


def set_disabled(args, disabled: bool) -> None:
    target_id = args.id
    found = False
    for cat in CATEGORY_FILES:
        patterns = load_patterns(cat)
        for p in patterns:
            if p.get("id") == target_id:
                p["disabled"] = disabled
                save_patterns(cat, patterns)
                action = "已禁用" if disabled else "已启用"
                print(f"{action}: {target_id} ({cat})")
                found = True
                break
        if found:
            break
    if not found:
        print(f"未找到 id={target_id!r} 的知识条目")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="SuperDesigner 知识库管理")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ls = sub.add_parser("list", help="列出知识条目")
    ls.add_argument("--category", choices=list(CATEGORY_FILES.keys()),
                    help="过滤类别")

    dis = sub.add_parser("disable", help="临时禁用知识条目")
    dis.add_argument("--id", required=True, help="条目 id，如 vp_001")

    en = sub.add_parser("enable", help="重新启用知识条目")
    en.add_argument("--id", required=True, help="条目 id，如 vp_001")

    args = parser.parse_args()

    if args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "disable":
        set_disabled(args, disabled=True)
    elif args.cmd == "enable":
        set_disabled(args, disabled=False)


if __name__ == "__main__":
    main()
