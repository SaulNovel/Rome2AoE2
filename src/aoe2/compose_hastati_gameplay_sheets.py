"""Compose readable animation and transition validation sheets."""

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pattern", default="*/x2/*.png")
    parser.add_argument("--columns", type=int, default=5)
    parser.add_argument("--cell", type=int, default=260)
    return parser.parse_args()


def main():
    args = arguments()
    paths = sorted(args.input_root.glob(args.pattern))
    if not paths:
        raise SystemExit(f"no images matched {args.input_root / args.pattern}")
    font = ImageFont.load_default(size=16)
    label_height = 30
    rows = math.ceil(len(paths) / args.columns)
    result = Image.new("RGBA", (args.columns * args.cell, rows * (args.cell + label_height)),
                       (38, 43, 40, 255))
    draw = ImageDraw.Draw(result)
    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGBA")
        bounds = image.getchannel("A").getbbox()
        crop = image.crop(bounds) if bounds else image
        crop.thumbnail((args.cell - 16, args.cell - 16), Image.Resampling.NEAREST)
        column, row = index % args.columns, index // args.columns
        x = column * args.cell + (args.cell - crop.width) // 2
        y = row * (args.cell + label_height) + (args.cell - crop.height) // 2
        result.alpha_composite(crop, (x, y))
        label = f"{path.parent.name}: {path.stem.rsplit('-', 1)[-1]}"
        draw.text((column * args.cell + 6, row * (args.cell + label_height) + args.cell + 5),
                  label, fill="white", font=font)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.save(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
