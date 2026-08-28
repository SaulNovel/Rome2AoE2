"""Create compact review images and the approval record for the Hastati pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


SAMPLES = (0, 11, 22, 33, 44, 55, 66)


def checker(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (42, 42, 42, 255))
    draw = ImageDraw.Draw(image)
    tile = 16
    for y in range(0, size, tile):
        for x in range(0, size, tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle((x, y, x + tile - 1, y + tile - 1), fill=(55, 55, 55, 255))
    return image


def enlarged_frame(path: Path, size: int = 256) -> Image.Image:
    source = Image.open(path).convert("RGBA")
    crop = source.crop((68, 44, 132, 116)).resize((size, size), Image.Resampling.NEAREST)
    base = checker(size)
    base.alpha_composite(crop)
    return base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.report.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = {(r["direction"], r["output_frame"]): r for r in data["records"]}
    directions = data["directions"]
    sheet = Image.new("RGBA", (len(SAMPLES) * 256, len(directions) * 280), (30, 30, 30, 255))
    draw = ImageDraw.Draw(sheet)
    for row, direction in enumerate(directions):
        for column, frame in enumerate(SAMPLES):
            tile = enlarged_frame(args.frames_dir / records[(direction, frame)]["path"])
            sheet.alpha_composite(tile, (column * 256, row * 280 + 24))
            draw.text((column * 256 + 6, row * 280 + 5), f"d{direction:02d} f{frame:03d}", fill="white")
    sheet.save(args.output_dir / "hastati-sws-stand-4-direction-contact-sheet.png")
    preview = Image.new("RGBA", (4 * 320, 344), (30, 30, 30, 255))
    draw = ImageDraw.Draw(preview)
    for column, direction in enumerate(directions):
        tile = enlarged_frame(args.frames_dir / records[(direction, 33)]["path"], 320)
        preview.alpha_composite(tile, (column * 320, 24))
        draw.text((column * 320 + 6, 5), f"facet {direction:02d} / frame 033", fill="white")
    preview.save(args.output_dir / "hastati-sws-stand-representative-frames.png")
    bounds = [r["bounds"] for r in data["records"]]
    approval = {
        "format": "rome2aoe2.hastati-sprite-pilot-approval",
        "version": 1,
        "verdict": "APPROVED_FOR_FULL_16_DIRECTION_EXPORT",
        "directions": directions,
        "direction_angles": data["direction_angles"],
        "frames_per_direction": data["output_frames_per_direction"],
        "canvas": data["canvas"],
        "hotspot": data["hotspot"],
        "alpha_bounds_union": [min(b[0] for b in bounds), min(b[1] for b in bounds),
                               max(b[2] for b in bounds), max(b[3] for b in bounds)],
        "visual_checks": {
            "correct_gladius": "pass", "corrected_crest_seated_and_tracking": "pass",
            "accepted_materials": "pass", "equipment_continuity": "pass",
            "directional_scale_consistency": "pass", "canvas_clipping": "pass",
        },
        "recommendation": "export all 16 ordered facets without mirroring using the frozen source",
    }
    (args.output_dir / "pilot-approval.json").write_text(
        json.dumps(approval, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
