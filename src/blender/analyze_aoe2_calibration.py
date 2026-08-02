"""Build deterministic numeric and contact-sheet reports from calibration PNGs."""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contact-sheet", type=Path, required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def percentile(values, fraction):
    values = sorted(values)
    return values[min(len(values) - 1, round((len(values) - 1) * fraction))]


def metrics(path):
    image = bpy.data.images.load(str(path.resolve()), check_existing=False)
    width, height = image.size
    pixels = list(image.pixels)
    luminance = []
    edge_pixels = 0
    opaque_pixels = 0
    alpha_values = []
    points = []
    for index in range(width * height):
        red, green, blue, alpha = pixels[index * 4:index * 4 + 4]
        if alpha > 1.0 / 255.0:
            points.append((index % width, height - 1 - index // width))
            alpha_values.append(alpha)
        if 1.0 / 255.0 < alpha < 254.0 / 255.0:
            edge_pixels += 1
        if alpha >= 0.1:
            opaque_pixels += 1
            luminance.append(0.2126 * red + 0.7152 * green + 0.0722 * blue)
    xs, ys = zip(*points) if points else ([], [])
    result = {
        "alpha_edge_pixels": edge_pixels,
        "alpha_mean_nonzero": sum(alpha_values) / len(alpha_values),
        "alpha_max": max(alpha_values),
        "bounds": None if not points else [min(xs), min(ys), max(xs) + 1, max(ys) + 1],
        "height": height,
        "luminance_mean": sum(luminance) / len(luminance),
        "luminance_p10": percentile(luminance, 0.1),
        "luminance_p90": percentile(luminance, 0.9),
        "opaque_pixels": opaque_pixels,
        "width": width,
    }
    return image, pixels, result


def main():
    args = arguments()
    records = []
    loaded = []
    for path in args.input:
        image, pixels, result = metrics(path)
        loaded.append((image, pixels))
        result["candidate"] = path.parent.name
        result["image"] = path.name
        records.append(result)
    tile_width, tile_height = loaded[0][0].size
    columns = min(4, len(loaded))
    rows = math.ceil(len(loaded) / columns)
    sheet = bpy.data.images.new("AoE2CalibrationContactSheet", tile_width * columns,
                                tile_height * rows, alpha=True)
    output = [0.0] * (tile_width * columns * tile_height * rows * 4)
    for tile, (_, pixels) in enumerate(loaded):
        tile_x, tile_y = tile % columns, rows - 1 - tile // columns
        for y in range(tile_height):
            source = y * tile_width * 4
            destination = ((tile_y * tile_height + y) * tile_width * columns + tile_x * tile_width) * 4
            output[destination:destination + tile_width * 4] = pixels[source:source + tile_width * 4]
    sheet.pixels.foreach_set(output)
    sheet.file_format = "PNG"
    args.contact_sheet.parent.mkdir(parents=True, exist_ok=True)
    sheet.filepath_raw = str(args.contact_sheet.resolve())
    sheet.save()
    document = {"format": "rome2aoe2.render-comparison", "version": 1,
                "candidates": records, "contact_sheet": args.contact_sheet.name}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()
