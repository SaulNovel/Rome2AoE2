"""Create a diagnostic Blender scene displaying one preserved faction-mask channel."""
import argparse, sys
from pathlib import Path
import bpy

def arguments():
    p=argparse.ArgumentParser(); p.add_argument("--input",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--channel",choices=("r","g","b"),required=True)
    return p.parse_args(sys.argv[sys.argv.index("--")+1:])

def main():
    args=arguments(); bpy.ops.wm.open_mainfile(filepath=str(args.input.resolve())); output_index={"r":0,"g":1,"b":2}[args.channel]
    for material in bpy.data.materials:
        if not material.use_nodes: continue
        nodes=material.node_tree.nodes; links=material.node_tree.links
        principled=next((n for n in nodes if n.bl_idname=="ShaderNodeBsdfPrincipled"),None)
        if principled is None: continue
        if "Metallic" in principled.inputs: principled.inputs["Metallic"].default_value=0.0
        principled.inputs["Roughness"].default_value=1.0
        separator=nodes.get("rome2_mask_channels")
        base=principled.inputs["Base Color"]
        for link in list(base.links): links.remove(link)
        if separator is None: base.default_value=(0,0,0,1)
        else: links.new(separator.outputs[output_index],base)
    args.output.parent.mkdir(parents=True,exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
if __name__=="__main__": main()
