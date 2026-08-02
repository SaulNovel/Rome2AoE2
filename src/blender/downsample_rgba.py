"""Deterministic alpha-correct RGBA downsampling used by Blender renders."""

import math


def _cubic(x):
    x = abs(x)
    if x < 1.0:
        return 1.5 * x**3 - 2.5 * x**2 + 1.0
    if x < 2.0:
        return -0.5 * x**3 + 2.5 * x**2 - 4.0 * x + 2.0
    return 0.0


def _sinc(x):
    return 1.0 if x == 0.0 else math.sin(math.pi * x) / (math.pi * x)


def _lanczos3(x):
    x = abs(x)
    return _sinc(x) * _sinc(x / 3.0) if x < 3.0 else 0.0


def _contributions(source_size, target_size, method):
    scale = source_size / target_size
    kernel = _cubic if method == "bicubic" else _lanczos3
    radius = (2.0 if method == "bicubic" else 3.0) * max(1.0, scale)
    rows = []
    for destination in range(target_size):
        center = (destination + 0.5) * scale - 0.5
        first = math.ceil(center - radius)
        last = math.floor(center + radius)
        values = []
        total = 0.0
        for source in range(first, last + 1):
            clamped = min(source_size - 1, max(0, source))
            weight = kernel((center - source) / max(1.0, scale))
            if weight:
                values.append((clamped, weight))
                total += weight
        rows.append([(index, weight / total) for index, weight in values])
    return rows


def downsample_rgba(pixels, source_width, source_height, target_width, target_height, method):
    if method not in {"bicubic", "lanczos3"}:
        raise ValueError("unsupported downsample method")
    if source_width % target_width or source_height % target_height:
        raise ValueError("source dimensions must be integer multiples of target dimensions")
    if len(pixels) != source_width * source_height * 4:
        raise ValueError("RGBA pixel count does not match source dimensions")
    x_rows = _contributions(source_width, target_width, method)
    y_rows = _contributions(source_height, target_height, method)
    horizontal = [0.0] * (target_width * source_height * 4)
    for y in range(source_height):
        for x, samples in enumerate(x_rows):
            rgba = [0.0, 0.0, 0.0, 0.0]
            for source_x, weight in samples:
                offset = (y * source_width + source_x) * 4
                alpha = pixels[offset + 3]
                rgba[0] += pixels[offset] * alpha * weight
                rgba[1] += pixels[offset + 1] * alpha * weight
                rgba[2] += pixels[offset + 2] * alpha * weight
                rgba[3] += alpha * weight
            offset = (y * target_width + x) * 4
            horizontal[offset:offset + 4] = rgba
    result = [0.0] * (target_width * target_height * 4)
    for y, samples in enumerate(y_rows):
        for x in range(target_width):
            rgba = [0.0, 0.0, 0.0, 0.0]
            for source_y, weight in samples:
                offset = (source_y * target_width + x) * 4
                for channel in range(4):
                    rgba[channel] += horizontal[offset + channel] * weight
            alpha = min(1.0, max(0.0, rgba[3]))
            offset = (y * target_width + x) * 4
            if alpha > 1e-8:
                result[offset:offset + 3] = [min(1.0, max(0.0, value / alpha)) for value in rgba[:3]]
            result[offset + 3] = alpha
    return result
