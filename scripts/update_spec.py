#!/usr/bin/env python3
"""
update_spec.py — 对比新旧 spec，生成变更报告，检查动画安全性
用法: python scripts/update_spec.py <old_spec.yaml> <new_spec.yaml>
输出: .superdesigner/tmp/change-report-YYYYMMDD.yaml
"""
import sys
import yaml
from pathlib import Path
from datetime import date


ANIMATION_REGISTRY_PATH = Path(".superdesigner/animation-registry.yaml")


def load_animation_registry() -> dict[str, list[str]]:
    """返回 {node_id: [anim_id, ...]} 映射"""
    if not ANIMATION_REGISTRY_PATH.exists():
        return {}
    with open(ANIMATION_REGISTRY_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    mapping: dict[str, list[str]] = {}
    for anim in data.get("animations", []):
        for bound in anim.get("bound_nodes", []):
            nid = bound.get("node_id", "")
            if nid:
                mapping.setdefault(nid, []).append(anim["id"])
    return mapping


def flatten_nodes(nodes: list, result: dict | None = None) -> dict:
    if result is None:
        result = {}
    for node in nodes:
        nid = node.get("id")
        if nid:
            result[nid] = node
        flatten_nodes(node.get("children", []), result)
    return result


def diff_specs(
    old_nodes: dict,
    new_nodes: dict,
    anim_registry: dict,
) -> dict:
    report: dict = {
        "added": [],
        "modified": [],
        "deleted": [],
        "animation_warnings": [],
        "locked_skipped": [],
    }

    # Check new/modified nodes
    for nid, new_node in new_nodes.items():
        if nid not in old_nodes:
            report["added"].append({"node_id": nid, "action": "insert"})
            continue

        old_node = old_nodes[nid]
        ownership = old_node.get("_ownership", {})
        locked = ownership.get("locked", False)
        modified_by = ownership.get("last_modified_by", "ai")

        if locked:
            report["locked_skipped"].append({"node_id": nid, "reason": ownership.get("lock_reason", "")})
            continue

        # Find changed fields (ignore private _ fields and children)
        changed_fields = [
            k for k in set(list(new_node.keys()) + list(old_node.keys()))
            if not k.startswith("_")
            and k != "children"
            and new_node.get(k) != old_node.get(k)
        ]

        if changed_fields:
            action = "partial_update" if modified_by in ("ui", "ue", "designer") else "overwrite"
            report["modified"].append({
                "node_id": nid,
                "type": "modified",
                "changed_fields": changed_fields,
                "ownership": modified_by,
                "action": action,
            })

    # Check deleted nodes
    for nid in old_nodes:
        if nid not in new_nodes:
            anims = anim_registry.get(nid, [])
            if anims:
                report["animation_warnings"].append({
                    "node_id": nid,
                    "animations": anims,
                    "action": "blocked_by_animation",
                })
                report["deleted"].append({
                    "node_id": nid,
                    "action": "blocked_by_animation",
                })
            else:
                report["deleted"].append({"node_id": nid, "action": "delete"})

    return report


def main() -> None:
    if len(sys.argv) < 3:
        print("用法: python scripts/update_spec.py <old.yaml> <new.yaml>")
        sys.exit(1)

    old_path = Path(sys.argv[1])
    new_path = Path(sys.argv[2])

    for p in (old_path, new_path):
        if not p.exists():
            print(f"错误：文件不存在 {p}")
            sys.exit(1)

    with open(old_path, encoding="utf-8") as f:
        old_spec = yaml.safe_load(f) or {}
    with open(new_path, encoding="utf-8") as f:
        new_spec = yaml.safe_load(f) or {}

    old_nodes = flatten_nodes(old_spec.get("components", []))
    new_nodes = flatten_nodes(new_spec.get("components", []))
    anim_registry = load_animation_registry()

    report = diff_specs(old_nodes, new_nodes, anim_registry)

    # Summary
    summary = {
        "added": len(report["added"]),
        "modified": len(report["modified"]),
        "deleted": len(report["deleted"]),
        "animation_warnings": len(report["animation_warnings"]),
        "locked_skipped": len(report["locked_skipped"]),
    }

    output = {"summary": summary, "changes": {
        "added": report["added"],
        "modified": report["modified"],
        "deleted": report["deleted"],
        "animation_warnings": report["animation_warnings"],
        "locked_skipped": report["locked_skipped"],
    }}

    today = date.today().strftime("%Y%m%d")
    tmp_dir = Path(".superdesigner/tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    report_path = tmp_dir / f"change-report-{today}.yaml"
    with open(report_path, "w", encoding="utf-8") as f:
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"\n=== 变更报告 ===")
    print(f"新增: {summary['added']}  修改: {summary['modified']}  "
          f"删除: {summary['deleted']}  动画警告: {summary['animation_warnings']}  "
          f"跳过(locked): {summary['locked_skipped']}")

    if report["animation_warnings"]:
        print("\n动画警告（以下节点有绑定动画，删除已阻断，请 UE 工程师处理）：")
        for w in report["animation_warnings"]:
            print(f"  - {w['node_id']}: {w['animations']}")

    print(f"\n报告已写入: {report_path}")


if __name__ == "__main__":
    main()
