"""Validate fixed-camera/unit-yaw facets against accepted orbit geometry."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_DEPS = ROOT / "build" / "python-deps" / "sld-authoring"
if LOCAL_DEPS.is_dir():
    sys.path.insert(0, str(LOCAL_DEPS))
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw
from aoe2.facet_mapping import legacy_source_facet, soldier_yaw_degrees

ACCEPTED_AZIMUTHS = [45.0, 22.5, 0.0, 337.5, 315.0, 292.5, 270.0, 247.5,
                     225.0, 202.5, 180.0, 157.5, 135.0, 112.5, 90.0, 67.5]
REFERENCE_AZIMUTH = 112.5


def path(root: Path, direction: int, ordinal: int) -> Path:
    return root / f"idle-direction-{direction:02d}-frame-{ordinal:03d}.png"


def mask(image: Image.Image) -> list[bool]:
    return [alpha >= 128 for alpha in image.convert("RGBA").getchannel("A").get_flattened_data()]


def centroid(bits: list[bool], width: int) -> list[float]:
    points = [(index % width, index // width) for index, value in enumerate(bits) if value]
    return [sum(x for x, _ in points) / len(points), sum(y for _, y in points) / len(points)]


def median_luminance(image: Image.Image) -> float:
    values = []
    for red, green, blue, alpha in image.convert("RGBA").get_flattened_data():
        if alpha >= 128:
            values.append((0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0)
    return statistics.median(values)


def checker(image: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(canvas)
    step = 10
    for y in range(0, image.height, step):
        for x in range(0, image.width, step):
            value = 62 if (x // step + y // step) % 2 else 92
            draw.rectangle((x, y, x + step - 1, y + step - 1), fill=(value, value, value, 255))
    canvas.alpha_composite(image.convert("RGBA"))
    return canvas.convert("RGB").resize((size, size), Image.Resampling.NEAREST)


def labeled_sheet(items, columns: int, cell: int, output: Path) -> None:
    label = 32
    rows = (len(items) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell, rows * (cell + label)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    for index, (caption, image) in enumerate(items):
        column, row = index % columns, index // columns
        x, y = column * cell, row * (cell + label)
        draw.text((x + 8, y + 8), caption, fill=(245, 245, 245))
        sheet.paste(checker(image, cell), (x, y + label))
    sheet.save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--accepted-root", type=Path, required=True)
    parser.add_argument("--fixed-root", type=Path, required=True)
    parser.add_argument("--accepted-frame", type=int, default=33)
    parser.add_argument("--fixed-frame", type=int, default=0)
    parser.add_argument("--render-report", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    accepted = [Image.open(path(args.accepted_root, i, args.accepted_frame)).convert("RGBA") for i in range(16)]
    fixed = [Image.open(path(args.fixed_root, i, args.fixed_frame)).convert("RGBA") for i in range(16)]
    comparisons = []
    for direction, after in enumerate(fixed):
        source_facet = legacy_source_facet(direction)
        before = accepted[source_facet]
        old, new = mask(before), mask(after)
        old_count, new_count = sum(old), sum(new)
        old_center, new_center = centroid(old, before.width), centroid(new, after.width)
        comparisons.append({
            "facet": direction,
            "accepted_source_facet": source_facet,
            "accepted_camera_azimuth_degrees": ACCEPTED_AZIMUTHS[source_facet],
            "unit_yaw_degrees": soldier_yaw_degrees(direction),
            "silhouette_xor_pixels": sum(a != b for a, b in zip(old, new)),
            "silhouette_union_pixels": sum(a or b for a, b in zip(old, new)),
            "coverage_delta_pixels": new_count - old_count,
            "centroid_delta_pixels": [new_center[0] - old_center[0], new_center[1] - old_center[1]],
            "fixed_median_luminance": median_luminance(after),
        })
    labeled_sheet(
        [(f"facet {i:02d} / yaw {comparisons[i]['unit_yaw_degrees']:g} deg", fixed[i]) for i in range(16)],
        4, 400, args.output_root / "fixed-studio-direction-sheet.png",
    )
    pairs = ((0, 8), (2, 10), (4, 12), (6, 14))
    labeled_sheet(
        [(f"facet {facet:02d} / yaw {comparisons[facet]['unit_yaw_degrees']:g} deg", fixed[facet])
         for pair in pairs for facet in pair],
        2, 500, args.output_root / "opposite-facets-comparison.png",
    )
    render = json.loads(args.render_report.read_text(encoding="utf-8"))
    mapping = {
        "format": "rome2aoe2.facet-yaw-map", "version": 1,
        "policy": "fixed camera/light/environment/ground; rotate complete unit root only",
        "formula": "yaw(i) = (292.5 - 22.5*i) mod 360",
        "runtime_order": ["E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW",
                          "W", "WNW", "NW", "NNW", "N", "NNE", "NE", "ENE"],
        "fixed_camera": render["camera"], "fixed_lighting": render["lighting"],
        "unit_root": render["unit_root"],
        "facets": [{"facet": row["facet"], "unit_yaw_degrees": row["unit_yaw_degrees"]}
                   for row in comparisons],
    }
    (args.output_root / "facet-yaw-map.json").write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = {
        "format": "rome2aoe2.fixed-studio-direction-validation", "version": 1,
        "comparisons": comparisons,
        "maximum_silhouette_xor_pixels": max(row["silhouette_xor_pixels"] for row in comparisons),
        "maximum_centroid_delta_pixels": max(max(abs(v) for v in row["centroid_delta_pixels"]) for row in comparisons),
        "fixed_luminance_darkest_to_brightest_ratio": min(row["fixed_median_luminance"] for row in comparisons) / max(row["fixed_median_luminance"] for row in comparisons),
        "artifacts": ["fixed-studio-direction-sheet.png", "opposite-facets-comparison.png", "facet-yaw-map.json"],
    }
    (args.output_root / "fixed-studio-validation-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
