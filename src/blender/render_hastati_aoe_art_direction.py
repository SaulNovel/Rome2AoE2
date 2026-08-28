"""Focused fixed-composition/fixed-R133 AoE render-art-direction study."""
import json,math,shutil,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"src/blender"))
import render_cross_unit_set_a as cu
from render_material_reconstruction_v1 import reconstruct
from render_lighting_sweep import clear_lights,set_world,add_sun,add_area,area,CANDIDATES
OUT=ROOT/"build/local-integration/rome2/aoe-render-art-direction/masters";EFFECTIVE=ROOT/"build/local-integration/rome2/runtime-resolution/effective/hastati/effective-unit.json"
BRONZE={"italian_square_muscled_cuirass_","roman_montefortino"};CLOTH={"E3_tunic","E3_tunic_flipped"}
LR={
 "LR0":{"name":"Current L11 control","base":"L11","areas":[]},
 "LR1":{"name":"Neutral soft multi-light studio","world":{"mode":"neutral","strength":.42,"color":[.82,.83,.84]},"sun":{"strength":.45,"azimuth":140,"elevation":62,"angular_size":28},"areas":[area("broad_key",(6,2,7),820,6.5),area("broad_fill",(3,7,5),500,7),area("restrained_rim",(-4,-3,6),120,4,(1,.86,.7))]},
 "LR2":{"name":"LR1 stronger frontal upper fill","parent":"LR1","extra":[area("upper_fill",(5,6,8),230,7)]},
 "LR3":{"name":"LR1 bronze readability pass","parent":"LR1","bronze_fill":.025},
 "LR4":{"name":"LR1 cloth fill","parent":"LR1","cloth_fill":.028,"cloth_warm":False},
 "LR5":{"name":"LR1 bronze and cloth contributions","parent":"LR1","bronze_fill":.025,"cloth_fill":.028,"cloth_warm":True},
 "LR6":{"name":"Sprite studio upper bound","world":{"mode":"neutral","strength":.55,"color":[.82,.83,.84]},"sun":{"strength":.35,"azimuth":140,"elevation":62,"angular_size":30},"areas":[area("broad_key",(6,2,8),1050,7),area("front_upper",(4,7,7),760,8),area("side_fill",(-2,6,5),310,6),area("rim",(-4,-4,7),150,4,(1,.84,.66))]}}
BR={"BR0":{"name":"Current bronze","factor":(1,1,1),"roughness":None,"fill":0},"BR1":{"name":"Darker conductor","factor":(.70,.58,.46),"roughness":None,"fill":0},"BR2":{"name":"Darker broader highlight","factor":(.68,.56,.43),"roughness":.60,"fill":0},"BR3":{"name":"Darker plus warm readability","factor":(.70,.58,.44),"roughness":.56,"fill":.025},"BR4":{"name":"Restrained AoE bronze","factor":(.62,.48,.34),"roughness":.62,"fill":.018}}
CL={"CL0":{"name":"Current cloth","fill":0,"warm":False,"roughness":None},"CL1":{"name":"Weak neutral cloth fill","fill":.022,"warm":False,"roughness":None},"CL2":{"name":"Weak warm cloth fill","fill":.032,"warm":True,"roughness":None},"CL3":{"name":"Warm fill and cloth roughness","fill":.032,"warm":True,"roughness":.72}}
FINALS={"F0":{"cm":"Standard","lr":"LR0","br":"BR0","cl":"CL0","finish":"none"},"F1":{"cm":"Khronos PBR Neutral","lr":"LR0","br":"BR0","cl":"CL0","finish":"none"},"F2":{"cm":"Standard","lr":"LR1","br":"BR0","cl":"CL0","finish":"none"},"F3":{"cm":"Standard","lr":"LR1","br":"BR4","cl":"CL0","finish":"none"},"F4":{"cm":"Standard","lr":"LR1","br":"BR0","cl":"CL2","finish":"none"},"F5":{"cm":"Standard","lr":"LR1","br":"BR4","cl":"CL2","finish":"none"},"F6":{"cm":"Standard","lr":"LR1","br":"BR4","cl":"CL2","finish":"mild known-safe luminance unsharp"},"F7":{"cm":"Standard","lr":"LR6","br":"BR4","cl":"CL2","finish":"none"}}
def linear(h):
 def f(v):v/=255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
 return tuple(f(int(h[i:i+2],16)) for i in (0,2,4))
def bsdf(mat):return next((n for n in mat.node_tree.nodes if n.bl_idname=="ShaderNodeBsdfPrincipled"),None)
def multiply_base(mat,factor):
 b=bsdf(mat);sock=b.inputs["Base Color"];links=mat.node_tree.links;src=sock.links[0].from_socket if sock.is_linked else None
 mix=mat.node_tree.nodes.new("ShaderNodeMixRGB");mix.blend_type="MULTIPLY";mix.inputs[0].default_value=1;mix.inputs[2].default_value=(*factor,1)
 if src:links.remove(sock.links[0]);links.new(src,mix.inputs[1])
 else:mix.inputs[1].default_value=sock.default_value
 links.new(mix.outputs["Color"],sock)
