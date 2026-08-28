"""Source-semantic Rome II tint/normal/spec-gloss material reconstruction."""
import json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration";OUT=ROOT/"build"/"local-integration"/"rome2"/"material-reconstruction"/"renders";OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/"src"/"blender"))
from render_cross_unit_set_a import import_unit,configure_camera,setup_render,lighting,CLASS
UNITS=("hastati","principes","triarii","velites","hoplites","celtic-warriors","eastern-spearmen")
# Gamma-authored TEST colours. White disables a channel. These are diagnostic,
# deterministic, and explicitly not authentic faction colours.
TEST={"neutral":((1,1,1),(1,1,1),(1,1,1)),"R":((1,.12,.12),(1,1,1),(1,1,1)),"G":((1,1,1),(.12,1,.12),(1,1,1)),"B":((1,1,1),(1,1,1),(.12,.12,1)),"RGB":((1,.12,.12),(.12,1,.12),(.12,.12,1))}
def maps(root):
 d=json.loads((root/"texture-manifest.json").read_text());return {m["material_name"]:{t["semantic"]:root/"textures"/Path(t["extracted_path"]) for t in m["textures"] if t["status"]=="resolved"} for m in d["materials"]}
def tex(nodes,path,label,noncolor=False):
 n=nodes.new("ShaderNodeTexImage");n.label=label;n.image=bpy.data.images.load(str(path),check_existing=True)
 if noncolor:n.image.colorspace_settings.name="Non-Color"
 return n
def exact_tint(nodes,links,color,mask,colors):
 sep=nodes.new("ShaderNodeSeparateColor");links.new(mask.outputs["Color"],sep.inputs["Color"]);cur=color
 for socket,c in zip(("Red","Green","Blue"),colors):
  mult=nodes.new("ShaderNodeMixRGB");mult.blend_type="MULTIPLY";mult.inputs[0].default_value=1;mult.inputs[2].default_value=(*c,1);links.new(cur,mult.inputs[1])
  mix=nodes.new("ShaderNodeMixRGB");mix.blend_type="MIX";links.new(sep.outputs[socket],mix.inputs[0]);links.new(cur,mix.inputs[1]);links.new(mult.outputs["Color"],mix.inputs[2]);cur=mix.outputs["Color"]
 return cur
def packed_normal(nodes,links,image):
 s=nodes.new("ShaderNodeSeparateColor");links.new(image.outputs["Color"],s.inputs["Color"])
 xa=nodes.new("ShaderNodeMath");xa.operation="MULTIPLY";links.new(s.outputs["Red"],xa.inputs[0]);links.new(image.outputs["Alpha"],xa.inputs[1])
 yi=nodes.new("ShaderNodeMath");yi.operation="SUBTRACT";yi.inputs[0].default_value=1;links.new(s.outputs["Green"],yi.inputs[1])
 x2=nodes.new("ShaderNodeMath");x2.operation="MULTIPLY_ADD";x2.inputs[1].default_value=2;x2.inputs[2].default_value=-1;links.new(xa.outputs[0],x2.inputs[0])
 y2=nodes.new("ShaderNodeMath");y2.operation="MULTIPLY_ADD";y2.inputs[1].default_value=2;y2.inputs[2].default_value=-1;links.new(yi.outputs[0],y2.inputs[0])
 xx=nodes.new("ShaderNodeMath");xx.operation="MULTIPLY";links.new(x2.outputs[0],xx.inputs[0]);links.new(x2.outputs[0],xx.inputs[1]);yy=nodes.new("ShaderNodeMath");yy.operation="MULTIPLY";links.new(y2.outputs[0],yy.inputs[0]);links.new(y2.outputs[0],yy.inputs[1]);add=nodes.new("ShaderNodeMath");add.operation="ADD";links.new(xx.outputs[0],add.inputs[0]);links.new(yy.outputs[0],add.inputs[1]);one=nodes.new("ShaderNodeMath");one.operation="SUBTRACT";one.inputs[0].default_value=1;links.new(add.outputs[0],one.inputs[1]);one.use_clamp=True;z=nodes.new("ShaderNodeMath");z.operation="SQRT";links.new(one.outputs[0],z.inputs[0])
 enc=nodes.new("ShaderNodeCombineColor")
 for val,sock in ((x2.outputs[0],"Red"),(y2.outputs[0],"Green"),(z.outputs[0],"Blue")):
  n=nodes.new("ShaderNodeMath");n.operation="MULTIPLY_ADD";n.inputs[1].default_value=.5;n.inputs[2].default_value=.5;links.new(val,n.inputs[0]);links.new(n.outputs[0],enc.inputs[sock])
 nm=nodes.new("ShaderNodeNormalMap");nm.space="TANGENT";nm.inputs["Strength"].default_value=1;links.new(enc.outputs["Color"],nm.inputs["Color"]);return nm.outputs["Normal"]
