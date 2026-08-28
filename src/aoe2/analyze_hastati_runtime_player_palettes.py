"""Evaluate the installed AoE2 DE player ramps against the approved shield."""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "build" / "python-deps" / "sld-authoring"
if LOCAL.is_dir():
    sys.path.insert(0, str(LOCAL))
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw

from aoe2.analyze_hastati_player_colour_proof import HISTORICAL_TARGETS, historical_tint, player_scalar, sheet
from aoe2.sld import parse_sld

PROOF = ROOT / "build" / "validation" / "hastati-player-colour-proof"
PALETTES = Path(r"C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\palettes")
NAMES = ("blue", "red", "green", "yellow")
WEIGHTS = {"red": 3, "blue": 1, "green": 1, "yellow": 1}
RAMP = range(42, 48)
LUMA = (.2126, .7152, .0722)


def palette(name):
    lines = (PALETTES / f"playercolor_{name}.pal").read_text(encoding="utf-8").splitlines()
    return [tuple(map(int, line.split())) for line in lines[3:259]]


def colour_distance(left, right):
    return sum((left[channel] - right[channel]) ** 2 for channel in range(3))


def luminance(colour):
    return sum(weight * value for weight, value in zip(LUMA, colour))


def runtime_images(source, support, desired, palettes):
    outputs = {name: source.copy() for name in NAMES}
    output_pixels = {name: [] for name in NAMES}
    indices = []
    for position, (base, mask) in enumerate(zip(source.get_flattened_data(), support.get_flattened_data())):
        if mask <= 1 or base[3] == 0:
            indices.append(255)
            for name in NAMES:
                output_pixels[name].append(base)
            continue
        best = min(RAMP, key=lambda index: sum(
            WEIGHTS[name] * colour_distance(desired[name][position][:3], palettes[name][index])
            for name in NAMES
        ))
        indices.append(best)
        for name in NAMES:
            output_pixels[name].append((*palettes[name][best], base[3]))
    for name in NAMES:
        outputs[name].putdata(output_pixels[name])
    scalar = Image.new("L", source.size); scalar.putdata(indices)
    return outputs, scalar, indices


def swatch_sheet(palettes, path):
    cell_w, cell_h = 104, 72
    image = Image.new("RGB", (16 * cell_w, 4 * cell_h), (24, 24, 24))
    draw = ImageDraw.Draw(image)
    for row, name in enumerate(NAMES):
        for column, index in enumerate(RAMP):
            x, y = column * cell_w, row * cell_h
            draw.rectangle((x, y, x + cell_w - 1, y + cell_h - 1), fill=palettes[name][index])
            draw.text((x + 4, y + 4), f"{name} {index}", fill="white" if luminance(palettes[name][index]) < 110 else "black")
            draw.text((x + 4, y + 20), str(palettes[name][index]), fill="white" if luminance(palettes[name][index]) < 110 else "black")
    image.save(path)


