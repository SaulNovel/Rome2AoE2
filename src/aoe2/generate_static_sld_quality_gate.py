"""Build the frozen one-frame, main-colour-only SLD transport quality gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_DEPS = ROOT / "build" / "python-deps" / "sld-authoring"
if LOCAL_DEPS.is_dir():
    sys.path.insert(0, str(LOCAL_DEPS))
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw

from aoe2.analyze_sld import decode_frame
from aoe2.sld import LAYER_MAIN, parse_sld, serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder, author_one_frame


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(source: Image.Image, decoded: Image.Image) -> dict:
    source = source.convert("RGBA")
    decoded = decoded.convert("RGBA")
    if source.size != decoded.size:
        raise ValueError("source and decoded canvases differ")
    rgb_squared = 0
    rgb_absolute = 0
    rgb_max = 0
    rgb_samples = 0
    silhouette_errors = 0
    alpha_exact = 0
    pixel_count = source.width * source.height
    for expected, actual in zip(source.get_flattened_data(), decoded.get_flattened_data()):
        expected_visible = expected[3] >= 128
        actual_visible = actual[3] >= 128
        silhouette_errors += expected_visible != actual_visible
        alpha_exact += (255 if expected_visible else 0) == actual[3]
        if expected_visible and actual_visible:
            for channel in range(3):
                error = abs(expected[channel] - actual[channel])
                rgb_squared += error * error
                rgb_absolute += error
                rgb_max = max(rgb_max, error)
                rgb_samples += 1
    mse = rgb_squared / rgb_samples if rgb_samples else 0.0
    psnr = float("inf") if mse == 0 else 10.0 * math.log10(255.0 * 255.0 / mse)
    return {
        "opaque_rgb_psnr_db": psnr,
        "opaque_rgb_mean_absolute_error": rgb_absolute / rgb_samples if rgb_samples else 0.0,
        "opaque_rgb_max_absolute_error": rgb_max,
        "silhouette_error_pixels": silhouette_errors,
        "alpha_binary_equality_pixels": alpha_exact,
        "alpha_binary_equality_fraction": alpha_exact / pixel_count,
        "canvas_pixels": pixel_count,
    }


def checker(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size)
    draw = ImageDraw.Draw(background)
    step = max(8, rgba.width // 25)
    for y in range(0, rgba.height, step):
        for x in range(0, rgba.width, step):
            value = 62 if (x // step + y // step) % 2 else 92
            draw.rectangle((x, y, x + step - 1, y + step - 1), fill=(value, value, value, 255))
    background.alpha_composite(rgba)
    return background.convert("RGB")


def contact_sheet(items: list[tuple[str, Image.Image]], output: Path) -> None:
    display_size = (600, 600)
    label_height = 44
    sheet = Image.new("RGB", (display_size[0] * len(items), display_size[1] + label_height), (28, 28, 28))
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(items):
        view = checker(image).resize(display_size, Image.Resampling.NEAREST)
        x = index * display_size[0]
        sheet.paste(view, (x, label_height))
        draw.text((x + 12, 14), label, fill=(245, 245, 245))
    sheet.save(output)


def build_one(source_path: Path, source_copy: Path, output: Path, decoded_path: Path,
              hotspot: tuple[int, int], texconv: Path) -> dict:
    source_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, source_copy)
    source = Image.open(source_copy).convert("RGBA")
    document = author_one_frame(source, None, hotspot=hotspot, encoder=DirectXTexBC1Encoder(texconv))
    raw = serialize_sld(document)
    output.write_bytes(raw)
    parsed = parse_sld(raw)
    if serialize_sld(parsed) != raw:
        raise AssertionError("SLD did not round-trip byte-for-byte")
    frame = parsed.frames[0]
    if frame.frame_type != LAYER_MAIN or len(frame.layers) != 1 or frame.layers[0].layer_type != LAYER_MAIN:
        raise AssertionError("quality gate SLD contains a non-main layer")
    decoded, shadow = decode_frame(parsed)
    if shadow.getbbox() is not None:
        raise AssertionError("main-only SLD decoded a non-empty shadow")
    decoded.save(decoded_path)
    return {
        "source_original": str(source_path),
        "source_copy": source_copy.name,
        "source_original_sha256": sha256(source_path),
        "source_copy_sha256": sha256(source_copy),
        "sld": output.name,
        "sld_sha256": sha256(output),
        "decoded": decoded_path.name,
        "canvas": list(source.size),
        "hotspot": list(hotspot),
        "frame_count": len(parsed.frames),
        "layer_mask": frame.frame_type,
        "layers": [layer.layer_type for layer in frame.layers],
        "metrics": compare(source, decoded),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-x1", required=True)
    parser.add_argument("--source-x2", required=True)
    parser.add_argument("--texconv", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    records = {
        "x1": build_one(Path(args.source_x1), root / "source-x1.png", root / "hastati-test_x1.sld",
                        root / "decoded-x1.png", (100, 174), Path(args.texconv)),
        "x2": build_one(Path(args.source_x2), root / "source-x2.png", root / "hastati-test_x2.sld",
                        root / "decoded-x2.png", (200, 349), Path(args.texconv)),
    }
    contact_sheet([
        ("accepted source x1 (2x view)", Image.open(root / "source-x1.png")),
        ("decoded SLD x1 (2x view)", Image.open(root / "decoded-x1.png")),
        ("accepted source x2", Image.open(root / "source-x2.png")),
        ("decoded SLD x2", Image.open(root / "decoded-x2.png")),
    ], root / "source-vs-decoded-contact-sheet.png")
    objective_pass = all(
        record["metrics"]["silhouette_error_pixels"] == 0
        and record["metrics"]["opaque_rgb_psnr_db"] >= 28.0
        and record["metrics"]["opaque_rgb_mean_absolute_error"] <= 8.0
        for record in records.values()
    )
    report = {
        "format": "rome2aoe2.static-sld-main-colour-gate",
        "version": 1,
        "source_frozen": True,
        "main_colour_only": True,
        "shadow_layer": False,
        "player_colour_layer": False,
        "outline_layer": False,
        "encoder": "DirectXTex BC1_UNORM",
        "objective_gate": {
            "minimum_opaque_rgb_psnr_db": 28.0,
            "maximum_opaque_rgb_mean_absolute_error": 8.0,
            "required_silhouette_error_pixels": 0,
            "passed": objective_pass,
        },
        "visual_gate": "requires inspection of source-vs-decoded-contact-sheet.png",
        "aoe_test_authorized": False,
        "records": records,
    }
    (root / "quality-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if objective_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
