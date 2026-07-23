#!/usr/bin/env python3
"""Convert a fake checkerboard/near-white background image into a transparent PNG."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from PIL import Image


def color_dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return sum((a[i] - b[i]) ** 2 for i in range(3))


def common_border_colors(img: Image.Image, sample_step: int = 8) -> list[tuple[int, int, int]]:
    rgb = img.convert("RGB")
    w, h = rgb.size
    pixels = rgb.load()
    samples = []
    for x in range(0, w, sample_step):
        samples.append(pixels[x, 0])
        samples.append(pixels[x, h - 1])
    for y in range(0, h, sample_step):
        samples.append(pixels[0, y])
        samples.append(pixels[w - 1, y])
    quantized = [tuple((c // 16) * 16 for c in px) for px in samples]
    common = Counter(quantized).most_common(4)
    return [color for color, _ in common]


def should_clear(px: tuple[int, int, int], bg_colors: list[tuple[int, int, int]], tolerance: int) -> bool:
    r, g, b = px
    low_saturation = max(px) - min(px) < 28
    bright = max(px) > 145
    near_bg = any(color_dist(px, bg) <= tolerance * tolerance * 3 for bg in bg_colors)
    return (near_bg and bright) or (low_saturation and max(px) > 218)


def normalize(input_path: Path, output_path: Path, tolerance: int) -> None:
    img = Image.open(input_path).convert("RGBA")
    bg_colors = common_border_colors(img)
    out = Image.new("RGBA", img.size)
    src = img.load()
    dst = out.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = src[x, y]
            if should_clear((r, g, b), bg_colors, tolerance):
                dst[x, y] = (r, g, b, 0)
            else:
                dst[x, y] = (r, g, b, a)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Input image.")
    parser.add_argument("output", help="Output transparent PNG.")
    parser.add_argument("--tolerance", type=int, default=34, help="Background color tolerance.")
    args = parser.parse_args()
    normalize(Path(args.input), Path(args.output), args.tolerance)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
