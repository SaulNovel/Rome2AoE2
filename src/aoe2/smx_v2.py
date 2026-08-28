"""Minimal SMPX v2 main-colour writer for frozen AoE2 sprite frames.

The layout follows the SMX reader shipped in AoE2 DE's licensed genieutils
source.  It deliberately emits only the main layer; shadow/player/outline
layers are not invented here.
"""

from __future__ import annotations

import struct
from pathlib import Path


def _runs(indexes: bytes, alpha: bytes, width: int, height: int):
    edges = bytearray()
    commands = bytearray()
    pixels: list[int] = []
    for y in range(height):
        a = alpha[y * width:(y + 1) * width]
        visible = [x for x, value in enumerate(a) if value >= 128]
        if not visible:
            edges.extend(struct.pack("<HH", 0xFFFF, 0xFFFF))
            continue
        left, right = visible[0], visible[-1]
        edges.extend(struct.pack("<HH", left, width - 1 - right))
        x = left
        while x <= right:
            opaque = a[x] >= 128
            end = x + 1
            while end <= right and (a[end] >= 128) == opaque:
                end += 1
            offset = x
            while offset < end:
                count = min(64, end - offset)
                commands.append(((count - 1) << 2) | (1 if opaque else 0))
                if opaque:
                    pixels.extend(indexes[y * width + offset:y * width + offset + count])
                offset += count
            x = end
        commands.append(3)
    return bytes(edges), bytes(commands), pixels


def _pack_10bit(values: list[int]) -> bytes:
    padded = list(values)
    while len(padded) % 4:
        padded.append(0)
    out = bytearray()
    for i in range(0, len(padded), 4):
        a, b, c, d = padded[i:i + 4]
        out.extend((a & 255, b & 255, c & 255, d & 255,
                    ((a >> 8) & 3) | ((b >> 6) & 12) |
                    ((c >> 4) & 48) | ((d >> 2) & 192)))
    return bytes(out)


def encode_frame(image, pillow_palette, hotspot: tuple[int, int], palette_id: int = 28) -> bytes:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    indexed = rgba.convert("RGB").quantize(palette=pillow_palette, dither=0).tobytes()
    alpha = rgba.getchannel("A").tobytes()
    edges, commands, values = _runs(indexed, alpha, width, height)
    pixels = _pack_10bit(values)
    layer_payload = edges + struct.pack("<II", len(commands), len(pixels)) + commands + pixels
    # The size fields are advisory accounting values in SMPX v2. The reader
    # advances from the serialized row and stream lengths below.
    layer_header = struct.pack("<HHhhII", width, height, hotspot[0], hotspot[1],
                               len(layer_payload), len(layer_payload))
    frame_size = 6 + len(layer_header) + len(layer_payload)
    return struct.pack("<BBI", 1, palette_id, frame_size) + layer_header + layer_payload


def write_smx_v2(path: Path, images, pillow_palette, hotspot: tuple[int, int],
                 palette_id: int = 28) -> dict:
    frames = [encode_frame(image, pillow_palette, hotspot, palette_id) for image in images]
    payload = b"".join(frames)
    header = struct.pack("<4sHHIIIIII", b"SMPX", 2, len(frames), len(payload),
                         sum(struct.unpack_from("<I", f, 2)[0] for f in frames),
                         0, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + payload)
    return {"version": 2, "frames": len(frames), "payload_size": len(payload),
            "file_size": path.stat().st_size, "layers": ["main"]}
