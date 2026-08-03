"""BC1/BC4 helpers for AoE2 DE SLDX v4 authoring.

Adapted from ``dxt.py`` in justinas-kazanavicius/aoe2-transparent-buildings,
commit bce7f2f795483ae1c91afb915cc014a520dc0a30. Copyright (c) 2026
Justinas Kazanavicius, used under the MIT License. See
``third_party/licenses/aoe2-transparent-buildings-MIT.txt``.
"""

from __future__ import annotations

import struct
from typing import Callable, Sequence

ALPHA_THRESHOLD = 128
BC1Encoder = Callable[[Sequence[Sequence[tuple[int, int, int, int]]], int], bytes]


def rgb565_to_rgb(value: int) -> tuple[int, int, int]:
    return (((value >> 11) & 31) * 255 // 31,
            ((value >> 5) & 63) * 255 // 63,
            (value & 31) * 255 // 31)


def rgb_to_rgb565(r: int, g: int, b: int) -> int:
    return (((r * 31 + 127) // 255) << 11) | (((g * 63 + 127) // 255) << 5) | ((b * 31 + 127) // 255)


def transparent_bc1_block() -> bytes:
    """A valid three-colour-mode BC1 block whose 16 texels use index 3."""
    return struct.pack("<HHI", 0, 0, 0xFFFFFFFF)


def _endpoints(pixels: list[tuple[int, int, int, int]]) -> tuple[int, int]:
    if len(pixels) == 1:
        value = rgb_to_rgb565(*pixels[0][:3])
        return value, value
    ranges = [max(p[c] for p in pixels) - min(p[c] for p in pixels) for c in range(3)]
    axis = max(range(3), key=ranges.__getitem__)
    lo = min(pixels, key=lambda p: p[axis])
    hi = max(pixels, key=lambda p: p[axis])
    return rgb_to_rgb565(*hi[:3]), rgb_to_rgb565(*lo[:3])


def encode_bc1_block(block: Sequence[Sequence[tuple[int, int, int, int]]], alpha_threshold: int = ALPHA_THRESHOLD) -> bytes:
    flat = [pixel for row in block for pixel in row]
    if len(flat) != 16:
        raise ValueError("BC1 input must contain exactly 16 pixels")
    visible = [pixel[3] >= alpha_threshold for pixel in flat]
    opaque = [pixel for pixel, keep in zip(flat, visible) if keep]
    if not opaque:
        return transparent_bc1_block()
    c0, c1 = _endpoints(opaque)
    transparent = not all(visible)
    if transparent:
        if c0 > c1:
            c0, c1 = c1, c0
    else:
        if c0 <= c1:
            if c0 < 0xFFFF:
                c0 += 1
            elif c1 > 0:
                c1 -= 1
    p0, p1 = rgb565_to_rgb(c0), rgb565_to_rgb(c1)
    if transparent:
        palette = [p0, p1, tuple((a + b) // 2 for a, b in zip(p0, p1))]
    else:
        palette = [p0, p1,
                   tuple((2 * a + b + 1) // 3 for a, b in zip(p0, p1)),
                   tuple((a + 2 * b + 1) // 3 for a, b in zip(p0, p1))]
    indices = 0
    for index, pixel in enumerate(flat):
        if not visible[index]:
            best = 3
        else:
            best = min(range(len(palette)), key=lambda candidate: sum((palette[candidate][c] - pixel[c]) ** 2 for c in range(3)))
        indices |= best << (2 * index)
    return struct.pack("<HHI", c0, c1, indices)


def decode_bc1_block(data: bytes) -> list[list[tuple[int, int, int, int]]]:
    if len(data) != 8:
        raise ValueError("BC1 block must be 8 bytes")
    c0, c1, indices = struct.unpack("<HHI", data)
    p0, p1 = rgb565_to_rgb(c0), rgb565_to_rgb(c1)
    palette = [(*p0, 255), (*p1, 255)]
    if c0 > c1:
        palette += [(*tuple((2 * a + b + 1) // 3 for a, b in zip(p0, p1)), 255),
                    (*tuple((a + 2 * b + 1) // 3 for a, b in zip(p0, p1)), 255)]
    else:
        palette += [(*tuple((a + b) // 2 for a, b in zip(p0, p1)), 255), (0, 0, 0, 0)]
    return [[palette[(indices >> (2 * (y * 4 + x))) & 3] for x in range(4)] for y in range(4)]


def encode_bc4_block(block: Sequence[Sequence[int]]) -> bytes:
    flat = [int(value) for row in block for value in row]
    if len(flat) != 16:
        raise ValueError("BC4 input must contain exactly 16 values")
    high, low = max(flat), min(flat)
    if high == low:
        return bytes([high, low, 0, 0, 0, 0, 0, 0])
    palette = [high, low] + [((6 - i) * high + (1 + i) * low + 3) // 7 for i in range(6)]
    indices = [min(range(8), key=lambda i: abs(value - palette[i])) for value in flat]
    bits = sum(index << (3 * position) for position, index in enumerate(indices))
    return bytes([high, low]) + bits.to_bytes(6, "little")


def decode_bc4_block(data: bytes) -> list[list[int]]:
    if len(data) != 8:
        raise ValueError("BC4 block must be 8 bytes")
    high, low = data[0], data[1]
    if high > low:
        palette = [high, low] + [((6 - i) * high + (1 + i) * low + 3) // 7 for i in range(6)]
    else:
        palette = [high, low] + [((4 - i) * high + (1 + i) * low + 2) // 5 for i in range(4)] + [0, 255]
    bits = int.from_bytes(data[2:], "little")
    values = [palette[(bits >> (3 * i)) & 7] for i in range(16)]
    return [values[row * 4:row * 4 + 4] for row in range(4)]
