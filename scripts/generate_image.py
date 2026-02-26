#!/usr/bin/env python3
"""
generate_image.py — 为未匹配资产调用 Gemini 生图
用法: python scripts/generate_image.py <spec.yaml> [--variants N] [--model MODEL]
依赖: pip install google-genai pyyaml
环境变量: GEMINI_API_KEY

支持的模型：
  Imagen 系列（generate_images接口）：
    imagen-4.0-generate-001 / imagen-4.0-fast-generate-001 / imagen-4.0-ultra-generate-001
  Gemini 系列（generateContent接口）：
    gemini-3-pro-image-preview / gemini-2.0-flash-exp-image-generation / gemini-2.5-flash-image
"""
import sys
import os
import yaml
import argparse
import time
import builtins
from pathlib import Path
from typing import Callable, Any

STYLE_GUIDE_PATH = Path(".superdesigner/style/style-guide.yaml")
PENDING_DIR = Path(".superdesigner/generated-assets/pending")

# 使用 generate_images 接口的 Imagen 模型前缀
IMAGEN_MODEL_PREFIXES = ("imagen-",)

DEFAULT_MODEL = "gemini-3-pro-image-preview"

DEFAULT_TIMEOUT_MS = int(os.environ.get("GEMINI_TIMEOUT_MS", "600000"))
DEFAULT_MAX_RETRIES = int(os.environ.get("GEMINI_MAX_RETRIES", "3"))
DEFAULT_RETRY_BACKOFF_MS = int(os.environ.get("GEMINI_RETRY_BACKOFF_MS", "2000"))


def _setup_stdio_utf8() -> None:
    """Force UTF-8 console output to avoid mojibake in Windows terminals."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                # Keep default encoding if runtime doesn't allow reconfigure.
                pass


def _safe_print(*args, **kwargs) -> None:
    """Best-effort print that won't fail on encoding mismatch."""
    sep = kwargs.pop("sep", " ")
    end = kwargs.pop("end", "\n")
    file = kwargs.pop("file", sys.stdout)
    flush = kwargs.pop("flush", False)
    if kwargs:
        # Preserve behavior for unsupported keyword args.
        builtins.print(*args, sep=sep, end=end, file=file, flush=flush, **kwargs)
        return

    text = sep.join(str(a) for a in args) + end
    try:
        file.write(text)
    except UnicodeEncodeError:
        enc = getattr(file, "encoding", None) or "utf-8"
        file.write(text.encode(enc, errors="replace").decode(enc, errors="replace"))
    if flush:
        try:
            file.flush()
        except Exception:
            pass


_setup_stdio_utf8()
print = _safe_print  # type: ignore[assignment]


