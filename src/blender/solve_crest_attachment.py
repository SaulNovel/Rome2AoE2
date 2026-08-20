"""Apply the generic asset-pair crest contact solver to a production blend."""

import argparse
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crest_attachment import mesh_for_asset, seat_crest


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", type=Path, required=True)
    parser.add_argument("--output-blend", type=Path, required=True)
    parser.add_argument("--helmet-asset", type=Path, required=True)
    parser.add_argument("--crest-asset", type=Path, required=True)
    parser.add_argument("--socket", default="crest_centre")
    parser.add_argument("--reference-frame", type=int, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def unique(kind, token):
    matches = [obj for obj in bpy.context.scene.objects
               if obj.type == kind and token in obj.name.lower()]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {kind} matching {token}, found {len(matches)}")
    return matches[0]


def main():
    args = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    wrapper = (bpy.data.objects.get(f"attachment__{args.socket}")
               or bpy.data.objects.get(f"attachment_{args.socket}"))
    if wrapper is None:
        raise RuntimeError(f"attachment wrapper for {args.socket} is missing")
    report = seat_crest(
        unique("ARMATURE", "rome_man_game"),
        mesh_for_asset(args.helmet_asset, "helmet"),
        mesh_for_asset(args.crest_asset, "crest"), wrapper, args.reference_frame,
        args.helmet_asset, args.crest_asset, args.socket,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