def emission_fill(mat,strength,warm=False):
 if not strength:return
 b=bsdf(mat);base=b.inputs["Base Color"];src=base.links[0].from_socket if base.is_linked else None;ec=b.inputs.get("Emission Color");es=b.inputs.get("Emission Strength")
 if not ec or not es:return
 if src:
  if warm:
   mix=mat.node_tree.nodes.new("ShaderNodeMixRGB");mix.blend_type="MULTIPLY";mix.inputs[0].default_value=1;mix.inputs[2].default_value=(1,.78,.66,1);mat.node_tree.links.new(src,mix.inputs[1]);src=mix.outputs["Color"]
  mat.node_tree.links.new(src,ec)
 else:ec.default_value=(.25,.02,.008,1) if warm else base.default_value
 es.default_value=strength
def materials(br,cl,extra_bronze=0,extra_cloth=0,extra_warm=False):
 for mat in bpy.data.materials:
  key=mat.name.split(".")[0];b=bsdf(mat)
  if not b:continue
  if key in BRONZE:
   multiply_base(mat,br["factor"])
   if br["roughness"] is not None:
    sock=b.inputs["Roughness"]
    if sock.is_linked:mat.node_tree.links.remove(sock.links[0])
    sock.default_value=br["roughness"]
   emission_fill(mat,br["fill"]+extra_bronze,True)
  if key in CLOTH:
   if cl["roughness"] is not None:
    sock=b.inputs["Roughness"]
    if sock.is_linked:mat.node_tree.links.remove(sock.links[0])
    sock.default_value=cl["roughness"]
   emission_fill(mat,cl["fill"]+extra_cloth,cl["warm"] or extra_warm)
def rig(name):
 d=LR[name]
 if "parent" in d:base=dict(LR[d["parent"]]);areas=list(base["areas"])+list(d.get("extra",[]));base["areas"]=areas;d={**base,**d}
 if d.get("base")=="L11":cu.lighting("L11");return d
 s=bpy.context.scene;clear_lights(s);set_world(s,d["world"]);add_sun(s,d["sun"])
 for a in d["areas"]:add_area(s,a)
 return d
def render(cid,cm,lr,br,cl):
 bpy.ops.wm.read_factory_settings(use_empty=True);root,_=cu.import_unit("hastati");cu.configure_camera(bpy.context.scene,45,30,8.5,12);reconstruct(root,COLORS,True);rd=rig(lr);materials(BR[br],CL[cl],rd.get("bronze_fill",0),rd.get("cloth_fill",0),rd.get("cloth_warm",False))
 s=bpy.context.scene;s.render.engine="BLENDER_EEVEE";s.render.resolution_x=s.render.resolution_y=3200;s.render.resolution_percentage=100;s.render.film_transparent=True;s.render.image_settings.file_format="PNG";s.render.image_settings.color_mode="RGBA";s.render.image_settings.color_depth="8";s.display_settings.display_device="sRGB";s.view_settings.view_transform=cm;s.view_settings.look="None";s.view_settings.exposure=.65;s.view_settings.gamma=1;s.render.filepath=str((OUT/f"{cid}.png").resolve());bpy.ops.render.render(write_still=True);print("rendered",cid,flush=True)
def main():
 global COLORS;OUT.mkdir(parents=True,exist_ok=True);m=json.loads(EFFECTIVE.read_text());COLORS=tuple(linear(m["faction_colours"][x]) for x in ("C0","C1","C2"));available=[]
 for name in ("Standard","Khronos PBR Neutral","AgX"):
  try:bpy.context.scene.view_settings.view_transform=name;available.append(name)
  except TypeError:pass
 if "Khronos PBR Neutral" not in available:raise RuntimeError(f"required transform unavailable: {available}")
 jobs={"CM1":("Standard","LR0","BR0","CL0"),"CM2":("Standard","LR0","BR0","CL0"),"CM3":("Khronos PBR Neutral","LR0","BR0","CL0"),"CM4":("AgX","LR0","BR0","CL0")}
 jobs.update({k:("Standard",k,"BR0","CL0") for k in LR});jobs.update({k:("Standard","LR1",k,"CL0") for k in BR});jobs.update({k:("Standard","LR1","BR0",k) for k in CL});jobs.update({k:(v["cm"],v["lr"],v["br"],v["cl"]) for k,v in FINALS.items()})
 rendered={}
 for cid,spec in jobs.items():
  if spec in rendered:shutil.copy2(OUT/f"{rendered[spec]}.png",OUT/f"{cid}.png");continue
  render(cid,*spec);rendered[spec]=cid
 report={"format":"rome2aoe2.aoe-render-art-direction-blender","version":1,"blender_version":bpy.app.version_string,"engine":"BLENDER_EEVEE_NEXT","color_management":{"current_actual_master_script":"src/blender/render_hastati_finish_inputs.py","current_engine":"BLENDER_EEVEE","display_device":"sRGB","view_transform":"Standard","look":"None","exposure":.65,"gamma":1,"output":"PNG RGBA 8-bit; Blender applies display/view transform before encoding","supported_tested":available},"fixed":{"composition":"unchanged runtime-resolved Hastati","pose_frame":1,"camera":[45,30,8.5,12],"scale_authoring":"R133 later; Blender camera unchanged","resolution":3200,"faction_C0":"#A62416"},"selective_lighting_method":"Headless-stable material-selective low-strength Principled emission contribution on semantic Blender material slots; equivalent diagnostic used instead of fragile light-linking collections.","lighting":LR,"bronze":BR,"cloth":CL,"finals":FINALS,"jobs":{k:list(v) for k,v in jobs.items()}}
 report["engine"]="BLENDER_EEVEE (Eevee Next implementation)"
 (OUT.parent/"blender-art-direction-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
