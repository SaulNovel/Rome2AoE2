"""Compose readable final-idle review sheets from production render reports."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


def checker(size):
    image = Image.new("RGBA", size, (42, 42, 42, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], 16):
        for x in range(0, size[0], 16):
            if (x // 16 + y // 16) % 2:
                draw.rectangle((x, y, x + 15, y + 15), fill=(54, 54, 54, 255))
    return image


def crop_for_review(path, bounds, output_size=(300, 340)):
    image = Image.open(path).convert("RGBA")
    x1, y1, x2, y2 = bounds
    pad = max(8, int(max(x2 - x1, y2 - y1) * .12))
    box = (max(0, x1 - pad), max(0, y1 - pad), min(image.width, x2 + pad), min(image.height, y2 + pad))
    crop = image.crop(box)
    scale = min(output_size[0] / crop.width, output_size[1] / crop.height)
    crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.Resampling.NEAREST)
    out = checker(output_size)
    out.alpha_composite(crop, ((output_size[0] - crop.width) // 2, (output_size[1] - crop.height) // 2))
    return out


def direction_sheet(report, destination):
    records = report["records"]
    if len(records) > 8:
        records = [record for record in records
                   if record["direction"] in range(0, 16, 2) and record["output_frame"] == 33]
    cell_w, cell_h = 320, 380
    out = Image.new("RGBA", (4 * cell_w, 2 * cell_h), (26, 26, 26, 255))
    draw = ImageDraw.Draw(out)
    for index, record in enumerate(records):
        tile = crop_for_review(record["x2"], record["x2_bounds"])
        x, y = index % 4 * cell_w, index // 4 * cell_h
        out.alpha_composite(tile, (x + 10, y + 28))
        draw.text((x + 12, y + 7), f"facet {record['direction']:02d} / {record['azimuth_degrees']:.1f} deg", fill="white")
    out.save(destination)


def animation_sheet(report, destination):
    records = report["records"]
    direction = report["directions"][0]
    frames = [r for r in records if r["direction"] == direction]
    selected = [frames[round(i * (len(frames) - 1) / 11)] for i in range(12)]
    cell_w, cell_h = 260, 330
    out = Image.new("RGBA", (6 * cell_w, 2 * cell_h), (26, 26, 26, 255))
    draw = ImageDraw.Draw(out)
    for index, record in enumerate(selected):
        tile = crop_for_review(record["x2"], record["x2_bounds"], (240, 290))
        x, y = index % 6 * cell_w, index // 6 * cell_h
        out.alpha_composite(tile, (x + 10, y + 28))
        draw.text((x + 12, y + 7), f"frame {record['output_frame']:03d}", fill="white")
    out.save(destination)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--direction-report", type=Path, required=True)
    parser.add_argument("--full-report", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    direction = json.loads(args.direction_report.read_text(encoding="utf-8"))
    direction_sheet(direction, args.output_dir / "final-idle-direction-sheet.png")
    if args.full_report:
        full = json.loads(args.full_report.read_text(encoding="utf-8"))
        animation_sheet(full, args.output_dir / "final-idle-animation-sheet.png")
        representative = next(r for r in full["records"] if r["direction"] == 13 and r["output_frame"] == 33)
        Image.open(representative["x1"]).save(args.output_dir / "final-x1-preview.png")
        Image.open(representative["x2"]).save(args.output_dir / "final-x2-uhd-preview.png")


if __name__ == "__main__":
    main()
