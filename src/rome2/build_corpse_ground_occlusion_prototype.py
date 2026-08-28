"""Build x2-only corpse ground-occlusion review sheets; never authors game assets."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "build/python-deps/pillow")]
from PIL import Image, ImageDraw, ImageFont

FONT = ImageFont.load_default()
CANVAS = (400, 400)
OLD = {"linger": 8.0, "sink": 52.0, "frames": 60, "frame_duration": 1.0}
NEW = {"linger": 10.0, "sink": 530.0, "frames": 54, "frame_duration": 10.0}
DIRECTIONS = (0, 6, 7, 14)


def ease(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def translate(source: Image.Image, offset: int) -> Image.Image:
    out = Image.new("RGBA", source.size)
    out.alpha_composite(source, (0, offset))
    return out


def line_clip(source: Image.Image, offset: int) -> Image.Image:
    if offset == 0:
        return source.copy()
    box = source.getchannel("A").getbbox()
    moved = translate(source, offset)
    out = Image.new("RGBA", source.size)
    out.paste(moved.crop((0, 0, source.width, box[3])), (0, 0))
    return out


def aperture_clip(source: Image.Image, offset: int) -> tuple[Image.Image, dict]:
    """Binary projected ground aperture derived from the complete silhouette footprint."""
    box = source.getchannel("A").getbbox()
    if offset == 0:
        return source.copy(), {"bounds": box, "lip_depth": 0}
    left, top, right, bottom = box
    half = max((right - left) / 2.0, 1.0)
    center = (left + right) / 2.0
    lip_depth = max(4, min(12, round((bottom - top) * 0.15)))
    moved = translate(source, offset)
    alpha = moved.getchannel("A")
    mask = Image.new("L", source.size)
    pixels = mask.load()
    for x in range(max(0, left - 2), min(source.width, right + 2)):
        u = min(1.0, abs(x - center) / half)
        boundary = round(bottom + lip_depth * math.sqrt(max(0.0, 1.0 - u * u)))
        for y in range(max(0, top), min(source.height, boundary)):
            pixels[x, y] = 255
    alpha = Image.composite(alpha, Image.new("L", source.size), mask)
    moved.putalpha(alpha)
    return moved, {"bounds": box, "lip_depth": lip_depth}


def tile(image: Image.Image, title: str, scale: float = 1.0) -> Image.Image:
    shown = image if scale == 1 else image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (shown.width, shown.height + 24), (25, 28, 31, 255))
    out.alpha_composite(shown, (0, 24)); ImageDraw.Draw(out).text((5, 6), title, font=FONT, fill="white")
    return out


def sheet(rows: list[list[tuple[Image.Image, str]]], output: Path, scale: float = 1.0) -> None:
    rendered = [[tile(im, label, scale) for im, label in row] for row in rows]
    width = max(sum(x.width for x in row) for row in rendered); height = sum(max(x.height for x in row) for row in rendered)
    out = Image.new("RGBA", (width, height), (15, 17, 19, 255)); y = 0
    for row in rendered:
        x = 0
        for cell in row: out.alpha_composite(cell, (x, y)); x += cell.width
        y += max(cell.height for cell in row)
    output.parent.mkdir(parents=True, exist_ok=True); out.convert("RGB").save(output)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--render-report", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); report = json.loads(args.render_report.read_text()); root = args.render_report.parent; count = int(report["rendered_sample_count"])
    sources = {d: Image.open(root / "main/x2" / f"death-direction-{d:02d}-frame-{count-1:03d}.png").convert("RGBA") for d in DIRECTIONS}
    fractions = (0.0, 0.25, 0.5, 0.75, 1.0); offsets = [round(96 * ease(t)) for t in fractions]
    old_new = []
    for d in DIRECTIONS:
        row = []
        for t, off in zip(fractions, offsets):
            im, _ = aperture_clip(sources[d], off); row.append((im, f"D{d} new {t:.0%} / {NEW['linger'] + t*NEW['sink']:.0f}s"))
        old_new.append(row)
    sheet(old_new, args.output / "corpse-ground-early-25-50-75-final-x2.png")
    comparisons = []
    for d in DIRECTIONS:
        old_mid = line_clip(sources[d], offsets[2]); new_mid, _ = aperture_clip(sources[d], offsets[2])
        comparisons.append([(old_mid, f"D{d} old horizontal clip"), (new_mid, f"D{d} projected ground aperture")])
    sheet(comparisons, args.output / "corpse-old-line-vs-ground-plane-x2.png")
    timeline = []
    for d in (6, 7):
        row = []
        for t, off in zip(fractions, offsets):
            old = line_clip(sources[d], off); new, _ = aperture_clip(sources[d], off)
            row.extend([(old, f"old {OLD['linger']+t*OLD['sink']:.0f}s"), (new, f"new {NEW['linger']+t*NEW['sink']:.0f}s")])
        timeline.append(row)
    sheet(timeline, args.output / "corpse-old-60s-vs-new-540s-timeline-x2.png")
    game = []
    for d in DIRECTIONS:
        row = []
        for t, off in zip((0.0, .5, .75, 1.0), (offsets[0], offsets[2], offsets[3], offsets[4])):
            im, _ = aperture_clip(sources[d], off); row.append((im, f"D{d} {t:.0%}"))
        game.append(row)
    sheet(game, args.output / "corpse-ground-plane-game-scale.png", .5)
    sink_offsets = [round(96 * ease(i / 52)) for i in range(53)]; deltas = [b-a for a, b in zip(sink_offsets, sink_offsets[1:])]
    meta = {"format":"rome2aoe2.corpse-ground-occlusion-prototype","version":1,"release_eligible":False,"source":str(args.render_report),"directions":DIRECTIONS,"old":OLD,"proposed":NEW,"total_lifetime":540.0,"sink_frames":53,"sink_transitions":52,"sink_travel_x2":96,"average_pixels_per_transition":sum(deltas)/len(deltas),"maximum_pixels_per_transition":max(deltas),"seconds_per_transition":10.0,"occlusion":{"model":"binary projected ground aperture","derivation":"generic final-alpha footprint; shallow elliptical near lip; no per-direction hand tuning","alpha_fade":False,"limitation":"RGBA-only approximation; physically exact terrain intersection requires a world-height mask pass"},"outputs":[str(p) for p in sorted(args.output.glob("*.png"))]}
    (args.output / "corpse-ground-occlusion-review.json").write_text(json.dumps(meta, indent=2) + "\n")


if __name__ == "__main__": main()
