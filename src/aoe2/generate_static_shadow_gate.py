"""Author and visualize the 16-facet fixed-studio Hastati shadow gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_DEPS = ROOT / "build" / "python-deps" / "sld-authoring"
if LOCAL_DEPS.is_dir():
    sys.path.insert(0, str(LOCAL_DEPS))
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw, ImageStat

from aoe2.analyze_sld import decode_frame
from aoe2.sld import LAYER_MAIN, LAYER_SHADOW, parse_sld, serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder, author_direction_frames


def source(root: Path, facet: int) -> Path:
    return root / f"idle-direction-{facet:02d}-frame-000.png"


def black_shadow(alpha: Image.Image) -> Image.Image:
    result = Image.new("RGBA", alpha.size, (0, 0, 0, 0))
    result.putalpha(alpha.convert("L"))
    return result


def checker(image: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(canvas)
    step = max(5, image.width // 20)
    for y in range(0, image.height, step):
        for x in range(0, image.width, step):
            value = 62 if (x // step + y // step) % 2 else 92
            draw.rectangle((x, y, x + step - 1, y + step - 1), fill=(value, value, value, 255))
    canvas.alpha_composite(image.convert("RGBA"))
    return canvas.convert("RGB").resize((size, size), Image.Resampling.NEAREST)


def sheet(items, columns: int, cell: int, output: Path) -> None:
    label = 32
    rows = (len(items) + columns - 1) // columns
    result = Image.new("RGB", (columns * cell, rows * (cell + label)), (24, 24, 24))
    draw = ImageDraw.Draw(result)
    for index, (caption, image) in enumerate(items):
        column, row = index % columns, index // columns
        x, y = column * cell, row * (cell + label)
        draw.text((x + 8, y + 8), caption, fill=(245, 245, 245))
        result.paste(checker(image, cell), (x, y + label))
    result.save(output)


def build(zoom: str, main_root: Path, shadow_root: Path, output: Path,
          hotspot: tuple[int, int], texconv: Path) -> tuple[dict, list]:
    inputs = []
    source_shadows = []
    for facet in range(16):
        main = Image.open(source(main_root, facet)).convert("RGBA")
        shadow = Image.open(source(shadow_root, facet)).convert("RGBA")
        inputs.append((main, shadow, None))
        source_shadows.append(shadow.getchannel("A"))
    document = author_direction_frames(
        inputs, hotspot, 16,
        encoder_factory=lambda: DirectXTexBC1Encoder(texconv),
    )
    raw = serialize_sld(document)
    output.write_bytes(raw)
    parsed = parse_sld(raw)
    if serialize_sld(parsed) != raw or len(parsed.frames) != 16:
        raise AssertionError("shadow proof SLD failed strict frame/round-trip validation")
    decoded = []
    errors = []
    for facet, frame in enumerate(parsed.frames):
        if frame.frame_type != LAYER_MAIN | LAYER_SHADOW:
            raise AssertionError("shadow proof frame does not contain exactly main + shadow")
        if [layer.layer_type for layer in frame.layers] != [LAYER_MAIN, LAYER_SHADOW]:
            raise AssertionError("shadow proof layer order is invalid")
        main, shadow = decode_frame(parsed, facet)
        decoded.append((main, shadow))
        difference = Image.new("L", shadow.size)
        difference.putdata([abs(a - b) for a, b in zip(source_shadows[facet].get_flattened_data(), shadow.get_flattened_data())])
        stats = ImageStat.Stat(difference)
        errors.append({"facet": facet, "mean_absolute_error": stats.mean[0],
                       "maximum_absolute_error": difference.getextrema()[1]})
    return ({
        "zoom": zoom, "path": str(output), "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(), "frames": 16,
        "hotspot": list(hotspot), "layer_mask": LAYER_MAIN | LAYER_SHADOW,
        "layers": ["main", "shadow"], "shadow_decode_errors": errors,
    }, decoded)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-root", type=Path, required=True)
    parser.add_argument("--shadow-root", type=Path, required=True)
    parser.add_argument("--texconv", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    records = {}
    decoded = {}
    for zoom, hotspot in (("x1", (100, 122)), ("x2", (200, 244))):
        records[zoom], decoded[zoom] = build(
            zoom, args.main_root / zoom, args.shadow_root / zoom,
            args.output_root / f"hastati-shadow-proof_{zoom}.sld",
            hotspot, args.texconv,
        )
    x1 = decoded["x1"]
    shadow_views = [(f"facet {facet:02d} shadow", black_shadow(x1[facet][1])) for facet in range(16)]
    sheet(shadow_views, 4, 400, args.output_root / "shadow-only-direction-sheet.png")
    combined = []
    triptych = []
    for facet, (main, shadow) in enumerate(x1):
        shadow_rgba = black_shadow(shadow)
        preview = Image.new("RGBA", main.size)
        preview.alpha_composite(shadow_rgba)
        preview.alpha_composite(main)
        combined.append((f"facet {facet:02d} combined", preview))
        triptych.extend(((f"facet {facet:02d} main", main),
                         (f"facet {facet:02d} shadow", shadow_rgba),
                         (f"facet {facet:02d} combined", preview)))
    sheet(combined, 4, 400, args.output_root / "combined-shadow-direction-sheet.png")
    sheet(triptych, 3, 320, args.output_root / "main-shadow-combined-validation-sheet.png")
    render_report = json.loads((args.shadow_root / "shadow-render-report.json").read_text(encoding="utf-8"))
    report = {
        "format": "rome2aoe2.static-shadow-sld-gate", "version": 1,
        "main_colour_modified": False, "separate_sld_shadow_layer": True,
        "facet_count": 16, "frame_count_per_facet": 1,
        "hotspots": {"x1": [100, 122], "x2": [200, 244]},
        "hotspot_impact": "none", "clipping": False,
        "shadow_generation": render_report["shadow"], "encoded": records,
        "runtime_status": "not packaged or tested; awaiting visual approval",
        "artifacts": ["shadow-only-direction-sheet.png", "combined-shadow-direction-sheet.png",
                      "main-shadow-combined-validation-sheet.png"],
    }
    (args.output_root / "shadow-proof-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
