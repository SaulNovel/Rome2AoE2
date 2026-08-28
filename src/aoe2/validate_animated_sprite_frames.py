"""Validate stable animated sprite canvases and emit compact visual diagnostics."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "third_party" / "python-deps"))
sys.path.insert(0, str(ROOT / "build" / "python-deps" / "pillow"))
from PIL import Image, ImageChops, ImageDraw


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--frames-dir", type=Path)
    return parser.parse_args()


def sheet(records, destination, columns=10, scale=2):
    cell_w, cell_h = 200 * scale, 220 * scale
    rows = (len(records) + columns - 1) // columns
    out = Image.new("RGBA", (columns * cell_w, rows * cell_h), (45, 45, 45, 255))
    draw = ImageDraw.Draw(out)
    for index, record in enumerate(records):
        image = Image.open(record["absolute_path"]).convert("RGBA").resize((200 * scale, 200 * scale))
        x, y = index % columns * cell_w, index // columns * cell_h
        out.alpha_composite(image, (x, y + 20 * scale))
        draw.text((x + 4, y + 2), f"d{record['direction']:02d} f{record['output_frame']:03d}", fill="white")
    out.save(destination)


def main():
    args = arguments()
    data = json.loads(args.report.read_text(encoding="utf-8"))
    base = args.report.parent
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = data["records"]
    frames_dir = args.frames_dir or (base / "one-direction")
    for record in records:
        record["absolute_path"] = str((frames_dir / record["path"]).resolve())
    by_direction = {}
    for record in records:
        by_direction.setdefault(record["direction"], []).append(record)
    checks = []
    for direction, frames in sorted(by_direction.items()):
        frames.sort(key=lambda item: item["output_frame"])
        if [item["output_frame"] for item in frames] != list(range(len(frames))):
            raise RuntimeError(f"non-contiguous frame order in direction {direction}")
        images = [Image.open(item["absolute_path"]).convert("RGBA") for item in frames]
        sizes = {image.size for image in images}
        if sizes != {tuple(data["canvas"])}:
            raise RuntimeError(f"canvas drift in direction {direction}: {sizes}")
        nonempty = all(image.getchannel("A").getbbox() is not None for image in images)
        adjacent = [sum(ImageChops.difference(images[i], images[i + 1]).getchannel("A").histogram()[1:])
                    for i in range(len(images) - 1)]
        loop = ImageChops.difference(images[0], images[-1]).getbbox()
        checks.append({"direction": direction, "frames": len(frames), "nonempty": nonempty,
                       "bounds_union": [min(item["bounds"][0] for item in frames),
                                        min(item["bounds"][1] for item in frames),
                                        max(item["bounds"][2] for item in frames),
                                        max(item["bounds"][3] for item in frames)],
                       "adjacent_alpha_change_range": [min(adjacent), max(adjacent)],
                       "first_last_pixel_difference_bbox": loop})
        sheet(frames, args.output_dir / f"idle-direction-{direction}-contact-sheet.png")
    preview_records = []
    for direction, frames in sorted(by_direction.items()):
        frames.sort(key=lambda item: item["output_frame"])
        for index in (0, len(frames) // 2, len(frames) - 1):
            preview_records.append(frames[index])
    sheet(preview_records, args.output_dir / "idle-all-directions-preview.png", columns=8, scale=2)
    (args.output_dir / "validation.json").write_text(
        json.dumps({"format": "rome2aoe2.animated-sprite-validation", "version": 1,
                    "canvas": data["canvas"], "hotspot": data["hotspot"], "checks": checks},
                   indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
