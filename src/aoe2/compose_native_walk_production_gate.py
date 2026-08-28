"""Compose the fixed 3x8 native walk production gate without recropping cells."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "build/python-deps/pillow"))

from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = (
        ("row-A-native-body", "A  Asset Editor-native / raw body"),
        ("row-B-centered-body", "B  Production body / outer centered"),
        ("row-C-complete-production", "C  Complete production / outer centered"),
    )
    images = [[Image.open(path).convert("RGBA") for path in sorted((args.input_root / folder).glob("*.png"))]
              for folder, _label in rows]
    if any(len(row) != 8 for row in images):
        raise SystemExit(f"expected exactly eight images per row, got {[len(row) for row in images]}")
    cell_w, cell_h = images[0][0].size
    left, top, phase_h = 290, 58, 26
    sheet = Image.new("RGBA", (left + 8 * cell_w, top + 3 * (cell_h + phase_h)), (22, 25, 24, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)
    title = ImageFont.load_default(size=22)
    draw.text((12, 14), "sws_walk_162_cm — native Action production gate", fill="white", font=title)
    for column in range(8):
        draw.text((left + column * cell_w + 8, top - 25), f"{column * 12.5:g}%", fill=(220, 220, 220), font=font)
    for row_index, ((_folder, label), row_images) in enumerate(zip(rows, images)):
        y = top + row_index * (cell_h + phase_h)
        draw.multiline_text((12, y + cell_h // 2 - 22), label.replace(" / ", "\n"), fill="white", font=font, spacing=5)
        for column, image in enumerate(row_images):
            sheet.alpha_composite(image, (left + column * cell_w, y))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
