"""Pure helpers shared by the AoE2 DE Blender render calibration harness."""

import json
import math
from pathlib import Path


SUPPORTED_ENGINES = {"BLENDER_EEVEE", "CYCLES"}
SUPPORTED_DOWNSAMPLE_FILTERS = {"bicubic", "lanczos3"}
REQUIRED_SECTIONS = {
    "camera", "target", "lighting", "render", "directions", "canvas", "sampling"
}


def load_profile(path):
    profile = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if profile.get("format") != "rome2aoe2.render-profile" or profile.get("version") not in (1, 2, 3):
        raise ValueError("unsupported render profile format/version")
    missing = sorted(REQUIRED_SECTIONS - profile.keys())
    if missing:
        raise ValueError("missing render profile sections: " + ", ".join(missing))
    if profile["camera"].get("projection") != "orthographic":
        raise ValueError("only orthographic calibration profiles are supported")
    if profile["render"].get("engine") not in SUPPORTED_ENGINES:
        raise ValueError("unsupported render engine")
    count = profile["directions"].get("count")
    order = profile["directions"].get("order", [])
    if not isinstance(count, int) or count <= 0 or len(order) != count or len(set(order)) != count:
        raise ValueError("direction count/order must contain unique matching entries")
    if profile["sampling"].get("mode") != "source_samples":
        raise ValueError("calibration requires source_samples sampling")
    for key in ("width", "height"):
        if profile["render"].get(key, 0) <= 0:
            raise ValueError(f"render.{key} must be positive")
    scale = profile["render"].get("internal_render_scale", 1)
    if not isinstance(scale, int) or scale not in (1, 2, 4):
        raise ValueError("render.internal_render_scale must be 1, 2, or 4")
    method = profile["render"].get("downsample_method", "bicubic")
    if method not in SUPPORTED_DOWNSAMPLE_FILTERS:
        raise ValueError("unsupported downsample method")
    if profile.get("version") == 2 and profile.get("status") not in {"calibrated", "provisional"}:
        raise ValueError("version 2 profile requires calibrated or provisional status")
    if profile.get("version") == 3 and profile.get("status") != "in_game_visual_candidate":
        raise ValueError("version 3 profile requires in_game_visual_candidate status")
    return profile


def direction_angles(profile):
    count = profile["directions"]["count"]
    start = float(profile["camera"]["azimuth_degrees"])
    sign = -1.0 if profile["directions"].get("clockwise", True) else 1.0
    return [((start + sign * index * 360.0 / count) % 360.0) for index in range(count)]


def camera_location(azimuth_degrees, elevation_degrees, distance, target=(0.0, 0.0, 0.0)):
    azimuth = math.radians(azimuth_degrees)
    elevation = math.radians(elevation_degrees)
    horizontal = distance * math.cos(elevation)
    return (
        target[0] + horizontal * math.cos(azimuth),
        target[1] + horizontal * math.sin(azimuth),
        target[2] + distance * math.sin(elevation),
    )


def sample_blender_frame(source_sample, source_sample_rate, scene_fps, timeline_start=1.0):
    if source_sample < 0 or source_sample_rate <= 0 or scene_fps <= 0:
        raise ValueError("sample, source rate and scene FPS must be valid")
    return timeline_start + source_sample * scene_fps / source_sample_rate


def output_filename(animation, sample, direction_index, kind="color"):
    stem = Path(animation).stem
    return f"{stem}-sample-{sample:04d}-direction-{direction_index:02d}-{kind}.png"


def alpha_bounds(width, height, alpha_values, threshold=1.0 / 255.0):
    points = [(i % width, height - 1 - i // width) for i, a in enumerate(alpha_values) if a > threshold]
    if not points:
        return None
    xs, ys = zip(*points)
    return [min(xs), min(ys), max(xs) + 1, max(ys) + 1]


def stable_canvas(profile):
    return {
        "width": profile["render"]["width"],
        "height": profile["render"]["height"],
        "anchor_pixels": list(profile["canvas"]["anchor_pixels"]),
        "policy": profile["canvas"]["policy"],
    }


def internal_dimensions(profile):
    scale = profile["render"].get("internal_render_scale", 1)
    return profile["render"]["width"] * scale, profile["render"]["height"] * scale


def scaled_anchor(profile):
    scale = profile["render"].get("internal_render_scale", 1)
    return [value * scale for value in profile["canvas"]["anchor_pixels"]]


def shadow_filename(animation, sample, direction_index):
    return output_filename(animation, sample, direction_index, "shadow")


def representative_frames():
    return [
        {"animation": "sws_stand", "source_sample": 0, "purpose": "stand_start"},
        {"animation": "sws_stand", "source_sample": 21, "purpose": "stand_middle"},
        {"animation": "sws_combat_ready", "source_sample": 22, "purpose": "combat_ready"},
        {"animation": "sws_charge_javelin_throw_001", "source_sample": 30, "purpose": "pilum_throw"},
    ]


def deterministic_json(document):
    return json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n"
