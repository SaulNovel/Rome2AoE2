"""Strict SLDX v4 parser and serializer.

Adapted from ``sld.py`` in justinas-kazanavicius/aoe2-transparent-buildings,
commit bce7f2f795483ae1c91afb915cc014a520dc0a30. Copyright (c) 2026
Justinas Kazanavicius, used under the MIT License. See the preserved notice.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import struct

LAYER_MAIN, LAYER_SHADOW, LAYER_UNKNOWN, LAYER_DAMAGE, LAYER_PLAYERCOLOR = 1, 2, 4, 8, 16
LAYER_ORDER = (LAYER_MAIN, LAYER_SHADOW, LAYER_UNKNOWN, LAYER_DAMAGE, LAYER_PLAYERCOLOR)


@dataclass
class SLDLayer:
    layer_type: int
    offset_x1: int = 0
    offset_y1: int = 0
    offset_x2: int = 0
    offset_y2: int = 0
    flag1: int = 0
    unknown1: int = 0
    commands: list[tuple[int, int]] = field(default_factory=list)
    blocks: list[bytes] = field(default_factory=list)
    raw_content: bytes = b""


@dataclass
class SLDFrame:
    canvas_width: int
    canvas_height: int
    center_x: int
    center_y: int
    frame_type: int
    frame_index: int = 0
    unknown: int = 0
    layers: list[SLDLayer] = field(default_factory=list)


@dataclass
class SLDFile:
    frames: list[SLDFrame] = field(default_factory=list)
    facet_count: int = 1
    version: int = 4
    unknown1: int = 0
    header_size_marker: int = 0x10
    flags: int = 0xFF


class _Reader:
    def __init__(self, data: bytes): self.data, self.pos = data, 0
    def take(self, size: int) -> bytes:
        if size < 0 or self.pos + size > len(self.data):
            raise ValueError(f"truncated SLD at byte {self.pos}: need {size} bytes")
        result = self.data[self.pos:self.pos + size]; self.pos += size; return result
    def unpack(self, fmt: str): return struct.unpack(fmt, self.take(struct.calcsize(fmt)))


def _validate(sld: SLDFile) -> None:
    if sld.version != 4: raise ValueError(f"unsupported SLDX version {sld.version}")
    if sld.header_size_marker != 0x10: raise ValueError(f"unsupported SLDX header marker {sld.header_size_marker:#x}")
    if not sld.frames: raise ValueError("SLD must contain at least one frame")
    if sld.facet_count < 1 or len(sld.frames) % sld.facet_count: raise ValueError("frame count is inconsistent with facet count")
    for frame in sld.frames:
        if frame.canvas_width <= 0 or frame.canvas_height <= 0: raise ValueError("invalid frame canvas")
        expected = 0
        previous = -1
        for layer in frame.layers:
            if layer.layer_type not in LAYER_ORDER or layer.layer_type <= previous: raise ValueError("invalid SLD layer order")
            previous = layer.layer_type; expected |= layer.layer_type
            if layer.layer_type != LAYER_UNKNOWN:
                if layer.layer_type in (LAYER_MAIN, LAYER_SHADOW):
                    if not (0 <= layer.offset_x1 <= layer.offset_x2 <= frame.canvas_width and 0 <= layer.offset_y1 <= layer.offset_y2 <= frame.canvas_height):
                        raise ValueError("layer bounds outside canvas")
                    grid = ((layer.offset_x2-layer.offset_x1+3)//4)*((layer.offset_y2-layer.offset_y1+3)//4)
                else:
                    main = next((x for x in frame.layers if x.layer_type == LAYER_MAIN), None)
                    if main is None: raise ValueError("dependent layer requires main layer")
                    grid = ((main.offset_x2-main.offset_x1+3)//4)*((main.offset_y2-main.offset_y1+3)//4)
                cursor = 0
                for skip, draw in layer.commands:
                    if not (0 <= skip <= 255 and 0 <= draw <= 255): raise ValueError("invalid skip/draw command")
                    cursor += skip + draw
                if cursor > grid: raise ValueError("skip/draw commands exceed layer grid")
                if sum(draw for _, draw in layer.commands) != len(layer.blocks): raise ValueError("command/block count mismatch")
                if any(len(block) != 8 for block in layer.blocks): raise ValueError("invalid compressed block length")
        if expected != frame.frame_type: raise ValueError("layer-presence mask disagrees with layers")


def parse_sld(data: bytes) -> SLDFile:
    reader = _Reader(data)
    magic, version, frame_count, unknown1, header_marker, flags = reader.unpack("<4sHHHHI")
    if magic != b"SLDX": raise ValueError(f"invalid SLDX signature {magic!r}")
    if version != 4: raise ValueError(f"unsupported SLDX version {version}")
    # SLD does not serialize the DAT graphic's facet count. DESpriteTool emits
    # 0x0010 here even for a one-frame source; retain and validate that marker.
    sld = SLDFile(facet_count=1, version=version, unknown1=unknown1, header_size_marker=header_marker, flags=flags)
    for _ in range(frame_count):
        width, height, cx, cy, frame_type, unknown, index = reader.unpack("<HHhhBBH")
        frame = SLDFrame(width, height, cx, cy, frame_type, index, unknown)
        for layer_type in LAYER_ORDER:
            if not frame_type & layer_type: continue
            start = reader.pos
            (content_length,) = reader.unpack("<I")
            if content_length < 4: raise ValueError("invalid layer content length")
            end = start + content_length
            layer = SLDLayer(layer_type)
            if layer_type == LAYER_UNKNOWN:
                layer.raw_content = reader.take(content_length - 4)
            else:
                if layer_type in (LAYER_MAIN, LAYER_SHADOW):
                    layer.offset_x1, layer.offset_y1, layer.offset_x2, layer.offset_y2, layer.flag1, layer.unknown1 = reader.unpack("<HHHHBB")
                else:
                    layer.flag1, layer.unknown1 = reader.unpack("<BB")
                (count,) = reader.unpack("<H")
                layer.commands = [reader.unpack("<BB") for _ in range(count)]
                layer.blocks = [reader.take(8) for _ in range(sum(draw for _, draw in layer.commands))]
            if reader.pos != end: raise ValueError(f"layer content length mismatch at byte {start}")
            reader.take((-content_length) % 4)
            frame.layers.append(layer)
        sld.frames.append(frame)
    if reader.pos != len(data): raise ValueError(f"unexpected trailing data at byte {reader.pos}")
    _validate(sld)
    return sld


def serialize_sld(sld: SLDFile) -> bytes:
    _validate(sld)
    output = bytearray(struct.pack("<4sHHHHI", b"SLDX", sld.version, len(sld.frames), sld.unknown1, sld.header_size_marker, sld.flags))
    for frame in sld.frames:
        output += struct.pack("<HHhhBBH", frame.canvas_width, frame.canvas_height, frame.center_x, frame.center_y, frame.frame_type, frame.unknown, frame.frame_index)
        for layer in frame.layers:
            if layer.layer_type == LAYER_UNKNOWN:
                content = layer.raw_content
            else:
                header = (struct.pack("<HHHHBB", layer.offset_x1, layer.offset_y1, layer.offset_x2, layer.offset_y2, layer.flag1, layer.unknown1)
                          if layer.layer_type in (LAYER_MAIN, LAYER_SHADOW) else struct.pack("<BB", layer.flag1, layer.unknown1))
                content = header + struct.pack("<H", len(layer.commands)) + b"".join(struct.pack("<BB", *command) for command in layer.commands) + b"".join(layer.blocks)
            length = len(content) + 4
            output += struct.pack("<I", length) + content + bytes((-length) % 4)
    return bytes(output)
