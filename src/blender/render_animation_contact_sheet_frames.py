"""Render nine inexpensive samples from a native-action preview scene."""
import argparse
import json
import shutil
import sys
from pathlib import Path

import bpy
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/blender"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exact-input", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 384
    scene.render.resolution_y = 384
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = True
    args.output.mkdir(parents=True, exist_ok=True)
    if args.exact_input:
        exact_document = json.loads(args.exact_input.read_text(encoding="utf-8"))
        shutil.copyfile(exact_document["texture_manifest"], args.output / "texture-manifest.json")
    samples = []
    for index in range(9):
        frame = scene.frame_start + (scene.frame_end - scene.frame_start) * index / 8.0
        whole = int(frame)
        scene.frame_set(whole, subframe=frame - whole)
        target = args.output / f"sample-{index}.png"
        if args.exact_input:
            import assemble_manifest_static as assembly
            assembly.exact_render(scene, exact_document, args.output, target.name, 384)
        else:
            scene.render.filepath = str(target.resolve())
            bpy.ops.render.render(write_still=True)
        samples.append({"index": index, "phase": index / 8.0, "frame": frame, "path": str(target)})
    (args.output / "samples.json").write_text(json.dumps(samples, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
