#!/usr/bin/env python3
"""
index_assets.py — 扫描引擎资产目录，生成 asset-index.yaml
用法:
  Unity: python scripts/index_assets.py --engine unity --path /path/to/UnityProject/Assets
  UE:    python scripts/index_assets.py --engine ue    --path /path/to/UEProject/Content
输出: .superdesigner/asset-index.yaml
"""
import sys
import yaml
import argparse
from pathlib import Path

SPRITE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".psd"}
FONT_EXTS = {".ttf", ".otf"}
AUDIO_EXTS = {".wav", ".mp3", ".ogg"}

# Keywords for automatic tag inference
TAG_KEYWORDS = {
    "btn": "button", "button": "button",
    "icon": "icon",
    "bg": "background", "background": "background",
    "frame": "frame", "border": "border",
    "panel": "panel",
    "bar": "bar", "hp": "hp", "exp": "exp", "mp": "mp",
    "bag": "bag", "inventory": "inventory",
    "shop": "shop", "store": "store",
    "common": "common", "shared": "shared",
    "popup": "popup", "dialog": "dialog", "modal": "modal",
    "tab": "tab",
    "close": "close", "confirm": "confirm", "cancel": "cancel",
    "slot": "slot", "item": "item",
    "hero": "hero", "player": "player",
    "skill": "skill", "buff": "buff",
    "gold": "gold", "coin": "coin",
    "title": "title", "header": "header",
    "arrow": "arrow", "back": "back",
    "loading": "loading", "progress": "progress",
}


def guess_tags(name: str, path_str: str) -> list[str]:
    """从文件名和路径推断语义标签，去重保序"""
    combined = (name + " " + path_str).lower().replace("_", " ").replace("-", " ")
    tags = []
    seen = set()
    for kw, tag in TAG_KEYWORDS.items():
        if kw in combined and tag not in seen:
            tags.append(tag)
            seen.add(tag)
    return tags


def is_particle_asset(path: Path, engine: str) -> bool:
    """判断是否为特效资产"""
    path_lower = str(path).lower()
    fx_keywords = {"fx", "effect", "particle", "vfx", "niagara"}
    if engine == "unity" and path.suffix.lower() == ".prefab":
        return any(kw in path_lower for kw in fx_keywords)
    if engine == "ue" and path.suffix.lower() == ".uasset":
        return any(kw in path_lower for kw in fx_keywords)
    return False


def scan_directory(root: Path, engine: str) -> dict:
    """扫描目录，返回分类后的资产列表"""
    index: dict = {"sprites": [], "fonts": [], "particles": [], "audio": []}
    root_parent = root.parent

    for file in root.rglob("*"):
        if not file.is_file():
            continue
        ext = file.suffix.lower()
        # Use forward slashes for cross-platform consistency
        rel_path = str(file.relative_to(root_parent)).replace("\\", "/")
        name = file.stem
        tags = guess_tags(name, rel_path)

        if ext in SPRITE_EXTS:
            entry = {"path": rel_path, "name": name}
            if tags:
                entry["tags"] = tags
            index["sprites"].append(entry)

        elif ext in FONT_EXTS:
            index["fonts"].append({"path": rel_path, "name": name})

        elif ext in AUDIO_EXTS:
            entry = {"path": rel_path, "name": name}
            if tags:
                entry["tags"] = tags
            index["audio"].append(entry)

        elif is_particle_asset(file, engine):
            entry = {"path": rel_path, "name": name}
            if tags:
                entry["tags"] = tags
            index["particles"].append(entry)

    return index


def main() -> None:
    parser = argparse.ArgumentParser(
        description="扫描引擎资产目录，生成 asset-index.yaml"
    )
    parser.add_argument(
        "--engine",
        choices=["unity", "ue"],
        required=True,
        help="目标引擎: unity 或 ue",
    )
    parser.add_argument(
        "--path",
        required=True,
        help="引擎资产根目录（Unity: Assets/, UE: Content/）",
    )
    args = parser.parse_args()

    root = Path(args.path)
    if not root.exists():
        print(f"错误：路径不存在 '{root}'")
        sys.exit(1)
    if not root.is_dir():
        print(f"错误：路径不是目录 '{root}'")
        sys.exit(1)

    print(f"扫描 [{args.engine}] 资产目录: {root}")
    index = scan_directory(root, args.engine)

    counts = {k: len(v) for k, v in index.items()}
    total = sum(counts.values())
    print(
        f"发现: {counts['sprites']} sprites, {counts['fonts']} fonts, "
        f"{counts['particles']} particles, {counts['audio']} audio  (共 {total} 条)"
    )

    out_path = Path(".superdesigner/asset-index.yaml")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(index, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"[OK] 已生成: {out_path}")


if __name__ == "__main__":
    main()
