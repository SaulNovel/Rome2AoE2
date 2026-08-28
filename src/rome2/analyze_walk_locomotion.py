"""Measure native Rome II walk roots and foot contacts from canonical samples."""

import argparse
import json
import math
from pathlib import Path


SPEEDS = (124, 162, 197, 251, 302)
FEET = ("bn_leftfoot", "bn_rightfoot")


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--decoded-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def translation(frame, name):
    bone = next(item for item in frame["bones"] if item["name"] == name)
    return [bone["world_matrix"][axis][3] for axis in range(3)]


def runs(indices):
    result = []
    for index in indices:
        if not result or index != result[-1][-1] + 1:
            result.append([index])
        else:
            result[-1].append(index)
    return result


def analyze(path, nominal):
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    frames = document["frames"]
    hips = [translation(frame, "bn_hips") for frame in frames]
    displacement = [hips[-1][axis] - hips[0][axis] for axis in range(3)]
    forward = displacement[2]
    horizontal = math.hypot(displacement[0], displacement[2])
    report = {
        "clip": document["animation"], "frame_count": document["sample_count"],
        "source_fps": document["sample_rate"], "cycle_duration_seconds": document["duration"],
        "authored_root_displacement": displacement,
        "authored_forward_displacement_m": forward,
        "authored_horizontal_displacement_m": horizontal,
        "measured_speed_mps": horizontal / document["duration"],
        "filename_nominal_speed_cmps": nominal,
        "root_vertical_range_m": max(point[1] for point in hips) - min(point[1] for point in hips),
        "root_removal_semantics": {
            "subtracted_from": "world translation of every sampled bone",
            "horizontal_delta": "bn_hips X/Z relative to first sample",
            "vertical_y_preserved": True,
            "rotations_modified": False,
        },
        "feet": {},
    }
    for foot in FEET:
        points = [translation(frame, foot) for frame in frames]
        minimum_height = min(point[1] for point in points)
        def forward_step(index):
            values = []
            if index:
                values.append(abs(points[index][2] - points[index - 1][2]))
            if index + 1 < len(points):
                values.append(abs(points[index + 1][2] - points[index][2]))
            return min(values)
        contact_indices = [index for index, point in enumerate(points)
                           if point[1] <= minimum_height + 0.04
                           and forward_step(index) <= 0.015]
        contacts = []
        for run in runs(contact_indices):
            if len(run) < 2:
                continue
            source_forward = [points[index][2] for index in run]
            centered_forward = [points[index][2] - (hips[index][2] - hips[0][2]) for index in run]
            contacts.append({
                "sample_indices": [run[0], run[-1]],
                "phase_range": [run[0] / (len(frames) - 1), run[-1] / (len(frames) - 1)],
                "source_world_forward_range_m": max(source_forward) - min(source_forward),
                "source_world_forward_net_m": source_forward[-1] - source_forward[0],
                "centered_forward_range_m": max(centered_forward) - min(centered_forward),
                "centered_forward_net_m": centered_forward[-1] - centered_forward[0],
                "height_range_m": max(points[index][1] for index in run) - min(points[index][1] for index in run),
            })
        report["feet"][foot] = {"minimum_height_m": minimum_height,
                                  "contact_height_threshold_m": minimum_height + 0.04,
                                  "contact_max_forward_step_m": 0.015,
                                  "apparent_contacts": contacts}
    report["stride_length_m"] = horizontal
    return report


def main():
    args = arguments()
    clips = [analyze(args.decoded_root / f"sws_walk_{speed}_cm.json", speed)
             for speed in SPEEDS]
    output = {"format": "rome2aoe2.walk-locomotion-analysis", "version": 1,
              "coordinate_system": "Rome source: Y vertical, Z forward", "clips": clips}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(clips, indent=2))


if __name__ == "__main__":
    main()
