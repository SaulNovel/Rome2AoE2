"""Expanded fixed-composition stock-punch lighting/material investigation."""
import json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"src/blender"))
import render_hastati_aoe_art_direction as ad
import render_cross_unit_set_a as cu
from render_material_reconstruction_v1 import reconstruct
from render_lighting_sweep import clear_lights,set_world,add_sun,add_area,area
OUT=ROOT/"build/local-integration/rome2/hastati-stock-punch/masters";OUT.mkdir(parents=True,exist_ok=True)
LIGHTS={
 "A0":{"name":"L11 control","base":"L11","areas":[]},
 "A1":{"name":"Lower left key","world":{"mode":"neutral","strength":.34,"color":[.82,.83,.84]},"sun":{"strength":.55,"azimuth":120,"elevation":48,"angular_size":20},"areas":[area("key",(7,1,5),900,5.5),area("fill",(2,7,5),360,7),area("rim",(-4,-3,6),130,4,(1,.82,.6))]},
 "A2":{"name":"Cross-body key","world":{"mode":"neutral","strength":.34,"color":[.82,.83,.84]},"sun":{"strength":.55,"azimuth":155,"elevation":54,"angular_size":20},"areas":[area("key",(4,-1,7),940,5.5),area("fill",(3,7,5),380,7),area("rim",(-5,-3,6),145,4,(1,.82,.6))]},
 "A3":{"name":"High key","world":{"mode":"neutral","strength":.38,"color":[.82,.83,.84]},"sun":{"strength":.45,"azimuth":135,"elevation":72,"angular_size":24},"areas":[area("key",(4,2,9),980,6),area("fill",(3,7,5),390,7),area("rim",(-4,-3,7),130,4,(1,.84,.65))]},
 "A4":{"name":"Low fill high separation","world":{"mode":"neutral","strength":.24,"color":[.82,.83,.84]},"sun":{"strength":.62,"azimuth":128,"elevation":55,"angular_size":18},"areas":[area("key",(6,2,7),1050,5.5),area("fill",(3,7,5),210,7),area("rim",(-4,-3,7),145,4,(1,.82,.6))]},
 "A5":{"name":"Medium fill","world":{"mode":"neutral","strength":.34,"color":[.82,.83,.84]},"sun":{"strength":.55,"azimuth":128,"elevation":56,"angular_size":22},"areas":[area("key",(6,2,7),1040,6),area("fill",(3,7,5),460,7),area("rim",(-4,-3,7),150,4,(1,.82,.6))]},
 "A6":{"name":"Readable rim","world":{"mode":"neutral","strength":.32,"color":[.82,.83,.84]},"sun":{"strength":.55,"azimuth":128,"elevation":56,"angular_size":22},"areas":[area("key",(6,2,7),1030,6),area("fill",(3,7,5),390,7),area("rim",(-4,-3,7),260,4.5,(1,.78,.52))]},
 "A7":{"name":"Ambient lift","world":{"mode":"neutral","strength":.68,"color":[.82,.83,.84]},"sun":{"strength":.42,"azimuth":128,"elevation":58,"angular_size":26},"areas":[area("key",(6,2,7),850,6.5),area("fill",(3,7,5),360,7.5),area("rim",(-4,-3,7),130,4,(1,.84,.65))]},
 "A8":{"name":"Very soft studio","world":{"mode":"neutral","strength":.44,"color":[.82,.83,.84]},"sun":{"strength":.30,"azimuth":130,"elevation":60,"angular_size":32},"areas":[area("key",(6,2,8),1080,8),area("fill",(2,7,6),480,8),area("rim",(-4,-3,7),150,5,(1,.84,.65))]},
 "A9":{"name":"Punch studio","world":{"mode":"neutral","strength":.28,"color":[.80,.82,.84]},"sun":{"strength":.62,"azimuth":125,"elevation":54,"angular_size":18},"areas":[area("key",(7,1,7),1180,5.5),area("fill",(2,7,5),390,7),area("upper",(4,4,9),210,6),area("rim",(-4,-3,7),205,4,(1,.78,.5))]},
}
MATERIALS={
 "B0":{"name":"Raw reconstructed control"},
 "B1":{"name":"Rich bronze","bronze":True},
 "B2":{"name":"Assertive red cloth","cloth":True},
 "B3":{"name":"Natural skin","skin":True},
 "B4":{"name":"Shield separation","shield":True},
 "B5":{"name":"Leather restraint","leather":True},
 "B6":{"name":"Bronze plus cloth","bronze":True,"cloth":True},
 "B7":{"name":"Balanced all-material response","bronze":True,"cloth":True,"skin":True,"shield":True,"leather":True},
}
SKIN={"roman_body1","roman_1_head"};SHIELD={"roman_early_scutum_lod1"};LEATHER={"roman_1_sandals","roman_belt_01"}
def tune(defn):
 for mat in bpy.data.materials:
  key=mat.name.split('.')[0];b=ad.bsdf(mat)
  if not b:continue
  if defn.get("bronze") and key in ad.BRONZE:ad.multiply_base(mat,(.54,.40,.25));b.inputs["Metallic"].default_value=1;ad.emission_fill(mat,.014,True);sock=b.inputs["Roughness"];[mat.node_tree.links.remove(x) for x in list(sock.links)];sock.default_value=.58
  if defn.get("cloth") and key in ad.CLOTH:ad.multiply_base(mat,(1.10,.91,.86));ad.emission_fill(mat,.026,True);sock=b.inputs["Roughness"];[mat.node_tree.links.remove(x) for x in list(sock.links)];sock.default_value=.76
  if defn.get("skin") and key in SKIN:ad.multiply_base(mat,(.94,.86,.80));sock=b.inputs["Roughness"];[mat.node_tree.links.remove(x) for x in list(sock.links)];sock.default_value=.68
  if defn.get("shield") and key in SHIELD:ad.multiply_base(mat,(.78,.80,.82));sock=b.inputs["Roughness"];[mat.node_tree.links.remove(x) for x in list(sock.links)];sock.default_value=.66
  if defn.get("leather") and key in LEATHER:ad.multiply_base(mat,(.70,.62,.55));sock=b.inputs["Roughness"];[mat.node_tree.links.remove(x) for x in list(sock.links)];sock.default_value=.78