def reconstruct(root,colors=TEST["neutral"],normal_on=True):
 mm=maps(root)
 for mat in bpy.data.materials:
  key=mat.name.split(".")[0];t=mm.get(key,{})
  if not t:continue
  mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;n.clear();o=n.new("ShaderNodeOutputMaterial");b=n.new("ShaderNodeBsdfPrincipled");l.new(b.outputs["BSDF"],o.inputs["Surface"]);cls=CLASS.get(key,"unknown")
  di=tex(n,t["Diffuse"],"Rome diffuse") if "Diffuse" in t else None;base=di.outputs["Color"] if di else None
  mk=tex(n,t["Mask"],"Rome faction RGB",True) if "Mask" in t and "test_mask" not in str(t["Mask"]).lower() else None
  if base and mk:base=exact_tint(n,l,base,mk,colors)
  conductor=cls in ("bronze","iron/steel")
  sp=tex(n,t["Specular"],"Rome specular RGB") if "Specular" in t else None
  if conductor:
   b.inputs["Metallic"].default_value=1
   if sp:l.new(sp.outputs["Color"],b.inputs["Base Color"])
   elif base:l.new(base,b.inputs["Base Color"])
  else:
   b.inputs["Metallic"].default_value=0
   if base:l.new(base,b.inputs["Base Color"])
   if sp:
    bw=n.new("ShaderNodeRGBToBW");l.new(sp.outputs["Color"],bw.inputs["Color"]);scale=n.new("ShaderNodeMath");scale.operation="DIVIDE";scale.inputs[1].default_value=.08;scale.use_clamp=True;l.new(bw.outputs["Val"],scale.inputs[0]);l.new(scale.outputs[0],b.inputs["Specular IOR Level"])
  if "GlossMap" in t:
   gl=tex(n,t["GlossMap"],"Rome gloss R",True);s=n.new("ShaderNodeSeparateColor");l.new(gl.outputs["Color"],s.inputs["Color"]);sq=n.new("ShaderNodeMath");sq.operation="MULTIPLY";l.new(s.outputs["Red"],sq.inputs[0]);l.new(s.outputs["Red"],sq.inputs[1]);inv=n.new("ShaderNodeMath");inv.operation="SUBTRACT";inv.inputs[0].default_value=1;l.new(sq.outputs[0],inv.inputs[1]);l.new(inv.outputs[0],b.inputs["Roughness"])
  else:b.inputs["Roughness"].default_value=.7
  if normal_on and "Normal" in t:
   no=tex(n,t["Normal"],"Rome packed normal R*A,1-G",True);l.new(packed_normal(n,l,no),b.inputs["Normal"])
  if di and di.outputs.get("Alpha"):l.new(di.outputs["Alpha"],b.inputs["Alpha"])
def render(slug,name,colors=TEST["neutral"],normal_on=True):
 bpy.ops.wm.read_factory_settings(use_empty=True);root,_=import_unit(slug);configure_camera(bpy.context.scene,45,30,8.5,12);reconstruct(root,colors,normal_on);lighting("L11");setup_render(OUT/name)
def main():
 for slug in UNITS:
  for k,c in TEST.items():render(slug,f"{slug}-faction-{k}.png",c,True)
  render(slug,f"{slug}-reconstructed.png",TEST["neutral"],True);render(slug,f"{slug}-normal-off.png",TEST["neutral"],False)
 (OUT.parent/"material-reconstruction-v1.json").write_text(json.dumps({"format":"rome2aoe2.material-reconstruction-v1","version":1,"units":UNITS,"fixed_light":"L11","test_colors":TEST,"equations":{"tint":"sequential lerp(D,D*linear(Ci),mask_i)","normal":"x=2*(R*A)-1; y=2*(1-G)-1; z=sqrt(max(0,1-x^2-y^2))","roughness":"1-gloss.r^2"}},indent=2)+"\n")
if __name__=="__main__":main()
