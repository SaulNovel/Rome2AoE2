"""Run inside Blender: one 400x400 Principes diagnostic frame from fixtures."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument("--fixture-root",type=Path,required=True);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    blend=args.fixture_root/"_prepared/principes/static-unit.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend.resolve()))
    by_name={}
    for path in args.fixture_root.rglob("*"):
        if path.is_file(): by_name.setdefault(path.name.casefold(),[]).append(path)
    missing=[]
    for image in bpy.data.images:
        if image.source != 'FILE': continue
        candidates=by_name.get(Path(image.filepath).name.casefold(),[])
        if len(candidates)==1: image.filepath=str(candidates[0].resolve())
        try: image.reload()
        except RuntimeError: missing.append(image.name)
    if missing: raise RuntimeError(f"unresolved fixture images: {missing}")
    scene=bpy.context.scene;scene.render.engine="BLENDER_EEVEE";scene.render.resolution_x=400;scene.render.resolution_y=400;scene.render.resolution_percentage=100
    scene.render.film_transparent=True;scene.render.image_settings.file_format="PNG";scene.render.image_settings.color_mode="RGBA"
    args.output.parent.mkdir(parents=True,exist_ok=True);scene.render.filepath=str(args.output.resolve());bpy.ops.render.render(write_still=True)
    print(json.dumps({"status":"PASS","output":str(args.output),"objects":len(bpy.data.objects),"images":len(bpy.data.images)}))
if __name__=="__main__":main()
