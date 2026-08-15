"""Encode and validate the frozen 67 x 16 Hastati idle as paired SLDX v4 files."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_DEPS = ROOT / "build" / "python-deps" / "sld-authoring"
if LOCAL_DEPS.is_dir():
    sys.path.insert(0, str(LOCAL_DEPS))
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw

from aoe2.analyze_sld import decode_frame
from aoe2.sld import LAYER_MAIN, SLDFile, parse_sld, serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder, author_one_frame

FACETS = 16
FRAMES_PER_FACET = 67
TOTAL_FRAMES = FACETS * FRAMES_PER_FACET


def frame_path(root: Path, direction: int, frame: int) -> Path:
    return root / f"idle-direction-{direction:02d}-frame-{frame:03d}.png"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def alpha_bounds(image: Image.Image) -> tuple[int, int, int, int] | None:
    return image.convert("RGBA").getchannel("A").point(lambda value: 255 if value >= 128 else 0).getbbox()


def checker(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    view = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(view)
    step = max(8, image.width // 20)
    for y in range(0, image.height, step):
        for x in range(0, image.width, step):
            value = 62 if (x // step + y // step) % 2 else 92
            draw.rectangle((x, y, x + step - 1, y + step - 1), fill=(value, value, value, 255))
    view.alpha_composite(image.convert("RGBA"))
    return view.convert("RGB").resize(size, Image.Resampling.NEAREST)


def sheet(items: list[tuple[str, Image.Image]], columns: int, cell: int, output: Path) -> None:
    label = 28
    rows = math.ceil(len(items) / columns)
    result = Image.new("RGB", (columns * cell, rows * (cell + label)), (28, 28, 28))
    draw = ImageDraw.Draw(result)
    for index, (name, image) in enumerate(items):
        column, row = index % columns, index // columns
        x, y = column * cell, row * (cell + label)
        result.paste(checker(image, (cell, cell)), (x, y + label))
        draw.text((x + 8, y + 8), name, fill=(245, 245, 245))
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output)


def audit_sources(root: Path, canvas: int, hotspot: tuple[int, int]) -> dict:
    records = []
    for direction in range(FACETS):
        for frame in range(FRAMES_PER_FACET):
            path = frame_path(root, direction, frame)
            if not path.is_file():
                raise FileNotFoundError(path)
            with Image.open(path) as opened:
                image = opened.convert("RGBA")
            if image.size != (canvas, canvas):
                raise ValueError(f"unexpected canvas {path}: {image.size}")
            bounds = alpha_bounds(image)
            if bounds is None:
                raise ValueError(f"empty alpha: {path}")
            clipped = bounds[0] == 0 or bounds[1] == 0 or bounds[2] == canvas or bounds[3] == canvas
            if clipped:
                raise ValueError(f"alpha touches canvas edge: {path} {bounds}")
            records.append({"direction": direction, "frame": frame, "bounds": list(bounds)})
    return {
        "root": str(root), "canvas": [canvas, canvas], "hotspot": list(hotspot),
        "frame_count": len(records), "empty_alpha": 0, "clipped_frames": 0,
        "minimum_bounds": [min(item["bounds"][0] for item in records), min(item["bounds"][1] for item in records)],
        "maximum_bounds": [max(item["bounds"][2] for item in records), max(item["bounds"][3] for item in records)],
    }


def encode(root: Path, output: Path, canvas: int, hotspot: tuple[int, int], texconv: Path) -> dict:
    frames = []
    for direction in range(FACETS):
        for animation_frame in range(FRAMES_PER_FACET):
            with Image.open(frame_path(root, direction, animation_frame)) as opened:
                main = opened.convert("RGBA")
            frame = author_one_frame(
                main, None, hotspot=hotspot, encoder=DirectXTexBC1Encoder(texconv)
            ).frames[0]
            frame.frame_index = len(frames)
            frames.append(frame)
            if len(frames) % 67 == 0:
                print(json.dumps({"output": output.name, "encoded": len(frames), "total": TOTAL_FRAMES}))
    raw = serialize_sld(SLDFile(frames=frames, facet_count=FACETS))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    parsed = parse_sld(raw)
    if serialize_sld(parsed) != raw:
        raise AssertionError("SLD strict parse/serialize round trip changed bytes")
    if len(parsed.frames) != TOTAL_FRAMES:
        raise AssertionError("SLD frame count mismatch")
    if [frame.frame_index for frame in parsed.frames] != list(range(TOTAL_FRAMES)):
        raise AssertionError("SLD frame-index order mismatch")
    for frame in parsed.frames:
        if (frame.canvas_width, frame.canvas_height) != (canvas, canvas):
            raise AssertionError("SLD canvas mismatch")
        if (frame.center_x, frame.center_y) != hotspot:
            raise AssertionError("SLD hotspot jitter")
        if frame.frame_type != LAYER_MAIN or [layer.layer_type for layer in frame.layers] != [LAYER_MAIN]:
            raise AssertionError("SLD is not main-colour-only")
        if not frame.layers[0].blocks:
            raise AssertionError("SLD contains an empty main frame")
    decoded_samples = []
    for direction in range(FACETS):
        for animation_frame in (0, 33, 66):
            index = direction * FRAMES_PER_FACET + animation_frame
            decoded, shadow = decode_frame(parsed, index)
            if alpha_bounds(decoded) is None or shadow.getbbox() is not None:
                raise AssertionError(f"invalid decoded sample {index}")
            decoded_samples.append(index)
    return {
        "path": str(output), "sha256": digest(output), "bytes": output.stat().st_size,
        "frame_count": len(parsed.frames), "canvas": [canvas, canvas], "hotspot": list(hotspot),
        "linear_order": "facet-major", "frame_indices": [0, TOTAL_FRAMES - 1],
        "main_colour_only": True, "decoded_sample_indices": decoded_samples,
        "strict_round_trip": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames-root", required=True)
    parser.add_argument("--texconv", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--hotspot-x1", nargs=2, type=int, default=(100, 122))
    parser.add_argument("--hotspot-x2", nargs=2, type=int, default=(200, 244))
    args = parser.parse_args()
    source = Path(args.frames_root)
    output = Path(args.output_root)
    output.mkdir(parents=True, exist_ok=True)
    audits = {
        "x1": audit_sources(source / "x1", 200, tuple(args.hotspot_x1)),
        "x2": audit_sources(source / "x2", 400, tuple(args.hotspot_x2)),
    }
    representative = 33
    sheet(
        [(f"direction {direction:02d}, frame {representative:02d}", Image.open(frame_path(source / "x1", direction, representative)).convert("RGBA")) for direction in range(FACETS)],
        4, 400, output / "full-idle-direction-sheet.png",
    )
    sheet(
        [(f"direction 13, frame {frame:02d}", Image.open(frame_path(source / "x1", 13, frame)).convert("RGBA")) for frame in range(FRAMES_PER_FACET)],
        7, 400, output / "full-idle-animation-sheet.png",
    )
    encoded = {
        "x1": encode(source / "x1", output / "hastati-idle_x1.sld", 200, tuple(args.hotspot_x1), Path(args.texconv)),
        "x2": encode(source / "x2", output / "hastati-idle_x2.sld", 400, tuple(args.hotspot_x2), Path(args.texconv)),
    }
    report = {
        "format": "rome2aoe2.hastati-full-idle-sld", "version": 1,
        "animation": "sws_stand", "frames_per_facet": FRAMES_PER_FACET,
        "facet_count": FACETS, "total_frames": TOTAL_FRAMES,
        "frame_duration_seconds": 1 / 24, "fps": 24,
        "frame_order": "facet-major", "main_colour_only": True,
        "shadow": False, "player_colour": False, "outline": False,
        "source_audit": audits, "encoded": encoded,
        "visual_artifacts": ["full-idle-direction-sheet.png", "full-idle-animation-sheet.png"],
    }
    (output / "full-idle-validation-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
