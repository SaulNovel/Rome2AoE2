"""Build a shield-only, shading-preserving Hastati player-colour proof."""

from __future__ import annotations

import argparse
import colorsys
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "build" / "python-deps" / "sld-authoring"
if LOCAL.is_dir():
    sys.path.insert(0, str(LOCAL))
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw

from aoe2.analyze_sld import decode_frame
from aoe2.sld import LAYER_MAIN, LAYER_PLAYERCOLOR, parse_sld, serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder, author_one_frame
from aoe2.sld_blocks import decode_bc4_block

COLOURS = {
    "BLUE": (48, 92, 224),
    "RED": (202, 49, 43),
    "GREEN": (42, 151, 72),
    "YELLOW": (226, 190, 46),
}
HISTORICAL_TARGETS = {
    "BLUE": (40, 57, 82),
    "RED": (105, 39, 35),
    "GREEN": (61, 78, 43),
    "YELLOW": (119, 87, 37),
}


def player_scalar(document):
    frame = document.frames[0]
    main = next(layer for layer in frame.layers if layer.layer_type == LAYER_MAIN)
    layer = next(layer for layer in frame.layers if layer.layer_type == LAYER_PLAYERCOLOR)
    image = Image.new("L", (frame.canvas_width, frame.canvas_height), 0)
    columns = (main.offset_x2 - main.offset_x1) // 4
    cursor = block_index = 0
    for skip, draw in layer.commands:
        cursor += skip
        for _ in range(draw):
            x = main.offset_x1 + (cursor % columns) * 4
            y = main.offset_y1 + (cursor // columns) * 4
            block = decode_bc4_block(layer.blocks[block_index])
            for row in range(4):
                for column in range(4):
                    image.putpixel((x + column, y + row), block[row][column])
            cursor += 1
            block_index += 1
    return image, layer, cursor


def tint(main, scalar, colour):
    output = main.copy()
    pixels = []
    target_luminance = sum(weight * value for weight, value in zip((.2126, .7152, .0722), colour))
    for base, shade in zip(main.get_flattened_data(), scalar.get_flattened_data()):
        if shade <= 1 or base[3] == 0:
            pixels.append(base)
            continue
        luminance = shade
        tinted = tuple(min(255, round(channel * luminance / target_luminance)) for channel in colour)
        pixels.append((*tinted, base[3]))
    output.putdata(pixels)
    return output


def muted_tint(main, scalar, colour, hue_influence=.75, saturation_cap=.48):
    """Bias shield hue toward the player while retaining approved local value.

    The original pixel remains the material/value source. Hue moves toward the
    owning player enough to stay readable, but saturation is source-weighted and
    tightly capped, then sRGB luminance is corrected back to the original pixel.
    """
    output = main.copy()
    pixels = []
    player_hue, player_sat, _ = colorsys.rgb_to_hsv(*(channel / 255 for channel in colour))
    weights = (.2126, .7152, .0722)
    for base, shade in zip(main.get_flattened_data(), scalar.get_flattened_data()):
        if shade <= 1 or base[3] == 0:
            pixels.append(base)
            continue
        rgb = tuple(channel / 255 for channel in base[:3])
        base_hue, base_sat, base_value = colorsys.rgb_to_hsv(*rgb)
        hue_delta = (player_hue - base_hue + .5) % 1.0 - .5
        hue = (base_hue + hue_delta * hue_influence) % 1.0
        saturation = min(saturation_cap, base_sat * .80 + player_sat * .20)
        candidate = colorsys.hsv_to_rgb(hue, saturation, base_value)
        base_luminance = sum(weight * channel for weight, channel in zip(weights, base[:3]))
        candidate_luminance = sum(weight * channel * 255 for weight, channel in zip(weights, candidate))
        scale = base_luminance / max(candidate_luminance, 1e-6)
        muted = tuple(min(255, round(channel * 255 * scale)) for channel in candidate)
        pixels.append((*muted, base[3]))
    output.putdata(pixels)
    return output


def historical_tint(main, scalar, target, saturation_cap=.42):
    """Apply an aged-pigment hue while preserving approved local light form."""
    output = main.copy()
    pixels = []
    target_hue, target_sat, _ = colorsys.rgb_to_hsv(*(channel / 255 for channel in target))
    weights = (.2126, .7152, .0722)
    for base, support in zip(main.get_flattened_data(), scalar.get_flattened_data()):
        if support <= 1 or base[3] == 0:
            pixels.append(base)
            continue
        _, base_sat, base_value = colorsys.rgb_to_hsv(*(channel / 255 for channel in base[:3]))
        # Direct target hue avoids the red-to-blue interpolation path through purple.
        saturation = min(saturation_cap, base_sat * .55 + target_sat * .45)
        candidate = colorsys.hsv_to_rgb(target_hue, saturation, base_value)
        base_luminance = sum(weight * channel for weight, channel in zip(weights, base[:3]))
        candidate_luminance = sum(weight * channel * 255 for weight, channel in zip(weights, candidate))
        scale = base_luminance / max(candidate_luminance, 1e-6)
        aged = tuple(min(255, round(channel * 255 * scale)) for channel in candidate)
        pixels.append((*aged, base[3]))
    output.putdata(pixels)
    return output


def crop_panel(image, box, size=440):
    crop = image.crop(box)
    crop.thumbnail((size, size), Image.Resampling.NEAREST)
    panel = Image.new("RGB", (size, size), (30, 30, 30))
    checker = Image.new("RGBA", crop.size)
    draw = ImageDraw.Draw(checker)
    step = 16
    for y in range(0, crop.height, step):
        for x in range(0, crop.width, step):
            value = 62 if (x // step + y // step) % 2 else 88
            draw.rectangle((x, y, x + step - 1, y + step - 1), fill=(value, value, value, 255))
    checker.alpha_composite(crop)
    panel.paste(checker.convert("RGB"), ((size - crop.width) // 2, (size - crop.height) // 2))
    return panel


def sheet(items, path, columns=3):
    cell, header = 440, 34
    rows = math.ceil(len(items) / columns)
    output = Image.new("RGB", (columns * cell, rows * (cell + header)), (24, 24, 24))
    draw = ImageDraw.Draw(output)
    boxes = [image.getchannel("A").getbbox() for _, image in items if image.mode == "RGBA"]
    union = tuple((min(box[i] for box in boxes) if i < 2 else max(box[i] for box in boxes)) for i in range(4))
    margin = 12
    union = (max(0, union[0] - margin), max(0, union[1] - margin),
             min(items[0][1].width, union[2] + margin), min(items[0][1].height, union[3] + margin))
    for index, (label, image) in enumerate(items):
        x, y = (index % columns) * cell, (index // columns) * (cell + header)
        draw.text((x + 8, y + 10), label, fill=(245, 245, 245))
        rgba = image.convert("RGBA")
        output.paste(crop_panel(rgba, union, cell), (x, y + header))
    output.save(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--texconv", type=Path, required=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    records = {}
    proof_items = []
    decoded_items = []
    comparison_items = []
    muted_metrics = {}
    historical_metrics = {}
    for zoom, canvas in (("x1", 200), ("x2", 400)):
        source = Image.open(args.render_root / zoom / "idle-direction-04-frame-000.png").convert("RGBA")
        player = Image.open(args.render_root / "player-colour" / zoom / "idle-direction-04-frame-000.png").convert("RGBA")
        encoder = DirectXTexBC1Encoder(args.texconv)
        document = author_one_frame(source, None, (canvas // 2, canvas // 2), player_color=player, encoder=encoder)
        sld_path = args.output_root / f"hastati-player-colour-proof_{zoom}.sld"
        sld_path.write_bytes(serialize_sld(document))
        parsed = parse_sld(sld_path.read_bytes())
        decoded_main, _ = decode_frame(parsed, 0)
        decoded_player, layer, consumed = player_scalar(parsed)
        control = author_one_frame(
            source, None, (canvas // 2, canvas // 2),
            encoder=DirectXTexBC1Encoder(args.texconv),
        )
        control_main, _ = decode_frame(parse_sld(serialize_sld(control)), 0)
        decoded_main.save(args.output_root / f"decoded-main-{zoom}.png")
        decoded_player.save(args.output_root / f"decoded-player-colour-{zoom}.png")
        mask = player.getchannel("A")
        mask_pixels = sum(value > 8 for value in mask.get_flattened_data())
        body_pixels = sum(value > 8 for value in source.getchannel("A").get_flattened_data())
        transport_alpha_errors = sum(a != b for a, b in zip(source.getchannel("A").get_flattened_data(), decoded_main.getchannel("A").get_flattened_data()))
        player_alpha_errors = sum(a != b for a, b in zip(control_main.getchannel("A").get_flattened_data(), decoded_main.getchannel("A").get_flattened_data()))
        player_main_pixel_errors = sum(a != b for a, b in zip(control_main.get_flattened_data(), decoded_main.get_flattened_data()))
        grid = sum(skip + draw for skip, draw in layer.commands)
        records[zoom] = {
            "canvas": [canvas, canvas], "frame_type": parsed.frames[0].frame_type,
            "player_layer_flags": [layer.flag1, layer.unknown1],
            "player_layer_blocks": len(layer.blocks), "player_grid_blocks_consumed": consumed,
            "player_grid_blocks_from_commands": grid,
            "player_pixels_over_threshold": mask_pixels,
            "player_coverage_of_body": round(mask_pixels / body_pixels, 4),
            "source_to_bc1_alpha_differences": transport_alpha_errors,
            "player_layer_silhouette_changes": player_alpha_errors,
            "player_layer_main_rgba_changes": player_main_pixel_errors,
            "main_layer_unchanged_by_player_layer": player_main_pixel_errors == 0,
        }
        scalar_rgba = Image.merge("RGBA", (decoded_player, decoded_player, decoded_player, decoded_player))
        display_size = (400, 400)
        decoded_items.extend([
            (f"SOURCE {zoom.upper()}", source.resize(display_size, Image.Resampling.NEAREST)),
            (f"DECODED MAIN {zoom.upper()}", decoded_main.resize(display_size, Image.Resampling.NEAREST)),
            (f"DECODED PLAYER {zoom.upper()}", scalar_rgba.resize(display_size, Image.Resampling.NEAREST)),
        ])
        if zoom == "x2":
            isolated = Image.new("RGBA", source.size, (0, 0, 0, 0))
            isolated.putdata([(235, 80, 235, value) for value in mask.get_flattened_data()])
            sheet([("APPROVED BASELINE", source), ("SHIELD PLAYER MASK", isolated)],
                  args.output_root / "player-colour-mask-preview.png", columns=2)
            muted = {name: muted_tint(source, decoded_player, colour) for name, colour in COLOURS.items()}
            proof_items = [("APPROVED BASELINE", source)] + [
                (f"MUTED PLAYER {name}", image) for name, image in muted.items()
            ]
            sheet(proof_items, args.output_root / "player-colour-representative-previews.png", columns=3)
            comparison_items = [("APPROVED BASELINE", source)]
            for name, colour in COLOURS.items():
                comparison_items.extend([
                    (f"CURRENT FULL {name}", tint(source, decoded_player, colour)),
                    (f"PROPOSED MUTED {name}", muted[name]),
                ])
                outside_changes = luminance_errors = selected = 0
                for original, result, support in zip(source.get_flattened_data(), muted[name].get_flattened_data(), decoded_player.get_flattened_data()):
                    if support <= 1:
                        outside_changes += original != result
                    elif original[3]:
                        selected += 1
                        left = sum(weight * channel for weight, channel in zip((.2126, .7152, .0722), original[:3]))
                        right = sum(weight * channel for weight, channel in zip((.2126, .7152, .0722), result[:3]))
                        luminance_errors += abs(left - right)
                muted_metrics[name.lower()] = {
                    "non_player_rgba_changes": outside_changes,
                    "selected_pixels": selected,
                    "mean_selected_luminance_error": round(luminance_errors / max(selected, 1), 4),
                }
            sheet(comparison_items, args.output_root / "player-colour-bright-vs-muted.png", columns=3)
            historical = {name: historical_tint(source, decoded_player, HISTORICAL_TARGETS[name])
                          for name in COLOURS}
            sheet([("APPROVED BASELINE", source)] + [
                      (f"AGED PIGMENT {name}", image) for name, image in historical.items()],
                  args.output_root / "player-colour-aged-pigment-previews.png", columns=3)
            aged_comparison = []
            for name in COLOURS:
                aged_comparison.extend([
                    (f"CURRENT MUTED {name}", muted[name]),
                    (f"IMPROVED AGED {name}", historical[name]),
                ])
                outside_changes = luminance_errors = selected = 0
                for original, result, support in zip(source.get_flattened_data(), historical[name].get_flattened_data(), decoded_player.get_flattened_data()):
                    if support <= 1:
                        outside_changes += original != result
                    elif original[3]:
                        selected += 1
                        left = sum(weight * channel for weight, channel in zip((.2126, .7152, .0722), original[:3]))
                        right = sum(weight * channel for weight, channel in zip((.2126, .7152, .0722), result[:3]))
                        luminance_errors += abs(left - right)
                historical_metrics[name.lower()] = {
                    "target_rgb": list(HISTORICAL_TARGETS[name]),
                    "non_player_rgba_changes": outside_changes,
                    "selected_pixels": selected,
                    "mean_selected_luminance_error": round(luminance_errors / max(selected, 1), 4),
                }
            sheet(aged_comparison, args.output_root / "player-colour-muted-vs-aged.png", columns=2)
    sheet(decoded_items, args.output_root / "decoded-x1-x2-proof.png", columns=3)
    report = {
        "format": "rome2aoe2.hastati-player-colour-proof", "version": 1,
        "scope": "shield DecalDirtmap Rome II faction-mask pixels only",
        "encoding": "SLDX v4 dependent player-colour BC4; approved final luminance multiplied by semantic mask coverage",
        "shading_policy": "runtime player hue replaces hue only; BC4 scalar retains local approved-render luminance, wear, curvature and lighting",
        "muted_preview_formula": {
            "model": "source-biased HSV hue interpolation followed by exact sRGB-luminance correction",
            "hue_influence": 0.75,
            "saturation": "80% source + 20% player, capped at 0.48",
            "value": "source HSV value",
            "final_luminance": "rescaled to the approved source pixel luminance",
        },
        "runtime_feasibility_note": "The native SLD BC4 player layer supplies a scalar/player-palette lookup, not an independently verified RGB alpha blend. Offline muted appearance must be runtime-tested; if the engine fully replaces hue, preserving source chroma may require limiting player-colour support to accents rather than changing material RGB.",
        "muted_preview_metrics_x2": muted_metrics,
        "aged_pigment_formula": {
            "model": "explicit historical pigment hue with source-weighted restrained saturation and source-luminance correction",
            "targets_rgb": {name.lower(): list(value) for name, value in HISTORICAL_TARGETS.items()},
            "hue": "direct target pigment hue; no red-to-player interpolation path",
            "saturation": "55% source + 45% target, capped at 0.42",
            "value": "approved source HSV value",
            "final_luminance": "rescaled to approved source pixel luminance",
        },
        "aged_pigment_metrics_x2": historical_metrics,
        "recommendation": "Use the aged-pigment mapping as the visual target; direct navy hue prevents blue from drifting through purple.",
        "accent_fallback": "If SLD runtime palette replacement cannot match this target, retain the approved dark-red shield in main colour and author a deliberate shield accent as the only nonzero player-colour support. Do not simulate partial tint with random dithering.",
        "non_player_regions": "main BC1 layer is authored unchanged; player layer has zero support outside shield faction mask",
        "runtime_status": "offline proof only; not packaged or installed",
        "records": records,
        "artifacts": ["player-colour-mask-preview.png", "player-colour-representative-previews.png",
                      "player-colour-bright-vs-muted.png",
                      "player-colour-aged-pigment-previews.png", "player-colour-muted-vs-aged.png",
                      "decoded-x1-x2-proof.png", "hastati-player-colour-proof_x1.sld",
                      "hastati-player-colour-proof_x2.sld"],
    }
    (args.output_root / "player-colour-proof-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