def load_style_guide() -> dict:
    if not STYLE_GUIDE_PATH.exists():
        return {}
    with open(STYLE_GUIDE_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_prompt(item: dict, style: dict) -> str:
    """Build prompt for a missing asset"""
    node_id = item.get("node_id", "unknown")
    node_type = item.get("type", "Image")
    query = item.get("query", node_id)

    art_style = style.get("art_style", "game UI")
    keywords = " ".join(style.get("prompt_keywords", ["game UI", "transparent PNG"]))

    subject = f"game UI {node_type.lower()} element, {query}"
    return f"{subject}, {art_style}, {keywords}"


def _is_imagen_model(model: str) -> bool:
    return any(model.startswith(p) for p in IMAGEN_MODEL_PREFIXES)


def _is_retryable_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    retryable_signals = (
        "429",
        "503",
        "504",
        "resource_exhausted",
        "deadline_exceeded",
        "readtimeout",
        "timed out",
        "temporarily unavailable",
    )
    return any(s in msg for s in retryable_signals)


def _with_retries(
    task: Callable[[], Any],
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_ms: int = DEFAULT_RETRY_BACKOFF_MS,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return task()
        except Exception as exc:
            last_error = exc
            if attempt >= max_retries or not _is_retryable_error(exc):
                raise
            wait_ms = attempt * backoff_ms
            print(f"  ⚠ 请求失败，重试 {attempt}/{max_retries}，等待 {wait_ms}ms: {exc}")
            time.sleep(wait_ms / 1000.0)
    if last_error:
        raise last_error
    raise RuntimeError("重试失败（未知错误）")


def _generate_via_imagen(client, model: str, prompt: str, variants: int, base_output_path: Path) -> list[Path]:
    """使用 Imagen predict 接口生图（imagen-* 系列）"""
    from google.genai import types as genai_types  # type: ignore

    result = client.models.generate_images(
        model=model,
        prompt=prompt,
        config=genai_types.GenerateImagesConfig(number_of_images=variants),
    )
    saved = []
    for i, generated in enumerate(result.generated_images, start=1):
        out_path = base_output_path.parent / f"{base_output_path.stem}_v{i}.png"
        out_path.write_bytes(generated.image.image_bytes)
        saved.append(out_path)
        print(f"  → 已生成: {out_path}")
    return saved


def _generate_via_gemini(
    client,
    model: str,
    prompt: str,
    variants: int,
    base_output_path: Path,
    max_retries: int = DEFAULT_MAX_RETRIES,
    aspect_ratio: str | None = None,
    image_size: str | None = None,
) -> list[Path]:
    """使用 generateContent 接口生图（gemini-* 系列）。
    支持思考模型（gemini-3-pro-image-preview 等）：自动跳过 thought 中间图，
    仅保存最终非 thought 图片。
    """
    from google.genai import types as genai_types  # type: ignore

    saved = []
    for i in range(1, variants + 1):
        config_kwargs = {
            "response_modalities": ["TEXT", "IMAGE"],
        }
        if aspect_ratio or image_size:
            config_kwargs["image_config"] = genai_types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )

        response = _with_retries(
            lambda: client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(**config_kwargs),
            ),
            max_retries=max_retries,
        )
        written = False
        # 官方推荐用 response.parts；思考模型会在 thought=True 的 part 里产出中间图
        parts = list(getattr(response, "parts", []) or [])
        if not parts and getattr(response, "candidates", None):
            # 兼容某些 SDK 响应结构
            try:
                parts = list(response.candidates[0].content.parts)
            except Exception:
                parts = []
        for part in parts:
            # 跳过 Thinking 阶段的中间思考图（thought=True）
            if getattr(part, "thought", False):
                continue
            # 尝试用官方 as_image() 接口取图
            image = None
            try:
                image = part.as_image()
            except Exception:
                pass
            if image is not None:
                out_path = base_output_path.parent / f"{base_output_path.stem}_v{i}.png"
                image.save(str(out_path))
                saved.append(out_path)
                print(f"  → 已生成: {out_path}")
                written = True
                break
            # 兜底：直接读 inline_data.data
            if part.inline_data is not None:
                import base64
                out_path = base_output_path.parent / f"{base_output_path.stem}_v{i}.png"
                image_bytes = part.inline_data.data
                if isinstance(image_bytes, str):
                    image_bytes = base64.b64decode(image_bytes)
                out_path.write_bytes(image_bytes)
                saved.append(out_path)
                print(f"  → 已生成: {out_path}")
                written = True
                break
        if not written:
            print(f"  ⚠ 变体 {i} 未返回图片数据")
    return saved


