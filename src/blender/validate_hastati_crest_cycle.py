"""Validate the production Hastati crest over the complete current action."""

import argparse
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crest_attachment import validate_crest_cycle


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--expected-frames", type=int)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def one(kind, token):
    matches = [obj for obj in bpy.context.scene.objects
               if obj.type == kind and token in obj.name.lower()]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {kind} matching {token}, found {len(matches)}")
    return matches[0]


def main():
    args = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(args.blend.resolve()))
    scene = bpy.context.scene
    armature = one("ARMATURE", "rome_man_game")
    helmet = one("MESH", "montefortino")
    crest = one("MESH", "feather")
    wrapper = bpy.data.objects.get("attachment__crest_centre") or bpy.data.objects.get("attachment_crest_centre")
    if wrapper is None:
        raise RuntimeError("crest attachment wrapper is missing")
    frames = range(scene.frame_start, scene.frame_end + 1)
    report = validate_crest_cycle(armature, helmet, crest, wrapper, frames)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.expected_frames is not None and report["frame_count"] != args.expected_frames:
        raise RuntimeError(
            f"expected {args.expected_frames} animation frames, found {report['frame_count']}"
        )
    if not report["all_transforms_finite"] or report["penetration_detected"]:
        raise RuntimeError("crest cycle validation failed")
    print(json.dumps({key: value for key, value in report.items() if key != "frames"}))


if __name__ == "__main__":
    main()
