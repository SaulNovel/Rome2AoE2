"""Deterministic indexed SLP staging for the official DE SLP-to-SMX encoder."""

from __future__ import annotations

import struct
from pathlib import Path


def read_jasc_palette(path: Path, limit: int = 256):
    lines = path.read_text(encoding="ascii").splitlines()
    if lines[:2] != ["JASC-PAL", "0100"]:
        raise ValueError("unsupported palette")
    colours = [tuple(map(int, line.split()[:3])) for line in lines[3:3 + limit]]
    if len(colours) != limit:
        raise ValueError(f"palette has fewer than {limit} colours")
    return colours


def _command_copy(count: int, indexes: bytes):
    out = bytearray()
    offset = 0
    while count:
        chunk = min(count, 0xFFF)
        if chunk <= 0x3F:
            out.append(chunk << 2)
        else:
            out.extend((0x02 | ((chunk & 0xF00) >> 4), chunk & 0xFF))
        out.extend(indexes[offset:offset + chunk])
        offset += chunk
        count -= chunk
    return out


def _encode_rows(indexes: bytes, alpha: bytes, width: int, height: int):
    edges = bytearray()
    commands = []
    for y in range(height):
        row_alpha = alpha[y * width:(y + 1) * width]
        visible = [x for x, value in enumerate(row_alpha) if value >= 128]
        if not visible:
            edges.extend(struct.pack("<HH", 0x8000, 0x8000))
            commands.append(b"")
            continue
        left, right = min(visible), max(visible)
        edges.extend(struct.pack("<HH", left, width - 1 - right))
        data = bytearray()
        x = left
        while x <= right:
            opaque = row_alpha[x] >= 128
            end = x + 1
            while end <= right and (row_alpha[end] >= 128) == opaque:
                end += 1
            count = end - x
            if opaque:
                data.extend(_command_copy(count, indexes[y * width + x:y * width + end]))
            else:
                remaining = count
                while remaining:
                    chunk = min(remaining, 0xFFF)
                    if chunk <= 0x3F:
                        data.append(0x01 | (chunk << 2))
                    else:
                        data.extend((0x03 | ((chunk & 0xF00) >> 4), chunk & 0xFF))
                    remaining -= chunk
            x = end
        data.append(0x0F)
        commands.append(bytes(data))
    return bytes(edges), commands


def write_slp(path: Path, frames, palette, hotspot=(100, 100)):
    """Write classic 2.0N SLP frames from RGBA Pillow images."""
    count = len(frames)
    header_size = 32 + 32 * count
    frame_headers = bytearray()
    frame_payloads = []
    cursor = header_size
    for image in frames:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        pal = rgba.convert("RGB").quantize(palette=palette, dither=0)
        indexes = pal.tobytes()
        alpha = rgba.getchannel("A").tobytes()
        edges, rows = _encode_rows(indexes, alpha, width, height)
        outline_offset = cursor
        command_table_offset = outline_offset + 4 * height
        command_data_offset = command_table_offset + 4 * height
        offsets = bytearray()
        commands = bytearray()
        for row in rows:
            offsets.extend(struct.pack("<I", command_data_offset + len(commands)))
            commands.extend(row)
        payload = edges + offsets + commands
        frame_headers.extend(struct.pack("<IIIIIIii", command_table_offset, outline_offset, 0, 0,
                                         width, height, hotspot[0], hotspot[1]))
        frame_payloads.append(payload)
        cursor += len(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"2.0N" + struct.pack("<I", count) + b"Rome2AoE2 indexed SMX\0"[:24].ljust(24, b"\0")
                     + bytes(frame_headers) + b"".join(frame_payloads))


def make_pillow_palette(colours):
    from PIL import Image
    palette = Image.new("P", (1, 1))
    palette.putpalette([channel for colour in colours for channel in colour])
    return palette
