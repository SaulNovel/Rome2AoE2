"""RESEARCH ONLY: reconstruct a decoded Rome II Action on an assembled Hastati.

This legacy matrix-reconstruction route is not production-authoritative.  It is
retained for diagnostics and regression research only.  Production animation
must use build_hastati_native_animation.py and preserve the Action produced by
Blender's standard import of Asset Editor's animated glTF.
"""

import argparse
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/blender"))

from import_animation_clip import create_action, find_armature


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--animation-json", type=Path, required=True)
    parser.add_argument("--input-blend", type=Path, required=True)
    parser.add_argument("--output-blend", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--scene-fps", type=int, default=20)
    parser.add_argument("--timeline-start", type=float, default=1.0)
    parser.add_argument("--remove-root-motion", action="store_true",
                        help="Center locomotion without rebuilding production attachments")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def main():
    args = arguments()
    animation = json.loads(args.animation_json.read_text(encoding="utf-8-sig"))
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    armature = find_armature()
    before = {
        obj.name: [list(row) for row in obj.matrix_world]
        for obj in bpy.context.scene.objects
        if obj.name.startswith("attachment_")
    }
    action, positions, curves, points = create_action(
        armature, animation, args.scene_fps, args.timeline_start, args.remove_root_motion
    )
    bpy.context.scene.render.fps = args.scene_fps
    bpy.context.scene.frame_start = int(round(positions[0]))
    bpy.context.scene.frame_end = int(round(positions[-1]))
    bpy.context.scene.frame_set(bpy.context.scene.frame_start)
    after = {
        obj.name: [list(row) for row in obj.matrix_world]
        for obj in bpy.context.scene.objects
        if obj.name.startswith("attachment_")
    }
    report = {
        "format": "rome2aoe2.hastati-production-action",
        "version": 1,
        "production_authority": False,
        "status": "obsolete research-only custom Action reconstruction",
        "animation": animation["animation"],
        "source_sample_rate": animation["sample_rate"],
        "source_sample_count": animation["sample_count"],
        "source_duration_seconds": animation["duration"],
        "scene_fps": args.scene_fps,
        "timeline": [positions[0], positions[-1]],
        "action": action.name,
        "fcurve_count": curves,
        "keyframe_point_count": points,
        "attachment_objects_preserved": sorted(before),
        "attachment_object_set_unchanged": sorted(before) == sorted(after),
        "materials_unchanged": True,
        "manual_attachment_corrections": False,
        "root_motion_removed": args.remove_root_motion,
    }
    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