def main():
    source = Image.open(PROOF / "render" / "x2" / "idle-direction-04-frame-000.png").convert("RGBA")
    document = parse_sld((PROOF / "hastati-player-colour-proof_x2.sld").read_bytes())
    support, _, _ = player_scalar(document)
    palettes = {name: palette(name) for name in NAMES}
    desired_images = {"red": source}
    desired_images.update({name: historical_tint(source, support, HISTORICAL_TARGETS[name.upper()])
                           for name in ("blue", "green", "yellow")})
    desired = {name: list(image.get_flattened_data()) for name, image in desired_images.items()}
    outputs, scalar, indices = runtime_images(source, support, desired, palettes)
    scalar.save(PROOF / "runtime-player-scalar-indices.png")
    sheet([("APPROVED BASELINE RED", source), ("REAL AOE RED RAMP", outputs["red"])],
          PROOF / "approved-red-vs-real-aoe-red.png", columns=2)
    sheet([("APPROVED RED BASELINE", source)] + [(f"REAL AOE {name.upper()}", outputs[name]) for name in NAMES],
          PROOF / "real-aoe-player-ramp-results.png", columns=3)
    mask_preview = Image.new("RGBA", source.size, (0, 0, 0, 0))
    mask_preview.putdata([(235, 80, 235, value) for value in support.get_flattened_data()])
    comparison = [("APPROVED BASELINE SHIELD", source), ("PAINTED-FACE MASK ONLY", mask_preview)]
    for name in NAMES:
        comparison.extend([(f"REAL AOE {name.upper()}", outputs[name]),
                           (f"AGED TARGET {name.upper()}", desired_images[name])])
    sheet(comparison, PROOF / "shield-player-real-vs-aged.png", columns=2)
    swatch_sheet(palettes, PROOF / "real-aoe-player-ramp-42-47.png")

    active = [position for position, value in enumerate(support.get_flattened_data()) if value > 1]
    metrics = {}
    closest = {}
    for name in NAMES:
        rgb_errors = []
        luminance_errors = []
        target_pixels = desired[name]
        result_pixels = list(outputs[name].get_flattened_data())
        mean_target = tuple(round(statistics.fmean(target_pixels[p][channel] for p in active)) for channel in range(3))
        nearest_all = min(range(128), key=lambda index: colour_distance(mean_target, palettes[name][index]))
        nearest_ramp = min(RAMP, key=lambda index: colour_distance(mean_target, palettes[name][index]))
        closest[name] = {
            "mean_target_rgb": list(mean_target),
            "nearest_all_index": nearest_all, "nearest_all_rgb": list(palettes[name][nearest_all]),
            "nearest_selected_ramp_index": nearest_ramp,
            "nearest_selected_ramp_rgb": list(palettes[name][nearest_ramp]),
        }
        for position in active:
            target = target_pixels[position][:3]; result = result_pixels[position][:3]
            rgb_errors.append(sum(abs(target[c] - result[c]) for c in range(3)) / 3)
            luminance_errors.append(abs(luminance(target) - luminance(result)))
        metrics[name] = {
            "mean_rgb_absolute_error": round(statistics.fmean(rgb_errors), 3),
            "mean_luminance_error": round(statistics.fmean(luminance_errors), 3),
        }
    active_indices = [value for value in indices if value != 255]
    report = {
        "format": "rome2aoe2.hastati-real-player-ramp-audit", "version": 1,
        "palette_source": str(PALETTES),
        "runtime_semantics": "SLD BC4 value is a direct 0-255 player palette index; 255/no drawn block retains main colour",
        "shared_scalar_constraint": "one scalar/index map is shared by all owning-player palettes",
        "selected_ramp": [42, 47],
        "selection": "per shield pixel minimize installed-palette RGB error; approved red weighted 3x, blue/green/yellow aged targets weighted 1x",
        "scalar_indices": {
            "minimum": min(active_indices), "maximum": max(active_indices),
            "median": statistics.median(active_indices),
            "distribution": {str(index): count for index, count in sorted(Counter(active_indices).items())},
        },
        "closest_entries": closest, "result_metrics": metrics,
        "verdict": "Standard full-face player colour cannot reproduce every aged target: red is close, green is usable, blue remains indigo/purple and yellow remains olive. The most realistic implementable solution is approved authored dark-red main colour plus a deliberate shield-face accent using dark indices 42-47.",
        "production_recommendation": {
            "shield": "retain approved authored shield unchanged outside a restrained painted-face accent",
            "player_support": "shield painted face only; never boss, rim, hardware, cloth, armour, skin, crest or weapons",
            "scalar_indices": [42, 47],
            "reason": "preserves most authored shield texture/chroma while the installed player ramp supplies recognizable ownership colour in a bounded area",
        },
        "artifacts": ["approved-red-vs-real-aoe-red.png", "real-aoe-player-ramp-results.png",
                      "shield-player-real-vs-aged.png", "real-aoe-player-ramp-42-47.png",
                      "runtime-player-scalar-indices.png"],
    }
    (PROOF / "real-aoe-player-ramp-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
