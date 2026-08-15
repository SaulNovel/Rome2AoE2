"""Deterministic PNG-to-SLDX v4 authoring adapter."""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
import os
import copy
from pathlib import Path
from typing import Callable

from PIL import Image

from .sld import LAYER_MAIN, LAYER_SHADOW, LAYER_PLAYERCOLOR, SLDFile, SLDFrame, SLDLayer, serialize_sld
from .sld_blocks import ALPHA_THRESHOLD, encode_bc1_block, encode_bc4_block

BLEED_RADIUS = 4


class DirectXTexBC1Encoder:
    """Whole-surface DirectXTex adapter retaining the SLD writer boundary."""
    def __init__(self, executable: Path):
        self.executable = Path(executable)
        self.blocks: list[bytes] = []
        self.blocks_per_row = 0

    def prepare(self, image: Image.Image, threshold: int) -> None:
        if image.width % 4 or image.height % 4:
            raise ValueError("DirectXTex BC1 input dimensions must be divisible by four")
        root = Path.cwd() / "build" / "tmp" / f"rome2aoe2-texconv-{os.getpid()}"
        root.mkdir(parents=True, exist_ok=True); png = root / "source.png"
        image.save(png)
        command = [str(self.executable.resolve()), "-nologo", "-y", "-m", "1", "-f", "BC1_UNORM",
                   "-at", format(threshold / 255.0, ".17g"), "-o", str(root.resolve()), str(png.resolve())]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(f"texconv failed ({result.returncode}): {result.stdout}{result.stderr}")
        data = (root / "source.dds").read_bytes()
        if len(data) < 128 or data[:4] != b"DDS ": raise ValueError("texconv produced an invalid DDS")
        height, width = struct.unpack_from("<II", data, 12)
        if (width, height) != image.size: raise ValueError("texconv changed the BC1 surface dimensions")
        fourcc = data[84:88]
        offset = 148 if fourcc == b"DX10" else 128
        expected = (width // 4) * (height // 4) * 8
        if len(data) != offset + expected: raise ValueError("unexpected DirectXTex DDS payload size")
        self.blocks = [data[index:index+8] for index in range(offset, len(data), 8)]
        self.blocks_per_row = width // 4

    def encode_at(self, _tile, _threshold: int, x: int, y: int) -> bytes:
        return self.blocks[(y // 4) * self.blocks_per_row + (x // 4)]


def visible(alpha: int, threshold: int = ALPHA_THRESHOLD) -> bool:
    return alpha >= threshold


def alpha_bounds(image: Image.Image, threshold: int = ALPHA_THRESHOLD) -> tuple[int, int, int, int] | None:
    rgba = image.convert("RGBA")
    points = [(x, y) for y in range(rgba.height) for x in range(rgba.width) if visible(rgba.getpixel((x, y))[3], threshold)]
    if not points:
        return None
    return min(x for x, _ in points), min(y for _, y in points), max(x for x, _ in points) + 1, max(y for _, y in points) + 1


def block_bounds(bounds: tuple[int, int, int, int] | None, width: int, height: int) -> tuple[int, int, int, int]:
    if bounds is None:
        return 0, 0, min(4, width), min(4, height)
    x1, y1, x2, y2 = bounds
    return max(0, x1 // 4 * 4), max(0, y1 // 4 * 4), min(width, (x2 + 3) // 4 * 4), min(height, (y2 + 3) // 4 * 4)


def bleed_transparent_rgb(image: Image.Image, threshold: int = ALPHA_THRESHOLD, radius: int = BLEED_RADIUS) -> Image.Image:
    """Propagate nearest visible RGB through at most *radius* 8-neighbour steps.

    Each pass reads only the preceding pass; row-major neighbour ordering makes
    ties deterministic. Alpha is copied unchanged.
    """
    result = image.convert("RGBA").copy()
    original_alpha = [result.getpixel((x, y))[3] for y in range(result.height) for x in range(result.width)]
    claimed = {(x, y) for y in range(result.height) for x in range(result.width) if visible(result.getpixel((x, y))[3], threshold)}
    frontier = set(claimed)
    neighbours = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy]
    for _ in range(radius):
        additions: dict[tuple[int, int], tuple[int, int, int]] = {}
        for x, y in sorted(frontier, key=lambda point: (point[1], point[0])):
            rgb = result.getpixel((x, y))[:3]
            for dy, dx in neighbours:
                target = (x + dx, y + dy)
                if 0 <= target[0] < result.width and 0 <= target[1] < result.height and target not in claimed and target not in additions:
                    additions[target] = rgb
        if not additions: break
        for (x, y), rgb in additions.items():
            alpha = result.getpixel((x, y))[3]
            result.putpixel((x, y), (*rgb, alpha))
        frontier = set(additions); claimed.update(additions)
    assert [result.getpixel((x, y))[3] for y in range(result.height) for x in range(result.width)] == original_alpha
    return result


def commands_for_positions(drawn: list[tuple[int, bytes]]) -> tuple[list[tuple[int, int]], list[bytes]]:
    if not drawn: return [(0, 0)], []
    commands, blocks, cursor, index = [], [], 0, 0
    while index < len(drawn):
        position = drawn[index][0]
        skip = position - cursor
        while skip > 255:
            commands.append((255, 0)); skip -= 255
        run_end = index + 1
        while run_end < len(drawn) and drawn[run_end][0] == drawn[run_end - 1][0] + 1: run_end += 1
        emitted = index
        while emitted < run_end:
            count = min(255, run_end - emitted)
            commands.append((skip if emitted == index else 0, count))
            blocks.extend(block for _, block in drawn[emitted:emitted + count])
            emitted += count
        cursor = drawn[run_end - 1][0] + 1; index = run_end
    return commands, blocks


def _rgba_tile(image: Image.Image, x: int, y: int):
    return [[image.getpixel((x + column, y + row)) for column in range(4)] for row in range(4)]


def build_main_layer(image: Image.Image, threshold: int = ALPHA_THRESHOLD,
                     encoder: Callable = encode_bc1_block) -> SLDLayer:
    source = image.convert("RGBA")
    prepared = bleed_transparent_rgb(source, threshold)
    bounds = block_bounds(alpha_bounds(source, threshold), source.width, source.height)
    x1, y1, x2, y2 = bounds; columns = (x2 - x1) // 4
    if hasattr(encoder, "prepare"): encoder.prepare(prepared, threshold)
    drawn = []
    for y in range(y1, y2, 4):
        for x in range(x1, x2, 4):
            tile = _rgba_tile(prepared, x, y)
            if not any(visible(pixel[3], threshold) for row in tile for pixel in row): continue
            block = encoder.encode_at(tile, threshold, x, y) if hasattr(encoder, "encode_at") else encoder(tile, threshold)
            drawn.append((((y-y1)//4)*columns + (x-x1)//4, block))
    commands, blocks = commands_for_positions(drawn)
    return SLDLayer(LAYER_MAIN, x1, y1, x2, y2, commands=commands, blocks=blocks)


def build_shadow_layer(image: Image.Image) -> SLDLayer:
    source = image.convert("RGBA")
    bounds = block_bounds(alpha_bounds(source, 1), source.width, source.height)
    x1, y1, x2, y2 = bounds; columns = (x2 - x1) // 4; drawn = []
    for y in range(y1, y2, 4):
        for x in range(x1, x2, 4):
            tile = [[source.getpixel((x+column, y+row))[3] for column in range(4)] for row in range(4)]
            if not any(value > 0 for row in tile for value in row): continue
            drawn.append((((y-y1)//4)*columns + (x-x1)//4, encode_bc4_block(tile)))
    commands, blocks = commands_for_positions(drawn)
    # Official DE shadow layers consume their complete declared block grid,
    # including a trailing transparent run.  They also set both layer control
    # bytes to 1.  The runtime accepts looser streams for main colour, but can
    # silently ignore a shadow layer that omits these shadow-specific values.
    remaining = columns * ((y2 - y1) // 4) - sum(skip + draw for skip, draw in commands)
    while remaining:
        skip = min(remaining, 255)
        commands.append((skip, 0))
        remaining -= skip
    return SLDLayer(
        LAYER_SHADOW, x1, y1, x2, y2,
        flag1=1, unknown1=1, commands=commands, blocks=blocks,
    )


def build_playercolor_layer(image: Image.Image, main_layer: SLDLayer) -> SLDLayer:
    """Encode shaded player-colour coverage on the main layer's block grid.

    AoE2 DE stores this dependent layer without independent bounds.  Zero-only
    blocks are skipped; non-zero grayscale values retain authored shading.
    """
    source = image.convert("RGBA")
    x1, y1, x2, y2 = (main_layer.offset_x1, main_layer.offset_y1,
                      main_layer.offset_x2, main_layer.offset_y2)
    if x2 > source.width or y2 > source.height:
        raise ValueError("player-color canvas is smaller than the main layer")
    columns = (x2 - x1) // 4
    drawn = []
    for y in range(y1, y2, 4):
        for x in range(x1, x2, 4):
            tile = []
            for row in range(4):
                values = []
                for column in range(4):
                    red, green, blue, alpha = source.getpixel((x + column, y + row))
                    values.append(round((0.2126 * red + 0.7152 * green + 0.0722 * blue) * alpha / 255.0))
                tile.append(values)
            if not any(value for row in tile for value in row):
                continue
            drawn.append((((y-y1)//4)*columns + (x-x1)//4, encode_bc4_block(tile)))
    commands, blocks = commands_for_positions(drawn)
    return SLDLayer(LAYER_PLAYERCOLOR, commands=commands, blocks=blocks)


def author_one_frame(main: Image.Image, shadow: Image.Image | None, hotspot: tuple[int, int] = (100, 100),
                     player_color: Image.Image | None = None,
                     threshold: int = ALPHA_THRESHOLD, encoder: Callable = encode_bc1_block) -> SLDFile:
    if shadow is not None and main.size != shadow.size: raise ValueError("main and shadow canvases differ")
    if player_color is not None and main.size != player_color.size: raise ValueError("main and player-color canvases differ")
    layers = [build_main_layer(main, threshold, encoder)]
    if shadow is not None: layers.append(build_shadow_layer(shadow))
    if player_color is not None: layers.append(build_playercolor_layer(player_color, layers[0]))
    frame_type=LAYER_MAIN | (LAYER_SHADOW if shadow is not None else 0) | (LAYER_PLAYERCOLOR if player_color is not None else 0)
    frame = SLDFrame(main.width, main.height, hotspot[0], hotspot[1], frame_type, layers=layers)
    return SLDFile(frames=[frame], facet_count=1)


def author_identical_facets(main: Image.Image, shadow: Image.Image | None, facet_count: int = 16,
                            hotspot: tuple[int, int] = (100, 100), threshold: int = ALPHA_THRESHOLD,
                            encoder: Callable = encode_bc1_block, player_color: Image.Image | None = None) -> SLDFile:
    if facet_count < 1: raise ValueError("facet count must be positive")
    source = author_one_frame(main, shadow, hotspot, player_color, threshold, encoder)
    frames=[]
    for index in range(facet_count):
        frame=copy.deepcopy(source.frames[0]); frame.frame_index=index; frames.append(frame)
    return SLDFile(frames=frames, facet_count=facet_count)


def author_direction_frames(frames: list[tuple[Image.Image, Image.Image | None, Image.Image | None]],
                            hotspot: tuple[int, int], facet_count: int,
                            threshold: int = ALPHA_THRESHOLD,
                            encoder_factory: Callable[[], Callable] | None = None) -> SLDFile:
    """Author source-ordered direction frames without mirroring or recentering."""
    if len(frames) != facet_count or facet_count < 1:
        raise ValueError("direction frame count must equal facet count")
    result = []
    for index, (main, shadow, player_color) in enumerate(frames):
        encoder = encoder_factory() if encoder_factory else encode_bc1_block
        frame = author_one_frame(main, shadow, hotspot, player_color, threshold, encoder).frames[0]
        frame.frame_index = index
        result.append(frame)
    return SLDFile(frames=result, facet_count=facet_count)


def author_facet_animation(
    frames: list[tuple[Image.Image, Image.Image | None, Image.Image | None]],
    hotspot: tuple[int, int],
    facet_count: int,
    frames_per_facet: int,
    threshold: int = ALPHA_THRESHOLD,
    encoder_factory: Callable[[], Callable] | None = None,
) -> SLDFile:
    """Author facet-major animation frames without mirroring or recentering."""
    if facet_count < 1 or frames_per_facet < 1:
        raise ValueError("facet and animation frame counts must be positive")
    if len(frames) != facet_count * frames_per_facet:
        raise ValueError("animation frame count does not match facets x frames-per-facet")
    result = []
    for index, (main, shadow, player_color) in enumerate(frames):
        encoder = encoder_factory() if encoder_factory else encode_bc1_block
        frame = author_one_frame(
            main, shadow, hotspot, player_color, threshold, encoder
        ).frames[0]
        frame.frame_index = index
        result.append(frame)
    return SLDFile(frames=result, facet_count=facet_count)


def premultiplied_bicubic(image: Image.Image, size: tuple[int, int], alpha_scale: float = 1.0) -> Image.Image:
    """Use the calibrated alpha-correct downsampler without changing its policy."""
    from src.blender.downsample_rgba import downsample_rgba
    source=image.convert("RGBA")
    pixels=[value/255.0 for value in source.tobytes()]
    result=downsample_rgba(pixels,source.width,source.height,size[0],size[1],"bicubic")
    for index in range(3,len(result),4): result[index]=min(1.0,max(0.0,result[index]*alpha_scale))
    return Image.frombytes("RGBA",size,bytes(round(min(1,max(0,value))*255) for value in result))


def build_manifest(main_path: Path, shadow_path: Path, output_path: Path, sld: SLDFile, encoder_name: str = "basic") -> dict:
    for path in (main_path, shadow_path, output_path):
        if path.is_absolute():
            raise ValueError("deterministic manifest paths must be relative")
    frame = sld.frames[0]
    return {"format":"rome2aoe2.sld-authoring", "version":1, "alpha_threshold":ALPHA_THRESHOLD, "bc1_encoder":encoder_name,
            "main_image":main_path.as_posix(), "shadow_image":shadow_path.as_posix(), "output":output_path.as_posix(),
            "canvas":{"width":frame.canvas_width,"height":frame.canvas_height},
            "hotspot":{"x":frame.center_x,"y":frame.center_y}, "frame_count":len(sld.frames), "facet_count":sld.facet_count,
            "layers":[{"type":layer.layer_type,"bounds":[layer.offset_x1,layer.offset_y1,layer.offset_x2,layer.offset_y2],
                       "commands":len(layer.commands),"blocks":len(layer.blocks)} for layer in frame.layers]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--main", required=True); parser.add_argument("--shadow", required=True)
    parser.add_argument("--output", required=True); parser.add_argument("--report", required=True)
    parser.add_argument("--bc1-encoder", choices=("basic","directxtex"), default="basic")
    parser.add_argument("--texconv")
    args = parser.parse_args()
    main_path, shadow_path, output_path = Path(args.main), Path(args.shadow), Path(args.output)
    if args.bc1_encoder == "directxtex":
        if not args.texconv: parser.error("--texconv is required for --bc1-encoder directxtex")
        encoder = DirectXTexBC1Encoder(Path(args.texconv))
    else: encoder = encode_bc1_block
    sld = author_one_frame(Image.open(main_path), Image.open(shadow_path), encoder=encoder)
    output_path.parent.mkdir(parents=True, exist_ok=True); output_path.write_bytes(serialize_sld(sld))
    report = build_manifest(Path(main_path.name), Path(shadow_path.name), Path(output_path.name), sld, args.bc1_encoder)
    Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    return 0


if __name__ == "__main__": raise SystemExit(main())
