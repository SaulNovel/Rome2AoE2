"""Read-only attachment validation across frozen native Hastati Actions."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


CASES = {
    "idle": "build/local-integration/hastati-sprite-production-pilot/source/corrected-hastati-sws-stand-frozen.blend",
    "walk": "build/cache/hastati-gameplay-actions/sws_walk_162_cm.native-production.blend",
    "attack": "build/cache/hastati-gameplay-actions/sws_sync_atk_005.native-production.blend",
    "death": "build/cache/hastati-gameplay-actions/sws_cr_death_missile_004.native-production.blend",
}
ROLES = {"gladius": "weapon_02", "scutum": "weapon_03", "shield": "weapon_03",
         "pilum": "weapon_05", "crest": "crest_centre"}


def matrix_rows(matrix):
    return [[round(float(matrix[r][c]), 8) for c in range(4)] for r in range(4)]


def source_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def role_objects(role):
    names = [role] + (["shield"] if role == "scutum" else [])
    return [obj for obj in bpy.data.objects if any(name in obj.name.casefold() for name in names)]


def weighted_points(group_name):
    graph = bpy.context.evaluated_depsgraph_get(); points = []
    for source in (obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.vertex_groups):
        group = source.vertex_groups.get(group_name)
        if group is None: continue
        evaluated = source.evaluated_get(graph); mesh = evaluated.to_mesh()
        indices = {v.index for v in source.data.vertices
                   if any(link.group == group.index and link.weight > .01 for link in v.groups)}
        points.extend(evaluated.matrix_world @ mesh.vertices[index].co for index in indices)
        evaluated.to_mesh_clear()
    return points


def solved_grip_sample(gladius):
    grip = gladius.parent.matrix_world.translation
    hand = weighted_points("bn_righthand"); forearm = weighted_points("bn_rightforearm")
    hand_center = sum(hand, Vector()) / len(hand); forearm_center = sum(forearm, Vector()) / len(forearm)
    outward = (hand_center - forearm_center).normalized()
    vertices = [gladius.matrix_world @ vertex.co for vertex in gladius.data.vertices]
    blade = max(vertices, key=lambda value: (value - grip).length)
    return {"hand_to_grip": min((value - grip).length for value in hand),
            "blade_outward_alignment": (blade - grip).normalized().dot(outward)}


def inspect(path, solved_matrix):
    bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
    scene = bpy.context.scene
    armatures = [obj for obj in scene.objects if obj.type == "ARMATURE"]
    action = next((obj.animation_data.action for obj in armatures
                   if obj.animation_data and obj.animation_data.action), None)
    start, end = (int(action.frame_range[0]), int(action.frame_range[1])) if action else (scene.frame_start, scene.frame_end)
    frames = sorted({start, (start + end) // 2, end})
    gladius_objects = role_objects("gladius")
    for gladius in gladius_objects: gladius.matrix_basis = solved_matrix
    samples = {}
    found = {}
    for role in ("gladius", "scutum", "pilum", "crest"):
        objects = role_objects(role)
        found[role] = [obj.name for obj in objects]
        samples[role] = []
        for frame in frames:
            scene.frame_set(frame); bpy.context.view_layer.update()
            samples[role].append({"frame": frame, "finite": all(math.isfinite(v)
                                  for obj in objects for row in obj.matrix_world for v in row),
                                  "local": {obj.name: matrix_rows(obj.matrix_basis) for obj in objects},
                                  "world_translation": {obj.name: list(obj.matrix_world.translation) for obj in objects}})
    return {"blend": str(path), "action": action.name if action else None,
            "source_blend_digest": source_digest(path),
            "frame_range": [start, end], "sample_frames": frames,
            "objects": found, "samples": samples,
            "generic_solver_validation": [{"frame": frame, **(scene.frame_set(frame) or {}),
                                            **solved_grip_sample(gladius_objects[0])}
                                           for frame in frames],
            "source_action_untouched": True}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    root = Path(__file__).resolve().parents[2]
    static_report = json.loads((root / "build/conversions/rom_principes/bc5d577aadbce8e452d4419c6282e1e0d916900a9038516b321684ead85135c6/static-assembly-report.json").read_text())
    final_rows = next(iter(static_report["attachments"]["melee_weapon"]["grip_solver"]["final_local_transforms"].values()))
    solved_matrix = Matrix(final_rows)
    cases = {name: inspect(root / relative, solved_matrix) for name, relative in CASES.items()}
    held = [sample for name in ("idle", "walk", "attack")
            for sample in cases[name]["generic_solver_validation"]]
    death = cases["death"]["generic_solver_validation"]
    acceptance = {"held_max_hand_to_grip": max(row["hand_to_grip"] for row in held),
                  "held_min_blade_outward_alignment": min(row["blade_outward_alignment"] for row in held),
                  "death_release_observed": max(row["hand_to_grip"] for row in death) > .5}
    acceptance["validated"] = (acceptance["held_max_hand_to_grip"] < .02 and
                               acceptance["held_min_blade_outward_alignment"] > 0 and
                               acceptance["death_release_observed"])
    report = {"format": "rome2aoe2.infantry-attachment-regression", "version": 1,
              "cases": cases, "acceptance": acceptance, "actions_modified": False,
              "death_policy": "follow source weapon carrier; no added hand constraint"}
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__": main()
