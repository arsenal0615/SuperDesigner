#!/usr/bin/env python3
"""
resolve_assets.py — 将 spec 中的 TBD source 字段匹配到实际资产路径
用法: python scripts/resolve_assets.py .superdesigner/specs/MainCity.spec.yaml
输出: 更新原 spec 文件 + 生成 .superdesigner/tmp/<spec>.unresolved.yaml（如有未匹配项）
"""
import sys
import yaml
from pathlib import Path
from difflib import SequenceMatcher


INDEX_PATH = Path(".superdesigner/asset-index.yaml")
SPRITE_TYPES = {"Image", "Button", "Panel", "Modal", "ProgressBar", "Tab", "Toggle", "Slider"}
PARTICLE_TYPES = {"Particle"}

# Prefixes to strip when building semantic query from node id
ID_PREFIXES = [
    "Btn_", "Img_", "Panel_", "Txt_", "Vfx_", "Bar_",
    "RT_", "Scroll_", "Tab_", "Toggle_", "Input_", "Grid_",
    "List_", "Modal_", "Slider_",
]


def load_index() -> dict:
    if not INDEX_PATH.exists():
        print(f"⚠️  {INDEX_PATH} 不存在，请先运行 /index-assets")
        return {}
    with open(INDEX_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def build_query(node: dict) -> str:
    """从节点 id 和 label 构建匹配查询词"""
    node_id = node.get("id", "")
    label = node.get("label", "")

    semantic = node_id
    for prefix in ID_PREFIXES:
        if node_id.startswith(prefix):
            semantic = node_id[len(prefix):]
            break

    parts = [semantic]
    if label:
        parts.append(label)
    return " ".join(parts)


def find_best_match(query: str, candidates: list) -> tuple:
    """返回 (best_asset_dict, confidence_str, score_float)"""
    best_score = 0.0
    best_asset = None

    for asset in candidates:
        name_score = similarity(query, asset.get("name", ""))
        tag_scores = [
            similarity(query, t) for t in asset.get("tags", [])
        ]
        tag_score = max(tag_scores, default=0.0)
        score = max(name_score, tag_score)

        if score > best_score:
            best_score = score
            best_asset = asset

    if best_score >= 0.7:
        confidence = "high"
    elif best_score >= 0.4:
        confidence = "medium"
    else:
        confidence = "low"

    return best_asset, confidence, best_score


def resolve_node(node: dict, index: dict, resolved_count: list, unresolved: list) -> None:
    """在 node 上就地修改 source 字段"""
    source = node.get("source")

    # Skip if already resolved (dict with 'resolved' key, or a plain non-TBD string)
    if isinstance(source, dict) and source.get("resolved") not in (None, "TBD"):
        return
    if isinstance(source, str) and source != "TBD":
        return
    # Also skip types that don't use source (e.g. Text, List, Grid, ScrollView, Tab)
    node_type = node.get("type", "")
    if node_type in {"Text", "List", "Grid", "ScrollView", "Tab", "InputField"}:
        return

    node_id = node.get("id", "?")
    query = build_query(node)

    # Choose candidate pool by type
    if node_type in PARTICLE_TYPES:
        candidates = index.get("particles", [])
    else:
        candidates = index.get("sprites", [])

    if not candidates:
        unresolved.append({
            "node_id": node_id,
            "type": node_type,
            "query": query,
            "reason": "asset-index 中无对应类型资产",
        })
        return

    best, confidence, score = find_best_match(query, candidates)

    if best and score >= 0.3:
        node["source"] = {
            "resolved": best["path"],
            "confidence": confidence,
            "score": round(score, 3),
        }
        print(f"  ✓ {node_id:<30} → {best['path']}  ({confidence}, {score:.2f})")
        resolved_count.append(1)
    else:
        node["source"] = "TBD"
        unresolved.append({
            "node_id": node_id,
            "type": node_type,
            "query": query,
            "reason": f"最高匹配得分 {score:.2f}，低于阈值 0.30",
        })
        print(f"  ✗ {node_id:<30} → TBD  ({query!r} 无匹配)")


def traverse_nodes(nodes: list, index: dict, resolved: list, unresolved: list) -> None:
    for node in nodes:
        resolve_node(node, index, resolved, unresolved)
        traverse_nodes(node.get("children", []), index, resolved, unresolved)


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python scripts/resolve_assets.py <spec.yaml>")
        print("      python scripts/resolve_assets.py .superdesigner/specs/MainCity.spec.yaml")
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

    index = load_index()
    resolved: list = []
    unresolved: list = []

    screen = spec.get("meta", {}).get("screen", spec_path.stem)
    print(f"\n=== 资产匹配：{screen} ===\n")

    traverse_nodes(spec.get("components", []), index, resolved, unresolved)

    # Write updated spec back
    with open(spec_path, "w", encoding="utf-8") as f:
        yaml.dump(spec, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"\n已更新：{spec_path}")

    # Summary
    print(f"\n匹配成功：{len(resolved)} 个  |  未匹配：{len(unresolved)} 个")

    if unresolved:
        tmp_dir = Path(".superdesigner/tmp")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        unresolved_path = tmp_dir / f"{spec_path.stem}.unresolved.yaml"
        with open(unresolved_path, "w", encoding="utf-8") as f:
            yaml.dump({"screen": screen, "unresolved": unresolved}, f,
                      allow_unicode=True, default_flow_style=False)
        print(f"未匹配清单：{unresolved_path}")
        print("运行 /resolve-assets 中的生图步骤可为未匹配资产生成图片")


if __name__ == "__main__":
    main()
