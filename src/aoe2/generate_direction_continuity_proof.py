"""Compare AoE's canonical Militia facets with a candidate standing SLD."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_DEPS = ROOT / "build" / "python-deps" / "sld-authoring"
if LOCAL_DEPS.is_dir():
    sys.path.insert(0, str(LOCAL_DEPS))
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw

from aoe2.analyze_sld import decode_frame
from aoe2.sld import parse_sld


def checker(image: Image.Image, size: int = 200) -> Image.Image:
    canvas = Image.new("RGBA", image.size, (72, 72, 72, 255))
    draw = ImageDraw.Draw(canvas)
    step = 10
    for y in range(0, image.height, step):
        for x in range(0, image.width, step):
            value = 58 if (x // step + y // step) % 2 else 86
            draw.rectangle((x, y, x + step - 1, y + step - 1), fill=(value, value, value, 255))
    canvas.alpha_composite(image.convert("RGBA"))
    canvas.thumbnail((size, size), Image.Resampling.NEAREST)
    result = Image.new("RGB", (size, size), (30, 30, 30))
    result.paste(canvas.convert("RGB"), ((size - canvas.width) // 2, (size - canvas.height) // 2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--militia-idle", type=Path, required=True)
    parser.add_argument("--militia-walk", type=Path, required=True)
    parser.add_argument("--candidate-idle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--militia-frames", type=int, default=30)
    args = parser.parse_args()
    idle = parse_sld(args.militia_idle.read_bytes())
    walk = parse_sld(args.militia_walk.read_bytes())
    candidate = parse_sld(args.candidate_idle.read_bytes())
    cell, label = 200, 28
    sheet = Image.new("RGB", (3 * cell, 16 * (cell + label)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    headings = ("Militia idle", "Militia walk", "Hastati idle")
    for facet in range(16):
        sources = (
            decode_frame(idle, facet * args.militia_frames)[0],
            decode_frame(walk, facet * args.militia_frames)[0],
            decode_frame(candidate, facet)[0],
        )
        y = facet * (cell + label)
        for column, (heading, image) in enumerate(zip(headings, sources)):
            x = column * cell
            draw.text((x + 6, y + 6), f"facet {facet:02d} | {heading}", fill=(245, 245, 245))
            sheet.paste(checker(image, cell), (x, y + label))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
