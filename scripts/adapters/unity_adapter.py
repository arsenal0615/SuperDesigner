#!/usr/bin/env python3
"""
unity_adapter.py — 将 UI Spec YAML 转换为 Unity MCP 调用序列

默认输出 v2（Unity MCP batch_execute 可直接执行的 commands）。
如需兼容旧输出，可指定 --output legacy。
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

CONTRACT_VERSION_V2 = "unity-mcp-command-v2"
CONTRACT_VERSION_LEGACY = "legacy-method-v1"

ANCHOR_MAP = {
    "top-left": {"min": [0.0, 1.0], "max": [0.0, 1.0]},
    "top-center": {"min": [0.5, 1.0], "max": [0.5, 1.0]},
    "top-right": {"min": [1.0, 1.0], "max": [1.0, 1.0]},
    "middle-left": {"min": [0.0, 0.5], "max": [0.0, 0.5]},
    "center": {"min": [0.5, 0.5], "max": [0.5, 0.5]},
    "middle-right": {"min": [1.0, 0.5], "max": [1.0, 0.5]},
    "bottom-left": {"min": [0.0, 0.0], "max": [0.0, 0.0]},
    "bottom-center": {"min": [0.5, 0.0], "max": [0.5, 0.0]},
    "bottom-right": {"min": [1.0, 0.0], "max": [1.0, 0.0]},
    "stretch": {"min": [0.0, 0.0], "max": [1.0, 1.0]},
}

TYPE_TO_COMPONENTS = {
    "Panel": ["RectTransform"],
    "Button": ["Image", "Button"],
    "Text": ["TextMeshProUGUI"],
    "Image": ["Image"],
    "List": ["RectTransform", "ScrollRect", "VerticalLayoutGroup"],
    "Grid": ["RectTransform", "ScrollRect", "GridLayoutGroup"],
    "ScrollView": ["RectTransform", "ScrollRect"],
    "Tab": ["RectTransform", "ToggleGroup"],
    "Toggle": ["RectTransform", "Toggle"],
    "InputField": ["RectTransform", "TMP_InputField"],
    "ProgressBar": ["RectTransform", "Slider"],
    "Particle": ["RectTransform", "ParticleSystem"],
    "RenderTexture": ["RectTransform", "RawImage"],
    "Modal": ["RectTransform", "CanvasGroup", "Image"],
    "Slider": ["RectTransform", "Slider"],
}

VALID_TOOLS = {"manage_gameobject", "manage_components"}


@dataclass
class AdapterSettings:
    output_mode: str
    normalize: bool
    normalize_threshold: int
    report_path: Path | None
    write_report: bool
    validate_contract: bool


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_vec2(v: list[float] | tuple[float, float]) -> dict[str, float]:
    return {"x": float(v[0]), "y": float(v[1])}


def resolve_source(source: Any) -> str | None:
    if source is None or source == "TBD":
        return None
    if isinstance(source, dict):
        resolved = source.get("resolved")
        return None if resolved == "TBD" else resolved
    if isinstance(source, str):
        return source
    return None


def collect_tbd_fields(node: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for k, v in node.items():
        if k.startswith("_") or k == "children":
            continue
        if v == "TBD":
            out.append(k)
            continue
        if isinstance(v, dict):
            for k2, v2 in v.items():
                if v2 == "TBD":
                    out.append(f"{k}.{k2}")
                elif isinstance(v2, dict):
                    for k3, v3 in v2.items():
                        if v3 == "TBD":
                            out.append(f"{k}.{k2}.{k3}")
    return out


def layout_override(node: dict[str, Any]) -> dict[str, Any]:
    return node.get("_layout") if isinstance(node.get("_layout"), dict) else {}


def estimate_wrap_size(node: dict[str, Any], diagnostics: dict[str, Any]) -> tuple[float, float]:
    node_id = node.get("id", "unknown")
    node_type = node.get("type", "Panel")
    if node_type == "Text":
        font = node.get("font", {}) if isinstance(node.get("font"), dict) else {}
        font_size = float(font.get("size", 22) or 22)
        content = node.get("content") or ""
        visible_chars = len(str(content))
        width = max(40.0, min(1200.0, visible_chars * font_size * 0.55 + 16.0))
        height = max(24.0, font_size * 1.4 + 8.0)
        diagnostics["semantic_fallbacks"].append(
            {
                "node_id": node_id,
                "field": "size",
                "semantic": "wrap",
                "fallback": {"sizeDelta": [round(width, 2), round(height, 2)]},
                "reason": "text_wrap_estimate",
            }
        )
        return width, height

    width = 180.0
    height = 60.0 if node_type in ("Button", "InputField", "Slider") else 100.0
    diagnostics["semantic_fallbacks"].append(
        {
            "node_id": node_id,
            "field": "size",
            "semantic": "wrap",
            "fallback": {"sizeDelta": [width, height]},
            "reason": "generic_wrap_fallback",
        }
    )
    return width, height


def resolve_size_strategy(node: dict[str, Any], diagnostics: dict[str, Any]) -> dict[str, Any]:
    size = node.get("size", [100, 100])
    if node.get("anchor") == "stretch":
        return {"mode": "stretch", "sizeDelta": [0.0, 0.0]}
    if size == "stretch" or size == ["fill", "fill"]:
        return {"mode": "stretch", "sizeDelta": [0.0, 0.0]}
    if not isinstance(size, list) or len(size) < 2:
        diagnostics["semantic_fallbacks"].append(
            {
                "node_id": node.get("id"),
                "field": "size",
                "semantic": "invalid",
                "fallback": {"sizeDelta": [100.0, 100.0]},
                "reason": "size_missing_or_invalid",
            }
        )
        return {"mode": "fixed", "sizeDelta": [100.0, 100.0]}

    w_raw, h_raw = size[0], size[1]
    width_fill = w_raw == "fill"
    height_fill = h_raw == "fill"
    width_wrap = w_raw == "wrap"
    height_wrap = h_raw == "wrap"

    if width_fill or height_fill:
        w = 0.0 if width_fill else (float(w_raw) if isinstance(w_raw, (int, float)) else 100.0)
        h = 0.0 if height_fill else (float(h_raw) if isinstance(h_raw, (int, float)) else 100.0)
        return {
            "mode": "partial_fill",
            "sizeDelta": [w, h],
            "fill_axes": {"x": width_fill, "y": height_fill},
        }

    if width_wrap or height_wrap:
        est_w, est_h = estimate_wrap_size(node, diagnostics)
        w = est_w if width_wrap else (float(w_raw) if isinstance(w_raw, (int, float)) else 100.0)
        h = est_h if height_wrap else (float(h_raw) if isinstance(h_raw, (int, float)) else 100.0)
        return {"mode": "wrap", "sizeDelta": [w, h]}

    w = float(w_raw) if isinstance(w_raw, (int, float)) else 100.0
    h = float(h_raw) if isinstance(h_raw, (int, float)) else 100.0
    return {"mode": "fixed", "sizeDelta": [w, h]}


def detect_collision_groups(parent: dict[str, Any], threshold: int) -> list[dict[str, Any]]:
    children = parent.get("children", [])
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for child in children:
        if not isinstance(child, dict):
            continue
        off = child.get("offset", [0, 0])
        if not (isinstance(off, list) and len(off) >= 2):
            continue
        key = (child.get("anchor", "top-left"), float(off[0]), float(off[1]), child.get("type", "Panel"))
        buckets.setdefault(key, []).append(child)
    groups = []
    for key, group in buckets.items():
        if len(group) >= threshold:
            groups.append({"signature": key, "nodes": group})
    return groups


def count_collisions(tree: list[dict[str, Any]], threshold: int) -> int:
    count = 0

    def walk(parent: dict[str, Any]) -> None:
        nonlocal count
        count += len(detect_collision_groups(parent, threshold))
        for child in parent.get("children", []):
            if isinstance(child, dict):
                walk(child)

    for root in tree:
        walk(root)
    return count


def infer_stack_axis(parent: dict[str, Any], group_nodes: list[dict[str, Any]]) -> str:
    override = layout_override(parent).get("stack")
    if override in ("horizontal", "vertical"):
        return override

    parent_id = str(parent.get("id", ""))
    hint = parent_id.lower()
    if any(t in hint for t in ("buttons", "action", "row", "tab")):
        return "horizontal"
    if any(str(n.get("id", "")).startswith("Btn_") for n in group_nodes):
        return "horizontal"
    return "vertical"


def estimate_node_size_for_spacing(node: dict[str, Any], diagnostics: dict[str, Any]) -> tuple[float, float]:
    size_info = resolve_size_strategy(node, diagnostics)
    sd = size_info.get("sizeDelta", [100.0, 100.0])
    return float(sd[0]), float(sd[1])


def normalize_layout_tree(tree: list[dict[str, Any]], diagnostics: dict[str, Any], threshold: int = 2) -> None:
    def walk(parent: dict[str, Any]) -> None:
        parent_override = layout_override(parent)
        if parent_override.get("normalize", True):
            groups = detect_collision_groups(parent, threshold)
            for group in groups:
                nodes = sorted(group["nodes"], key=lambda n: str(n.get("id", "")))
                axis = infer_stack_axis(parent, nodes)
                gap = float(parent_override.get("gap", 12))
                before = {n.get("id"): deepcopy(n.get("offset", [0, 0])) for n in nodes}
                base_x, base_y = before[nodes[0].get("id")] if nodes else (0, 0)
                cursor = 0.0
                for node in nodes:
                    node_override = layout_override(node)
                    if node_override.get("normalize", True) is False:
                        continue
                    w, h = estimate_node_size_for_spacing(node, diagnostics)
                    if axis == "horizontal":
                        node["offset"] = [round(base_x + cursor, 2), round(base_y, 2)]
                        cursor += w + gap
                    else:
                        node["offset"] = [round(base_x, 2), round(base_y - cursor, 2)]
                        cursor += h + gap
                diagnostics["normalization"]["groups"].append(
                    {
                        "parent_id": parent.get("id"),
                        "signature": list(group["signature"]),
                        "axis": axis,
                        "reason": "sibling_collision",
                        "nodes": [
                            {
                                "node_id": n.get("id"),
                                "before_offset": before.get(n.get("id")),
                                "after_offset": n.get("offset"),
                            }
                            for n in nodes
                        ],
                    }
                )

        for child in parent.get("children", []):
            if isinstance(child, dict):
                walk(child)

    for root in tree:
        walk(root)


def build_legacy_methods(spec: dict[str, Any], spec_path: Path) -> list[dict[str, Any]]:
    """兼容旧输出格式：method + params."""

    def node_to_legacy(node: dict[str, Any], parent_name: str) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        node_id = node.get("id", "")
        node_type = node.get("type", "Panel")
        anchor = node.get("anchor", "top-left")
        size = node.get("size", [100, 100])
        offset = node.get("offset", [0, 0])
        z_order = node.get("z_order")
        opacity = node.get("opacity")
        anchor_data = ANCHOR_MAP.get(anchor, ANCHOR_MAP["top-left"])
        components = TYPE_TO_COMPONENTS.get(node_type, ["RectTransform"])

        call: dict[str, Any] = {
            "method": "CreateUIGameObject",
            "params": {
                "name": node_id,
                "parent": parent_name,
                "components": components,
                "anchorMin": anchor_data["min"],
                "anchorMax": anchor_data["max"],
            },
        }

        if anchor == "stretch" or size in (["fill", "fill"], "stretch"):
            call["params"]["offsetMin"] = [0, 0]
            call["params"]["offsetMax"] = [0, 0]
        else:
            w = size[0] if isinstance(size, list) and isinstance(size[0], (int, float)) else 100
            h = size[1] if isinstance(size, list) and len(size) > 1 and isinstance(size[1], (int, float)) else 100
            call["params"]["sizeDelta"] = [w, h]
            if offset:
                call["params"]["anchoredPosition"] = offset

        if z_order is not None:
            call["params"]["siblingIndex"] = z_order
        if opacity is not None and opacity != 1.0:
            call["params"]["alpha"] = opacity

        if node_type in ("Image", "Button", "Toggle", "Panel", "Modal"):
            source_path = resolve_source(node.get("source"))
            if source_path:
                call["params"]["spritePath"] = source_path
            if node.get("slice_type") == "nine_slice":
                call["params"]["imageType"] = "Sliced"
                if node.get("slice_border"):
                    call["params"]["pixelsPerUnitMultiplier"] = 1

        if node_type in ("Text", "Button"):
            font = node.get("font", {})
            if isinstance(font, dict):
                if font.get("family") and font["family"] != "TBD":
                    call["params"]["fontAssetPath"] = font["family"]
                if font.get("size"):
                    call["params"]["fontSize"] = font["size"]
                if font.get("color"):
                    call["params"]["fontColor"] = font["color"]
            content = node.get("content") or node.get("label", "")
            if content and content != "TBD":
                call["params"]["text"] = content

        if node_type in ("List", "Grid"):
            gap = node.get("gap", [0, 0])
            padding = node.get("padding", [0, 0, 0, 0])
            call["params"]["spacing"] = gap
            call["params"]["padding"] = padding
            if node_type == "Grid":
                call["params"]["constraintCount"] = node.get("columns", 2)

        tbd_fields = collect_tbd_fields(node)
        if tbd_fields:
            call["params"]["inspectorComment"] = f"[SuperDesigner] 待填写: {', '.join(tbd_fields)}"

        calls.append(call)
        for child in node.get("children", []):
            calls.extend(node_to_legacy(child, parent_name=node_id))
        return calls

    meta = spec.get("meta", {})
    screen_name = meta.get("screen", spec_path.stem)
    size = meta.get("size", [1920, 1080])
    all_calls = [
        {
            "method": "CreateCanvas",
            "params": {
                "name": screen_name,
                "renderMode": "ScreenSpaceOverlay",
                "referenceResolution": size,
                "output_contract_version": CONTRACT_VERSION_LEGACY,
            },
        }
    ]
    for component in spec.get("components", []):
        all_calls.extend(node_to_legacy(component, parent_name=screen_name))
    return all_calls


def push_component_set(
    commands: list[dict[str, Any]],
    target: str,
    component_type: str,
    prop: str,
    value: Any,
) -> None:
    commands.append(
        {
            "tool": "manage_components",
            "params": {
                "action": "set_property",
                "target": target,
                "search_method": "by_name",
                "component_type": component_type,
                "property": prop,
                "value": value,
            },
        }
    )


def build_v2_commands(spec: dict[str, Any], spec_path: Path, diagnostics: dict[str, Any]) -> dict[str, Any]:
    meta = spec.get("meta", {})
    screen_name = str(meta.get("screen", spec_path.stem))
    system_name = str(meta.get("system", "UnknownSystem"))
    size = meta.get("size", [1920, 1080])

    commands: list[dict[str, Any]] = []
    commands.append(
        {
            "tool": "manage_gameobject",
            "params": {
                "action": "create",
                "name": screen_name,
                "components_to_add": ["Canvas", "CanvasScaler", "GraphicRaycaster"],
            },
        }
    )
    push_component_set(
        commands=commands,
        target=screen_name,
        component_type="CanvasScaler",
        prop="referenceResolution",
        value={"x": float(size[0]), "y": float(size[1])},
    )

    def walk(node: dict[str, Any], parent_name: str) -> None:
        node_id = str(node.get("id", ""))
        node_type = str(node.get("type", "Panel"))
        if not node_id:
            return

        components_to_add = TYPE_TO_COMPONENTS.get(node_type, ["RectTransform"])
        if not components_to_add:
            components_to_add = ["RectTransform"]

        commands.append(
            {
                "tool": "manage_gameobject",
                "params": {
                    "action": "create",
                    "name": node_id,
                    "parent": parent_name,
                    "components_to_add": components_to_add,
                },
            }
        )

        anchor = str(node.get("anchor", "top-left"))
        anchor_data = deepcopy(ANCHOR_MAP.get(anchor, ANCHOR_MAP["top-left"]))
        size_strategy = resolve_size_strategy(node, diagnostics)
        fill_axes = size_strategy.get("fill_axes", {"x": False, "y": False})
        if fill_axes.get("x"):
            anchor_data["min"][0] = 0.0
            anchor_data["max"][0] = 1.0
        if fill_axes.get("y"):
            anchor_data["min"][1] = 0.0
            anchor_data["max"][1] = 1.0

        push_component_set(commands, node_id, "RectTransform", "anchorMin", to_vec2(anchor_data["min"]))
        push_component_set(commands, node_id, "RectTransform", "anchorMax", to_vec2(anchor_data["max"]))
        push_component_set(commands, node_id, "RectTransform", "pivot", to_vec2(anchor_data["min"]))

        offset = node.get("offset", [0, 0])
        if isinstance(offset, list) and len(offset) >= 2:
            push_component_set(
                commands,
                node_id,
                "RectTransform",
                "anchoredPosition",
                {"x": float(offset[0]), "y": float(offset[1])},
            )

        size_delta = size_strategy.get("sizeDelta")
        if isinstance(size_delta, list) and len(size_delta) == 2:
            push_component_set(
                commands,
                node_id,
                "RectTransform",
                "sizeDelta",
                {"x": float(size_delta[0]), "y": float(size_delta[1])},
            )

        if size_strategy.get("mode") == "stretch":
            push_component_set(commands, node_id, "RectTransform", "offsetMin", {"x": 0.0, "y": 0.0})
            push_component_set(commands, node_id, "RectTransform", "offsetMax", {"x": 0.0, "y": 0.0})

        if node_type == "Text":
            content = node.get("content")
            if isinstance(content, str) and content and content != "TBD":
                push_component_set(commands, node_id, "TextMeshProUGUI", "text", content)
            font = node.get("font", {})
            if isinstance(font, dict) and isinstance(font.get("size"), (int, float)):
                push_component_set(commands, node_id, "TextMeshProUGUI", "fontSize", float(font["size"]))

        if node_type == "Button":
            label = node.get("label") or node.get("content")
            if isinstance(label, str) and label and label != "TBD":
                push_component_set(commands, node_id, "Button", "interactable", bool(node.get("interactable", True)))
                diagnostics["semantic_fallbacks"].append(
                    {
                        "node_id": node_id,
                        "field": "button.label",
                        "semantic": "inline_label",
                        "fallback": {"note": "Button text should be child Text node"},
                        "reason": "no_direct_button_text_field",
                    }
                )

        tbd_fields = collect_tbd_fields(node)
        if tbd_fields:
            push_component_set(
                commands,
                node_id,
                "RectTransform",
                "name",
                f"{node_id} [SuperDesigner: 待填写 {', '.join(tbd_fields)}]",
            )

        for child in node.get("children", []):
            if isinstance(child, dict):
                walk(child, node_id)

    for root in spec.get("components", []):
        if isinstance(root, dict):
            walk(root, screen_name)

    return {
        "schema": "unity-mcp-batch",
        "contract_version": CONTRACT_VERSION_V2,
        "screen": screen_name,
        "system": system_name,
        "source_spec": str(spec_path),
        "generated_at": utc_now_iso(),
        "commands": commands,
    }


def validate_v2_contract(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for idx, cmd in enumerate(commands):
        if not isinstance(cmd, dict):
            errors.append({"index": idx, "field": "command", "message": "command must be object"})
            continue
        tool = cmd.get("tool")
        params = cmd.get("params")
        if tool not in VALID_TOOLS:
            errors.append({"index": idx, "field": "tool", "message": f"unsupported tool: {tool}"})
        if not isinstance(params, dict):
            errors.append({"index": idx, "field": "params", "message": "params must be object"})
            continue
        if tool == "manage_gameobject":
            if "action" not in params:
                errors.append({"index": idx, "field": "params.action", "message": "missing action"})
            if "name" not in params and params.get("action") == "create":
                errors.append({"index": idx, "field": "params.name", "message": "missing name for create"})
        if tool == "manage_components":
            required = ("action", "target", "component_type", "property")
            for req in required:
                if req not in params:
                    errors.append({"index": idx, "field": f"params.{req}", "message": "missing required field"})
    return errors


def summarize_tree(components: list[dict[str, Any]]) -> dict[str, Any]:
    total_nodes = 0
    tbd_nodes = 0
    for node in components:
        stack = [node]
        while stack:
            cur = stack.pop()
            total_nodes += 1
            if collect_tbd_fields(cur):
                tbd_nodes += 1
            stack.extend(ch for ch in cur.get("children", []) if isinstance(ch, dict))
    return {"total_nodes": total_nodes, "nodes_with_tbd": tbd_nodes}


def build_payload(spec_path: Path, settings: AdapterSettings) -> dict[str, Any] | list[dict[str, Any]]:
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    components = spec.get("components", [])
    if not isinstance(components, list):
        raise ValueError("spec.components 必须是数组")

    diagnostics: dict[str, Any] = {
        "normalization": {"enabled": settings.normalize, "groups": []},
        "semantic_fallbacks": [],
        "contract_validation": {"enabled": settings.validate_contract, "valid": True, "errors": []},
        "summary": summarize_tree([c for c in components if isinstance(c, dict)]),
    }
    diagnostics["summary"]["collision_groups_before"] = count_collisions(
        [c for c in components if isinstance(c, dict)],
        settings.normalize_threshold,
    )

    working_spec = deepcopy(spec)
    if settings.normalize:
        normalize_layout_tree(
            [c for c in working_spec.get("components", []) if isinstance(c, dict)],
            diagnostics=diagnostics,
            threshold=settings.normalize_threshold,
        )
    diagnostics["summary"]["collision_groups_after"] = count_collisions(
        [c for c in working_spec.get("components", []) if isinstance(c, dict)],
        settings.normalize_threshold,
    )

    if settings.output_mode == "legacy":
        payload = build_legacy_methods(working_spec, spec_path)
        envelope = {
            "legacy_mode": True,
            "contract_version": CONTRACT_VERSION_LEGACY,
            "generated_at": utc_now_iso(),
            "source_spec": str(spec_path),
            "methods": payload,
            "diagnostics": diagnostics,
        }
        if settings.write_report and settings.report_path:
            settings.report_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    payload = build_v2_commands(working_spec, spec_path, diagnostics)
    commands = payload.get("commands", [])
    if settings.validate_contract:
        errors = validate_v2_contract(commands)
        diagnostics["contract_validation"]["errors"] = errors
        diagnostics["contract_validation"]["valid"] = len(errors) == 0
    payload["diagnostics"] = diagnostics

    if settings.write_report and settings.report_path:
        settings.report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将 UI Spec YAML 转换为 Unity MCP 调用序列")
    parser.add_argument("spec", help="spec.yaml 路径")
    parser.add_argument(
        "--output",
        choices=("v2", "legacy"),
        default="v2",
        help="输出模式：v2 为 Unity MCP 可执行命令；legacy 为旧 method+params 格式",
    )
    parser.add_argument("--no-normalize", action="store_true", help="关闭布局冲突归一化")
    parser.add_argument(
        "--normalize-threshold",
        type=int,
        default=2,
        help="同一父节点下，达到该数量的同签名节点触发归一化（默认 2）",
    )
    parser.add_argument("--report", type=str, default=None, help="可选：写出机器可读生成报告 JSON")
    parser.add_argument("--no-report", action="store_true", help="关闭默认报告写出")
    parser.add_argument("--no-validate-contract", action="store_true", help="关闭 v2 合同校验")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"错误：文件不存在 {spec_path}", file=sys.stderr)
        raise SystemExit(1)

    settings = AdapterSettings(
        output_mode=args.output,
        normalize=not args.no_normalize,
        normalize_threshold=max(2, args.normalize_threshold),
        report_path=Path(args.report) if args.report else Path(".superdesigner/tmp") / f"{spec_path.stem}.unity-report.json",
        write_report=not args.no_report,
        validate_contract=not args.no_validate_contract,
    )
    payload = build_payload(spec_path=spec_path, settings=settings)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
