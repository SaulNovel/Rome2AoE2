from __future__ import annotations

import colorsys
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "build" / "python-deps" / "pillow"))
from PIL import Image, ImageDraw, ImageFont

BASE = ROOT / "build/local-integration/rome2/hastati-ca-structured-ab"
MASTERS = BASE / "masters"
MASKS = BASE / "masks"
RUNTIME = Path(r"C:\Program Files (x86)\Steam\userdata\128135655\760\remote\214950\screenshots\20260809202533_1.jpg")
OUT = BASE / "analysis"


def percentile(values: list[float], p: float) -> float:
    values = sorted(values)
    x = (len(values) - 1) * p
    lo, hi = math.floor(x), math.ceil(x)
    return values[lo] if lo == hi else values[lo] * (hi - x) + values[hi] * (x - lo)


def semantic_metrics(image: Image.Image, mask: Image.Image) -> dict:
    rgb = image.convert("RGB")
    rgba = image.convert("RGBA")
    m = mask.convert("RGB")
    lum, sat, hues, hue_weights = [], [], [], []
    for colour, alpha, flag in zip(rgb.getdata(), rgba.getdata(), m.getdata()):
        if alpha[3] < 128 or max(flag) < 128:
            continue
        r, g, b = (x / 255.0 for x in colour)
        lum.append(.2126 * r + .7152 * g + .0722 * b)
        h, s, _ = colorsys.rgb_to_hsv(r, g, b)
        sat.append(s)
        hues.append(h * 2 * math.pi)
        hue_weights.append(max(s, .001))
    sx = sum(math.cos(h) * w for h, w in zip(hues, hue_weights))
    sy = sum(math.sin(h) * w for h, w in zip(hues, hue_weights))
    hue = math.degrees(math.atan2(sy, sx)) % 360
    return {
        "pixels": len(lum),
        "L10": percentile(lum, .10), "L50": percentile(lum, .50),
        "L90": percentile(lum, .90), "L95": percentile(lum, .95),
        "mean_hsv_saturation": sum(sat) / len(sat),
        "saturation_weighted_circular_hue_degrees": hue,
    }


def alpha_crop(im: Image.Image, pad: int = 12) -> Image.Image:
    bbox = im.getchannel("A").getbbox()
    if not bbox:
        return im
    x0, y0, x1, y1 = bbox
    return im.crop((max(0, x0-pad), max(0, y0-pad), min(im.width, x1+pad), min(im.height, y1+pad)))


def fit(im: Image.Image, size: tuple[int, int], bg=(31, 34, 37, 255)) -> Image.Image:
    im = im.copy()
    im.thumbnail(size, Image.Resampling.LANCZOS)
    panel = Image.new("RGBA", size, bg)
    panel.alpha_composite(im, ((size[0]-im.width)//2, (size[1]-im.height)//2))
    return panel


def relative_crop(im: Image.Image, box: tuple[float, float, float, float]) -> Image.Image:
    body = alpha_crop(im, 0)
    x0, y0, x1, y1 = box
    return body.crop((round(x0*body.width), round(y0*body.height), round(x1*body.width), round(y1*body.height)))


def make_sheet(p5: Image.Image, proto: Image.Image, runtime: Image.Image) -> None:
    labels = ["P5 control (facet 03)", "CA-structured prototype", "Rome II runtime (unaltered crop)"]
    rows = [
        ("full", None, (1450, 480, 1920, 1080)),
        ("helmet bronze", (.23, .00, .73, .27), (1580, 485, 1870, 705)),
        ("cuirass bronze", (.15, .20, .78, .53), (1460, 650, 1915, 965)),
        ("tunic red", (.12, .38, .80, .73), (960, 505, 1260, 930)),
        ("bronze / cloth boundary", (.10, .18, .86, .65), (1450, 600, 1920, 1000)),
    ]
    panel_w, panel_h, header_h, label_w = 600, 430, 88, 230
    sheet = Image.new("RGB", (label_w + 3*panel_w, header_h + len(rows)*panel_h), (24, 27, 30))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=24)
    small = ImageFont.load_default(size=20)
    for col, label in enumerate(labels):
        draw.text((label_w + col*panel_w + 18, 25), label, fill="white", font=font)
    for row, (name, rel, rbox) in enumerate(rows):
        y = header_h + row*panel_h
        draw.text((14, y+18), name, fill=(225, 225, 225), font=small)
        sources = [alpha_crop(p5), alpha_crop(proto), runtime.crop(rbox)] if rel is None else [relative_crop(p5, rel), relative_crop(proto, rel), runtime.crop(rbox)]
        for col, source in enumerate(sources):
            panel = fit(source.convert("RGBA"), (panel_w, panel_h))
            sheet.paste(panel.convert("RGB"), (label_w + col*panel_w, y))
    sheet.save(OUT / "hastati_ca_structured_comparison.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p5 = Image.open(MASTERS / "P5_CONTROL_F03.png").convert("RGBA")
    proto = Image.open(MASTERS / "CA_STRUCTURED_F03.png").convert("RGBA")
    runtime = Image.open(RUNTIME).convert("RGB")
    masks = {name: Image.open(MASKS / f"{name}_f03.png") for name in ("bronze", "cloth")}
    report = {
        "metric_definition": "display-referred sRGB; Rec.709 luma; HSV saturation; saturation-weighted circular HSV hue",
        "runtime_reference": str(RUNTIME),
        "runtime_metrics_excluded": "No exact semantic mask exists for the scene screenshot; scene-threshold statistics would not be comparable.",
        "P5_CONTROL_F03": {key: semantic_metrics(p5, mask) for key, mask in masks.items()},
        "CA_STRUCTURED_F03": {key: semantic_metrics(proto, mask) for key, mask in masks.items()},
    }
    (OUT / "metrics.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    make_sheet(p5, proto, runtime)


if __name__ == "__main__":
    main()
