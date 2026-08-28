"""Audit per-object evaluated bounds for a production animation blend."""

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    bpy.ops.wm.open_mainfile(filepath=str(args.blend.resolve()))
    scene = bpy.context.scene
    records = []
    for frame in sorted({scene.frame_start, (scene.frame_start + scene.frame_end) // 2, scene.frame_end}):
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for obj in scene.objects:
            if obj.type != "MESH":
                continue
            evaluated = obj.evaluated_get(depsgraph)
            points = [evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box]
            records.append({"frame": frame, "object": obj.name,
                            "min": [min(point[i] for point in points) for i in range(3)],
                            "max": [max(point[i] for point in points) for i in range(3)]})
    report = {"format": "rome2aoe2.hastati-animation-scene-audit", "version": 1,
              "blend": str(args.blend), "records": records}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