def generate_with_gemini(
    prompt: str,
    base_output_path: Path,
    api_key: str,
    variants: int,
    model: str = DEFAULT_MODEL,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    aspect_ratio: str | None = None,
    image_size: str | None = None,
) -> list[Path]:
    """调用 Gemini API 生图，自动按模型选择接口。返回已保存的路径列表。"""
    try:
        from google import genai  # type: ignore
        from google.genai import types as genai_types  # type: ignore
    except ImportError:
        print("  错误：未安装 google-genai，请运行: pip install google-genai")
        return []

    client = genai.Client(
        api_key=api_key,
        http_options=genai_types.HttpOptions(timeout=timeout_ms),
    )
    try:
        if _is_imagen_model(model):
            return _generate_via_imagen(client, model, prompt, variants, base_output_path)
        else:
            return _generate_via_gemini(
                client=client,
                model=model,
                prompt=prompt,
                variants=variants,
                base_output_path=base_output_path,
                max_retries=max_retries,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )
    except Exception as exc:
        print(f"  错误：生图失败 — {exc}")
        return []


def main() -> None:
    parser = argparse.ArgumentParser(
        description="为未匹配资产调用 Gemini 生图"
    )
    parser.add_argument("spec", help="spec.yaml 路径")
    parser.add_argument(
        "--variants", type=int, default=2,
        help="每个资产生成的图片变体数量（默认 2）",
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL,
        help=f"生图模型名称（默认 {DEFAULT_MODEL}）",
    )
    parser.add_argument(
        "--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS,
        help=f"Gemini 请求超时（毫秒，默认 {DEFAULT_TIMEOUT_MS}）",
    )
    parser.add_argument(
        "--max-retries", type=int, default=DEFAULT_MAX_RETRIES,
        help=f"请求失败最大重试次数（默认 {DEFAULT_MAX_RETRIES}）",
    )
    parser.add_argument(
        "--aspect-ratio", type=str, default=None,
        help="可选：图片宽高比，如 1:1 / 16:9",
    )
    parser.add_argument(
        "--image-size", type=str, default=None,
        help="可选：图片分辨率档位（Pro 推荐 1K/2K/4K）",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("错误：请设置环境变量 GEMINI_API_KEY")
        print("  Windows PowerShell: $env:GEMINI_API_KEY = 'your-key'")
        sys.exit(1)

    spec_path = Path(args.spec)
    unresolved_path = Path(".superdesigner/tmp") / f"{spec_path.stem}.unresolved.yaml"

    if not unresolved_path.exists():
        print(f"未找到未匹配清单 {unresolved_path}")
        print("请先运行: python scripts/resolve_assets.py <spec.yaml>")
        sys.exit(1)

    with open(unresolved_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    unresolved = data.get("unresolved", [])
    if not unresolved:
        print("没有需要生图的未匹配资产")
        sys.exit(0)

    style = load_style_guide()
    PENDING_DIR.mkdir(parents=True, exist_ok=True)

    IMAGE_TYPES = {"Image", "RenderTexture", "Particle"}
    image_items = [item for item in unresolved if item.get("type") in IMAGE_TYPES]

    if not image_items:
        print("没有需要生图的 Image/RenderTexture/Particle 资产")
        sys.exit(0)

    model = args.model
    iface = "predict(Imagen)" if _is_imagen_model(model) else "generateContent(Gemini)"
    print(
        f"\n=== 为 {len(image_items)} 个图片资产生图 | 模型: {model} [{iface}] "
        f"| {args.variants} 变体/资产 | timeout={args.timeout_ms}ms | retries={args.max_retries} ===\n"
    )

    for item in image_items:
        node_id = item.get("node_id", "unknown")
        prompt = build_prompt(item, style)
        print(f"生成: {node_id}")
        print(f"  Prompt: {prompt[:100]}...")

        base_path = PENDING_DIR / f"{node_id}.png"
        generate_with_gemini(
            prompt=prompt,
            base_output_path=base_path,
            api_key=api_key,
            variants=args.variants,
            model=model,
            timeout_ms=args.timeout_ms,
            max_retries=args.max_retries,
            aspect_ratio=args.aspect_ratio,
            image_size=args.image_size,
        )

    print(f"\n生成完成，图片存入: {PENDING_DIR}")
    print("请运行 /approve-assets 审查并入库")


if __name__ == "__main__":
    main()
