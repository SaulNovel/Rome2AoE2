"""Compare production rigid attachment-local transforms between two Actions."""

import argparse
import json
import sys
from pathlib import Path

import bpy


KEYS = ("weapon_02", "weapon_03", "weapon_05", "crest_centre")


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--idle-blend", type=Path, required=True)
    parser.add_argument("--walk-blend", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def rows(matrix):
    return [[float(matrix[row][column]) for column in range(4)] for row in range(4)]


def snapshot(path):
    bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
    result = {}
    for key in KEYS:
        wrapper = bpy.data.objects.get(f"attachment__{key}") or bpy.data.objects.get(f"attachment_{key}")
        if wrapper is None:
            result[key] = {"present": False}
            continue
        constraints = [item for item in wrapper.constraints if item.type == "CHILD_OF"]
        result[key] = {
            "present": True,
            "wrapper": wrapper.name,
            "carrier": constraints[0].subtarget if len(constraints) == 1 else None,
            "wrapper_local": rows(wrapper.matrix_basis),
            "rigid_children": {child.name: rows(child.matrix_basis) for child in wrapper.children},
        }
    return result


def delta(left, right):
    return max(abs(left[row][column] - right[row][column]) for row in range(4) for column in range(4))


def main():
    args = arguments()
    idle = snapshot(args.idle_blend)
    walk = snapshot(args.walk_blend)
    comparisons = {}
    for key in KEYS:
        left, right = idle[key], walk[key]
        row = {"present_in_both": left["present"] and right["present"]}
        if row["present_in_both"]:
            row["carrier_idle"] = left["carrier"]
            row["carrier_walk"] = right["carrier"]
            row["wrapper_local_max_delta"] = delta(left["wrapper_local"], right["wrapper_local"])
            left_children = list(left["rigid_children"].values())
            right_children = list(right["rigid_children"].values())
            row["rigid_child_local_max_delta"] = (
                delta(left_children[0], right_children[0])
                if len(left_children) == len(right_children) == 1 else None
            )
        comparisons[key] = row
    document = {"format": "rome2aoe2.attachment-action-invariance", "version": 1,
                "idle_blend": str(args.idle_blend), "walk_blend": str(args.walk_blend),
                "idle": idle, "walk": walk, "comparison": comparisons}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(comparisons, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
