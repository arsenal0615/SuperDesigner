#!/usr/bin/env python3
"""
layout_regression.py — 生成 Unity adapter 前后对比指标

用法:
  python scripts/adapters/layout_regression.py <spec.yaml> [--output <metrics.json>]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from unity_adapter import AdapterSettings, build_payload


def run_metrics(spec_path: Path) -> dict:
    settings_no_norm = AdapterSettings(
        output_mode="v2",
        normalize=False,
        normalize_threshold=2,
        report_path=None,
        write_report=False,
        validate_contract=True,
    )
    payload_no_norm = build_payload(spec_path, settings_no_norm)

    settings_norm = AdapterSettings(
        output_mode="v2",
        normalize=True,
        normalize_threshold=2,
        report_path=None,
        write_report=False,
        validate_contract=True,
    )
    payload_norm = build_payload(spec_path, settings_norm)

    d0 = payload_no_norm.get("diagnostics", {})  # type: ignore[union-attr]
    d1 = payload_norm.get("diagnostics", {})  # type: ignore[union-attr]
    s0 = d0.get("summary", {})
    s1 = d1.get("summary", {})
    c0 = int(s0.get("collision_groups_before", 0))
    c1 = int(s1.get("collision_groups_after", c0))

    return {
        "screen": payload_norm.get("screen"),
        "spec_path": str(spec_path),
        "contract_version": payload_norm.get("contract_version"),
        "before": {
            "collision_groups": c0,
            "command_count": len(payload_no_norm.get("commands", [])),  # type: ignore[union-attr]
        },
        "after": {
            "collision_groups": c1,
            "command_count": len(payload_norm.get("commands", [])),  # type: ignore[union-attr]
            "normalized_groups": len(d1.get("normalization", {}).get("groups", [])),
            "semantic_fallbacks": len(d1.get("semantic_fallbacks", [])),
            "contract_valid": bool(d1.get("contract_validation", {}).get("valid", False)),
        },
        "improvement": {
            "collision_groups_reduced": c0 - c1,
            "collision_reduction_ratio": (0.0 if c0 == 0 else round((c0 - c1) / c0, 4)),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate layout regression metrics for unity adapter")
    parser.add_argument("spec", help="spec.yaml path")
    parser.add_argument("--output", type=str, default=None, help="output metrics json path")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        raise SystemExit(f"Spec file not found: {spec_path}")

    metrics = run_metrics(spec_path)
    text = json.dumps(metrics, ensure_ascii=False, indent=2)
    print(text)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
