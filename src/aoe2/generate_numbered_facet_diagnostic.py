"""Generate an in-game 0-15 facet diagnostic for AoE direction selection."""

from __future__ import annotations

import argparse
import colorsys
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_DEPS = ROOT / "build" / "python-deps" / "sld-authoring"
if LOCAL_DEPS.is_dir():
    sys.path.insert(0, str(LOCAL_DEPS))
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont

from aoe2.sld import serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder, author_direction_frames


def font(size: int):
    for candidate in ("arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def facet_image(facet: int, size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    scale = size / 200
    hue = facet / 16
    rgb = tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(hue, 0.78, 0.95))
    box = tuple(round(value * scale) for value in (52, 48, 148, 142))
    draw.rounded_rectangle(box, radius=round(12 * scale), fill=(*rgb, 245),
                           outline=(255, 255, 255, 255), width=max(2, round(3 * scale)))
    label = str(facet)
    face = font(round(58 * scale))
    bounds = draw.textbbox((0, 0), label, font=face, stroke_width=max(1, round(2 * scale)))
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    draw.text(((size - width) / 2, round(91 * scale) - height / 2), label, font=face,
              fill=(255, 255, 255, 255), stroke_width=max(1, round(2 * scale)),
              stroke_fill=(0, 0, 0, 255))
    # Ground-origin marker: it must remain at the same hotspot in every facet.
    x, y = size // 2, round(122 * scale)
    draw.line((x - round(18 * scale), y, x + round(18 * scale), y), fill=(0, 0, 0, 255), width=max(2, round(3 * scale)))
    draw.line((x, y - round(6 * scale), x, y + round(6 * scale)), fill=(0, 0, 0, 255), width=max(2, round(3 * scale)))
    return image


def build(size: int, output: Path, texconv: Path) -> None:
    frames = [(facet_image(facet, size), None, None) for facet in range(16)]
    document = author_direction_frames(
        frames, (size // 2, round(122 * size / 200)), 16,
        encoder_factory=lambda: DirectXTexBC1Encoder(texconv),
    )
    output.write_bytes(serialize_sld(document))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--texconv", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    x1 = args.output_root / "hastati-facet-diagnostic_x1.sld"
    x2 = args.output_root / "hastati-facet-diagnostic_x2.sld"
    build(200, x1, args.texconv)
    build(400, x2, args.texconv)
    sheet = Image.new("RGBA", (4 * 200, 4 * 200), (35, 35, 35, 255))
    for facet in range(16):
        sheet.alpha_composite(facet_image(facet, 200), ((facet % 4) * 200, (facet // 4) * 200))
    sheet.convert("RGB").save(args.output_root / "numbered-facet-sheet.png")
    report = {
        "format": "rome2aoe2.numbered-facet-diagnostic", "version": 1,
        "facet_count": 16, "frame_count": 1,
        "purpose": "measure AoE movement direction to selected idle facet index",
        "x1": str(x1), "x2": str(x2),
    }
    (args.output_root / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
