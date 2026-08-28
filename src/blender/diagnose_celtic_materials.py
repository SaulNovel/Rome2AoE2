"""Trace and render Celtic Warrior material IDs/texture wiring diagnostics."""
import colorsys,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration";OUT=BASE/"celtic-forensics";UNIT=BASE/"units"/"celtic-warriors"
sys.path.insert(0,str(ROOT/"src"/"blender"));from render_cross_unit_set_a import import_unit,beauty_materials,configure_camera,setup_render  # noqa:E402
STATUS={"connected":(0.02,0.8,0.08,1),"suspicious":(1,0.7,0.02,1),"missing":(1,0.02,0.02,1),"sentinel":(0.02,0.85,0.9,1),"unsupported":(1,0,1,1)}
SUSPICIOUS={"celtic_oval_shield_a_lod1":"VMD decal texture-array reference is not applied by Set A material builder"}
UNSUPPORTED={"celtic_cloak_a":"neutral diffuse plus authored mask requires runtime tint interpretation","celtic_checker_trousers":"neutral diffuse plus authored mask requires runtime tint interpretation"}
def emission(mat,color):
 mat.use_nodes=True;n=mat.node_tree.nodes;n.clear();o=n.new("ShaderNodeOutputMaterial");e=n.new("ShaderNodeEmission");e.inputs["Color"].default_value=color;e.inputs["Strength"].default_value=1;mat.node_tree.links.new(e.outputs["Emission"],o.inputs["Surface"])
def main():
 OUT.mkdir(parents=True,exist_ok=True);root,_=import_unit("celtic-warriors");configure_camera(bpy.context.scene,45,30,8.5,12);beauty_materials(root);manifest=json.loads((UNIT/"texture-manifest.json").read_text());spec={m["material_name"]:m for m in manifest["materials"]};rows=[];mats=list(bpy.data.materials)
 valid=set(spec)
 for obj in bpy.data.objects:
  if obj.type=="MESH" and not any(slot.material and slot.material.name.split(".")[0] in valid for slot in obj.material_slots):obj.hide_render=True
 for idx,mat in enumerate(mats):
  key=mat.name.split(".")[0];s=spec.get(key,{});textures=s.get("textures",[]);diff=next((t for t in textures if t["semantic"]=="Diffuse"),None);nodes=[n for n in mat.node_tree.nodes if n.bl_idname=="ShaderNodeTexImage"] if mat.node_tree else [];dn=next((n for n in nodes if n.label=="diffuse"),None);meshes=[o for o in bpy.data.objects if o.type=="MESH" and any(slot.material==mat for slot in o.material_slots)];uv=[]
  for obj in meshes:
   layer=obj.data.uv_layers.active
   if layer:uv.extend((v.uv.x,v.uv.y) for v in layer.data)
  status="missing" if not diff or diff["status"]!="resolved" else "connected"
  if key in SUSPICIOUS:status="suspicious"
  if key in UNSUPPORTED:status="unsupported"
  sent=[t for t in textures if t["status"]!="resolved" and Path(t["source_path"]).name.lower() in ("test_mask.dds","test_black.dds")]
  row={"material":key,"blender_material":mat.name,"material_type":s.get("material_type"),"source_models":s.get("source_models",[]),"textures":textures,"mesh_objects":[o.name for o in meshes],"uv_map_exists":bool(uv),"uv_range":{"min":[min(x for x,y in uv),min(y for x,y in uv)],"max":[max(x for x,y in uv),max(y for x,y in uv)]} if uv else None,"diffuse_node_created":dn is not None,"diffuse_image":dn.image.filepath if dn and dn.image else None,"diffuse_colorspace":dn.image.colorspace_settings.name if dn and dn.image else None,"diffuse_connected_to_base_color":bool(dn and any(l.from_node==dn and l.to_socket.name=="Base Color" for l in mat.node_tree.links)),"alpha_connected":bool(dn and any(l.from_node==dn and l.to_socket.name=="Alpha" for l in mat.node_tree.links)),"sentinel_defaults":[Path(t["source_path"]).name for t in sent],"status":status,"status_reason":SUSPICIOUS.get(key) or UNSUPPORTED.get(key)};rows.append(row)
 # Material-ID render.
 for idx,mat in enumerate(mats):
  rgb=colorsys.hsv_to_rgb((idx*.61803398875)%1,.78,1);emission(mat,(*rgb,1))
 setup_render(OUT/"celtic-material-id.png")
 # Status render.
 for mat,row in zip(mats,rows):emission(mat,STATUS[row["status"]])
 setup_render(OUT/"celtic-texture-status.png")
 (OUT/"celtic-material-trace.json").write_text(json.dumps({"format":"rome2aoe2.celtic-material-trace","version":1,"status_colors":STATUS,"materials":rows},indent=2,sort_keys=True)+"\n");print(json.dumps(rows,indent=2))
if __name__=="__main__":main()