def rig(d):
 if d.get("base")=="L11":cu.lighting("L11");return
 s=bpy.context.scene;clear_lights(s);set_world(s,d["world"]);add_sun(s,d["sun"])
 for x in d["areas"]:add_area(s,x)
def render(cid,light,material):
 bpy.ops.wm.read_factory_settings(use_empty=True);root,_=cu.import_unit("hastati");cu.configure_camera(bpy.context.scene,45,30,8.5,12);reconstruct(root,ad.COLORS,True);rig(LIGHTS[light]);tune(MATERIALS[material]);s=bpy.context.scene;s.render.engine="BLENDER_EEVEE";s.render.resolution_x=s.render.resolution_y=3200;s.render.resolution_percentage=100;s.render.film_transparent=True;s.render.image_settings.file_format="PNG";s.render.image_settings.color_mode="RGBA";s.render.image_settings.color_depth="8";s.display_settings.display_device="sRGB";s.view_settings.view_transform="Standard";s.view_settings.look="None";s.view_settings.exposure=.65;s.view_settings.gamma=1;s.render.filepath=str((OUT/f"{cid}.png").resolve());bpy.ops.render.render(write_still=True);print("rendered",cid,flush=True)
def main():
 m=json.loads(ad.EFFECTIVE.read_text());ad.COLORS=tuple(ad.linear(m["faction_colours"][x]) for x in ("C0","C1","C2"))
 for cid in LIGHTS:render(cid,cid,"B0")
 for cid in MATERIALS:render(cid,"A9",cid)
 (OUT.parent/"stock-punch-blender-report.json").write_text(json.dumps({"format":"rome2aoe2.stock-punch-blender","version":1,"fixed":{"composition":"unchanged","camera":[45,30,8.5,12],"pose_frame":1,"resolution":3200,"view":"Standard","exposure":.65},"lighting_only":LIGHTS,"material_only":MATERIALS},indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
