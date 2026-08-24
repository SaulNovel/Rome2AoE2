"""One facet-03 proof using the captured Rome II deferred material pipeline.

Blender is used only to assemble/pose/rasterise source-material G-buffer inputs.
Lighting and display conversion are evaluated below from the frame-46753 capture.
"""
import json
import math
import struct
import sys
import zlib
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/blender"))
sys.path.insert(0, str(ROOT / "src/rome2"))
import render_cross_unit_set_a as cu
from runtime_material_preparation import (prepare_decal_dirtmap,
    prepare_weighted, prepare_weighted_dirtmap, prepare_weighted_skin_dirtmap,
    shield_faction_colours)
from rome2aoe2.shield_readability import resolve_shield_readability

OUT = ROOT / "build/local-integration/rome2/runtime-parity-proof"
AOV = OUT / "aov"
REC = ROOT / "build/local-integration/rome2/runtime-shader-recovery/capture-analysis/frame46753/resources-export"
DECAL_REC = ROOT / "build/local-integration/rome2/runtime-shader-recovery/capture-analysis/frame46753/decal-inventory"
FACET_AZIMUTH = 112.5
RESOLUTION = 3200
FACTION = (
    (0.388910264, 0.013473397, 0.004559755),
    (1.0, 0.470440269, 0.000107187),
    (0.325036973, 0.042987015, 0.013473397),
)
SHIELD_FACTION = shield_faction_colours(FACTION)
SUN_DIRECTION_R2 = np.array((0.752204835, -0.368124515, 0.546509087), np.float32)
SUN_COLOUR = np.array((4744.829102, 4335.678711, 3330.588623), np.float32)
AMBIENT = np.array((
    ((0.757388592, 0.619574547, 0.428393602), (0.589906037, 0.479111701, 0.287942886)),
    ((0.746249497, 1.065410614, 1.176159620), (0.051749278, 0.068555206, 0.074733950)),
    ((0.670795798, 0.542214215, 0.412173957), (0.670795798, 0.826110303, 1.176159620)),
), np.float32)


def image_node(nodes, path, noncolor=False):
    node = nodes.new("ShaderNodeTexImage")
    node.image = bpy.data.images.load(str(path), check_existing=True)
    node.interpolation = "Linear"
    node.extension = "REPEAT"
    if noncolor:
        node.image.colorspace_settings.name = "Non-Color"
    return node


def math_node(nodes, operation, a=None, b=None):
    n = nodes.new("ShaderNodeMath"); n.operation = operation
    if isinstance(a, (int, float)): n.inputs[0].default_value = a
    if isinstance(b, (int, float)): n.inputs[1].default_value = b
    return n


def _image_uv(nodes, links, node, uv_name="UVMap", scale=1.0):
    uv=nodes.new("ShaderNodeUVMap");uv.uv_map=uv_name
    value=uv.outputs["UV"]
    if scale != 1.0:
        mul=nodes.new("ShaderNodeVectorMath")
        if isinstance(scale,(tuple,list)):
            mul.operation="MULTIPLY";mul.inputs[1].default_value=(*scale[:2],1.0)
        else:
            mul.operation="SCALE";mul.inputs[3].default_value=scale
        links.new(value,mul.inputs[0]);value=mul.outputs[0]
    links.new(value,node.inputs["Vector"])


def _encoded_vector(nodes, links, vector):
    scale=nodes.new("ShaderNodeVectorMath");scale.operation="SCALE";scale.inputs[3].default_value=.5;links.new(vector,scale.inputs[0])
    add=nodes.new("ShaderNodeVectorMath");add.operation="ADD";add.inputs[1].default_value=(.5,.5,.5);links.new(scale.outputs[0],add.inputs[0]);return add.outputs[0]


def _normal_uv_name(material, material_type):
    """Use skin TEXCOORD_1 only when the decoded source set is non-degenerate.

    Rome II assets without a secondary set decode to a constant (0, 0).  The
    approved Asset Editor scene omits that empty layer and therefore samples
    the primary set; preserve the same source-defined fallback after glTF import.
    """
    if material_type != "WeightedSkinDirtmap":
        return "UVMap"
    for obj in bpy.data.objects:
        if obj.type != "MESH" or not any(slot.material == material for slot in obj.material_slots):
            continue
        layer = obj.data.uv_layers.get("UVMap.001")
        if layer is None or not layer.data:
            continue
        u0, v0 = layer.data[0].uv
        if any(abs(item.uv[0]-u0)>1e-7 or abs(item.uv[1]-v0)>1e-7 for item in layer.data[1:]):
            return "UVMap.001"
    return "UVMap"


def build_pass(root, pass_name, texture_base=None):
    manifest=json.loads((root/"texture-manifest.json").read_text())
    records={m["material_name"]:m for m in manifest["materials"]}
    texture_base=Path(texture_base) if texture_base is not None else root/"textures"
    maps={name:{t["semantic"]:texture_base/Path(t["extracted_path"]) for t in row["textures"] if t["status"]=="resolved"} for name,row in records.items()}
    material_roles={}
    for obj in bpy.data.objects:
        if obj.type!="MESH":continue
        for slot in obj.material_slots:
            if slot.material:material_roles.setdefault(slot.material.name.split('.')[0],set()).add(obj.get("manifest_component"))
    for mat in bpy.data.materials:
        key=mat.name.split('.')[0]; tex=maps.get(key,{})
        mat.use_nodes=True; nodes=mat.node_tree.nodes; links=mat.node_tree.links; nodes.clear()
        out=nodes.new("ShaderNodeOutputMaterial"); emission=nodes.new("ShaderNodeEmission"); transparent=nodes.new("ShaderNodeBsdfTransparent"); mix=nodes.new("ShaderNodeMixShader")
        links.new(transparent.outputs[0],mix.inputs[1]); links.new(emission.outputs[0],mix.inputs[2]); links.new(mix.outputs[0],out.inputs["Surface"])
        di=image_node(nodes,tex["Diffuse"],False) if "Diffuse" in tex else None
        alpha=di.outputs["Alpha"] if di else None
        if alpha:
            cutoff=math_node(nodes,"GREATER_THAN",b=128/255); links.new(alpha,cutoff.inputs[0]); links.new(cutoff.outputs[0],mix.inputs[0])
        else: mix.inputs[0].default_value=1
        material_type=records.get(key,{}).get("material_type")
        mask=image_node(nodes,tex["Mask"],True) if "Mask" in tex and "test_mask" not in str(tex["Mask"]).lower() else None
        spec=image_node(nodes,tex["Specular"],False) if "Specular" in tex else None
        gloss=image_node(nodes,tex["GlossMap"],False) if "GlossMap" in tex else None # captured sRGB view
        normal=image_node(nodes,tex["Normal"],True) if "Normal" in tex else None
        normal_uv=_normal_uv_name(mat,material_type)
        if normal:
            # Captured skin TEXCOORD1.zw maps to the preserved glTF TEXCOORD_1.
            _image_uv(nodes,links,normal,normal_uv)
        dirt_map=dirt_mask=skin_mask=None
        if material_type=="WeightedDirtmap" and key=="roman_montefortino":
            # Frozen captured bindings used by the approved Hastati frames.
            dirt_map=image_node(nodes,REC/"helmet_05_s_decal_dirt_map.dds",True)
            dirt_mask=image_node(nodes,REC/"helmet_04_s_decal_dirt_mask.dds",True)
        elif material_type=="WeightedDirtmap":
            # Other assets use their authoritative bindings.  CA's test_black
            # placeholder is a zero-contribution sentinel, never full dirt.
            if "DecalDirtmap" in tex and "test_black" not in str(tex["DecalDirtmap"]).lower():
                dirt_map=image_node(nodes,tex["DecalDirtmap"],True)
            if "DecalDirtmask" in tex and "test_black" not in str(tex["DecalDirtmask"]).lower():
                dirt_mask=image_node(nodes,tex["DecalDirtmask"],True)
            scales={int(pair[0]):float(pair[1]) for pair in records.get(key,{}).get("parameters",{}).get("float",[])}
            dirt_scale=(scales.get(0,1.0),scales.get(1,1.0))
            if dirt_map:_image_uv(nodes,links,dirt_map,"UVMap",dirt_scale)
            if dirt_mask:_image_uv(nodes,links,dirt_mask,"UVMap",dirt_scale)
        elif material_type=="WeightedSkinDirtmap":
            if "DecalDirtmap" in tex and "DecalDirtmask" in tex:
                dirt_map=image_node(nodes,tex["DecalDirtmap"],True); dirt_mask=image_node(nodes,tex["DecalDirtmask"],True)
                _image_uv(nodes,links,dirt_map,"UVMap",4)
            if "SkinMask" in tex: skin_mask=image_node(nodes,tex["SkinMask"],True)
        elif material_type=="DecalDirtmap":
            if "DecalDirtmap" in tex:
                dirt_map=image_node(nodes,tex["DecalDirtmap"],True)
                # The pack resolver reports `test_black` as missing, so retain
                # the exact captured binding under ignored local evidence.
                dirt_mask=image_node(nodes,DECAL_REC/"resource-7925-slice0-mip0.dds",True)
        if pass_name=="diffuse_raw": value=di.outputs["Color"] if di else None
        elif pass_name=="specular_raw": value=skin_mask.outputs["Color"] if skin_mask else (spec.outputs["Color"] if spec else None)
        elif pass_name=="gloss_raw": value=gloss.outputs["Color"] if gloss else None
        elif pass_name=="normal_sample": value=normal.outputs["Color"] if normal else None
        elif pass_name=="normal_alpha": value=normal.outputs["Alpha"] if normal else None
        elif pass_name=="mask_raw": value=mask.outputs["Color"] if mask else None
        elif pass_name=="dirt_raw": value=dirt_map.outputs["Color"] if dirt_map else None
        elif pass_name=="dirt_alpha": value=dirt_map.outputs["Alpha"] if dirt_map else None
        elif pass_name=="dirt_mask_raw": value=dirt_mask.outputs["Color"] if dirt_mask else None
        elif pass_name=="dirt_mask_alpha": value=dirt_mask.outputs["Alpha"] if dirt_mask else None
        elif pass_name=="family":
            codes={"WeightedSkinDirtmap":(1,0,0,1),"DecalDirtmap":(0,1,0,1),"WeightedDirtmap":(0,0,1,1),"Weighted":(0,0,0,1)}
            emission.inputs["Color"].default_value=codes.get(material_type,(1,1,0,1)); value=None
        elif pass_name=="semantic_role":
            roles=material_roles.get(key,set());code=(1,0,0,1) if roles=={"shield"} else ((0,1,0,1) if roles=={"melee_weapon"} else (0,0,0,1))
            emission.inputs["Color"].default_value=code;value=None
        elif pass_name=="region":
            if key=="italian_square_muscled_cuirass_": code=(1,0,0,1)
            elif key in ("roman_body1","roman_1_head"): code=(0,1,0,1)
            elif key in ("E3_tunic","E3_tunic_flipped"): code=(0,0,1,1)
            elif key=="roman_montefortino": code=(1,1,0,1)
            else: code=(0,0,0,1)
            emission.inputs["Color"].default_value=code;value=None
        elif pass_name in ("basis_normal","basis_tangent","basis_bitangent"):
            if pass_name=="basis_normal":
                geo=nodes.new("ShaderNodeNewGeometry");vector=geo.outputs["Normal"]
            else:
                nm=nodes.new("ShaderNodeNormalMap");nm.space="TANGENT";nm.uv_map=normal_uv
                nm.inputs["Strength"].default_value=1
                nm.inputs["Color"].default_value=((1,.5,.5,1) if pass_name=="basis_tangent" else (.5,1,.5,1))
                vector=nm.outputs["Normal"]
            value=_encoded_vector(nodes,links,vector)
        else:
            value=None
        if value: links.new(value,emission.inputs["Color"])
        elif pass_name=="diffuse_raw": emission.inputs["Color"].default_value=(.5,.5,.5,1)
        elif pass_name=="specular_raw": emission.inputs["Color"].default_value=(.04,.04,.04,1)
        elif pass_name=="gloss_raw": emission.inputs["Color"].default_value=(.35,.04,0,1)
        elif pass_name=="normal_sample": emission.inputs["Color"].default_value=(.5,.5,1,1)
        elif pass_name not in ("family","region","semantic_role"): emission.inputs["Color"].default_value=(0,0,0,1)


def render_aov(scene, root, name, texture_base=None):
    build_pass(root,name,texture_base); path=(AOV/f"{name}.exr").resolve(); scene.render.filepath=str(path); bpy.ops.render.render(write_still=True)
    image=bpy.data.images.load(str(path),check_existing=False); data=np.empty(len(image.pixels),np.float32); image.pixels.foreach_get(data); data=data.reshape((RESOLUTION,RESOLUTION,4))[::-1].copy(); bpy.data.images.remove(image)
    np.save(AOV/f"{name}.npy",data); return data


def decode_ufloat(v, mantissa_bits):
    exp=(v>>mantissa_bits)&31; mant=v&((1<<mantissa_bits)-1)
    return np.where(exp==0,mant*np.float32(2.0**(1-15-mantissa_bits)),(1+mant/np.float32(1<<mantissa_bits))*np.exp2(exp.astype(np.float32)-15))


def load_cube(path):
    raw=path.read_bytes(); offset=148; faces=[]
    for face in range(6):
        mips=[]
        for mip in range(9):
            n=max(1,256>>mip); packed=np.frombuffer(raw,dtype='<u4',count=n*n,offset=offset).reshape(n,n); offset += n*n*4
            r=decode_ufloat(packed&0x7ff,6); g=decode_ufloat((packed>>11)&0x7ff,6); b=decode_ufloat((packed>>22)&0x3ff,5)
            mips.append(np.stack((r,g,b),axis=-1).astype(np.float32))
        faces.append(mips)
    return faces


def cube_sample(cube, directions, lod):
    flat=directions.reshape(-1,3); result=np.zeros_like(flat); major=np.argmax(np.abs(flat),axis=1); signs=flat[np.arange(len(flat)),major]>=0
    for axis in range(3):
        for positive in (False,True):
            ids=np.where((major==axis)&(signs==positive))[0]
            if not len(ids): continue
            d=flat[ids]; a=np.abs(d[:,axis]); x,y,z=d[:,0],d[:,1],d[:,2]
            if axis==0: face=0 if positive else 1; u=(-z if positive else z)/a; v=-y/a
            elif axis==1: face=2 if positive else 3; u=x/a; v=(z if positive else -z)/a
            else: face=4 if positive else 5; u=(x if positive else -x)/a; v=-y/a
            lv=np.clip(lod.reshape(-1)[ids],0,8); lo=np.floor(lv).astype(int); hi=np.minimum(lo+1,8); frac=lv-lo
            accum=np.zeros((len(ids),3),np.float32)
            for level_set,weight in ((lo,1-frac),(hi,frac)):
                for level in np.unique(level_set):
                    q=np.where(level_set==level)[0]; im=cube[face][level]; n=im.shape[0]; px=np.clip((u[q]*.5+.5)*(n-1),0,n-1); py=np.clip((v[q]*.5+.5)*(n-1),0,n-1)
                    x0=np.floor(px).astype(int); y0=np.floor(py).astype(int); x1=np.minimum(x0+1,n-1); y1=np.minimum(y0+1,n-1); fx=(px-x0)[:,None]; fy=(py-y0)[:,None]
                    sample=(im[y0,x0]*(1-fx)*(1-fy)+im[y0,x1]*fx*(1-fy)+im[y1,x0]*(1-fx)*fy+im[y1,x1]*fx*fy)
                    accum[q]+=sample*weight[q,None]
            result[ids]=accum
    return result.reshape(directions.shape)


def erf_ca(x):
    # Same Winitzki approximation/constants visible in the captured DXBC.
    a=np.float32(.140012); xx=x*x
    return np.sign(x)*np.sqrt(np.maximum(0,1-np.exp(-xx*(np.float32(4/math.pi)+a*xx)/(1+a*xx))))


def erfinv_ca(x):
    a=np.float32(.140012); ln=np.log(np.maximum(1e-20,1-x*x)); t=np.float32(2/(math.pi*.140012))+ln*.5
    return np.sign(x)*np.sqrt(np.maximum(0,np.sqrt(np.maximum(0,t*t-ln/a))-t))


def facet_fraction(smoothness, angle):
    distribution=.02+.9799*smoothness*smoothness; inv=erfinv_ca(distribution); sigma=np.maximum(np.float32(.0001),np.float32(math.radians(1))/(np.float32(math.sqrt(2))*np.maximum(inv,1e-12)))
    return .5*(erf_ca((angle+math.radians(1))/(sigma*math.sqrt(2)))-erf_ca((angle-math.radians(1))/(sigma*math.sqrt(2))))


def normalize(v): return v/np.maximum(np.linalg.norm(v,axis=-1,keepdims=True),1e-12)


def png_rgba(path, rgba):
    data=np.clip(np.rint(rgba*255),0,255).astype(np.uint8); h,w,_=data.shape; raw=b''.join(b'\0'+data[y].tobytes() for y in range(h))
    def chunk(kind,payload): return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw,6))+chunk(b'IEND',b''))


def debug_rgba(name,rgb,alpha,active):
    out=np.clip(rgb,0,1).copy(); out[~active]=0; png_rgba(OUT/name,np.concatenate((out,np.clip(alpha,0,1)),axis=-1))


def shade(scene, arrays, environment_yaw_degrees=0, output_name="runtime-parity-f03.png", diagnostics=True, region_aov=None, canvas_offset=None, prepared_override=None,
          illumination_yaw_offset_degrees=0.0, readability_fill=0.0,
          equipment_readability=0.0, equipment_mask=None, metric_masks=None,
          equipment_diffuse_irradiance_floor=None, equipment_floor_transition=0.15,
          semantic_role_aov=None, shield_readability=None):
    diffuse_aov=arrays["diffuse_raw"]; family_aov=arrays["family"]
    # Blender surface alpha is geometric coverage, so texture alpha travels in
    # explicit raw scalar passes rather than being confused with AOV coverage.
    arrays["normal_sample"][...,3]=arrays["normal_alpha"][...,0]
    arrays["dirt_raw"][...,3]=arrays["dirt_alpha"][...,0]
    arrays["dirt_mask_raw"][...,3]=arrays["dirt_mask_alpha"][...,0]
    alpha=diffuse_aov[...,3:4]; active=alpha[...,0]>.001
    base=normalize(arrays["basis_normal"][...,:3]*2-1)
    tangent=normalize(arrays["basis_tangent"][...,:3]*2-1)
    bitangent=normalize(arrays["basis_bitangent"][...,:3]*2-1)
    shape=diffuse_aov.shape[:2];N=base.copy();D=np.zeros((*shape,3),np.float32);F=np.zeros((*shape,3),np.float32);S=np.zeros(shape,np.float32);R=np.zeros(shape,np.float32)
    skin_pixels=(family_aov[...,0]>.5)&(family_aov[...,1]<.5)
    decal_pixels=(family_aov[...,1]>.5)&(family_aov[...,0]<.5)
    dirt_pixels=(family_aov[...,2]>.5)&(family_aov[...,0]<.5)&(family_aov[...,1]<.5)
    weighted_pixels=active&~skin_pixels&~decal_pixels&~dirt_pixels
    if prepared_override is not None:
        N=np.asarray(prepared_override["normal"],np.float32).copy();D=np.asarray(prepared_override["diffuse"],np.float32).copy()
        F=np.asarray(prepared_override["specular"],np.float32).copy();S=np.asarray(prepared_override["smoothness"],np.float32).copy();R=np.asarray(prepared_override["reflectivity"],np.float32).copy()
    else:
        def assign(mask,p):
            N[mask]=p.normal;D[mask]=p.diffuse;F[mask]=p.specular;S[mask]=p.smoothness;R[mask]=p.reflectivity
        raw=(diffuse_aov,arrays["specular_raw"],arrays["normal_sample"],arrays["gloss_raw"])
        if np.any(weighted_pixels):
            q=weighted_pixels;assign(q,prepare_weighted(*(x[q] for x in raw),base[q],tangent[q],bitangent[q],arrays["mask_raw"][q],FACTION))
        if np.any(dirt_pixels):
            q=dirt_pixels;assign(q,prepare_weighted_dirtmap(*(x[q] for x in raw),arrays["dirt_mask_raw"][q],arrays["dirt_raw"][q],base[q],tangent[q],bitangent[q],arrays["mask_raw"][q],FACTION))
        if np.any(skin_pixels):
            q=skin_pixels;assign(q,prepare_weighted_skin_dirtmap(diffuse_aov[q],arrays["normal_sample"][q],arrays["gloss_raw"][q],arrays["dirt_mask_raw"][q],arrays["dirt_raw"][q],arrays["specular_raw"][q],base[q],tangent[q],bitangent[q]))
        if np.any(decal_pixels):
            q=decal_pixels;assign(q,prepare_decal_dirtmap(*(x[q] for x in raw),arrays["mask_raw"][q],arrays["dirt_mask_raw"][q],arrays["dirt_raw"][q],base[q],tangent[q],bitangent[q],SHIELD_FACTION))
    D=np.maximum(D,0);F=np.maximum(F,0);S=np.clip(S,0,1);R=np.clip(R,0,1)
    V=np.array(scene.camera.matrix_world.to_quaternion()@Vector((0,0,1)),np.float32); V=V/np.linalg.norm(V)
    # Exact exporter/global conversion. Captured instance rows contain only
    # uniform scale + translation, so no per-soldier or camera-derived yaw exists.
    axis=np.array(((1,0,0),(0,0,-1),(0,1,0)),np.float32)
    transform=axis
    angle_yaw=math.radians(environment_yaw_degrees+illumination_yaw_offset_degrees);cy=math.cos(angle_yaw);sy=math.sin(angle_yaw)
    Renv=np.array(((cy,-sy,0),(sy,cy,0),(0,0,1)),np.float32)
    L0=transform@(-SUN_DIRECTION_R2);L=Renv@L0; L=L/np.linalg.norm(L)
    equipment_pixels=np.asarray(equipment_mask,bool) if equipment_mask is not None else np.zeros(shape,bool)
    shield_resolution=None
    if shield_readability is not None and semantic_role_aov is not None:
        shield_pixels=(np.asarray(semantic_role_aov)[...,0]>.5)&active
        if np.any(shield_pixels):
            response={"specular_luminance":float(np.mean(F[shield_pixels]@np.array((.2126,.7152,.0722),np.float32))),"smoothness":float(np.mean(S[shield_pixels])),"reflectivity":float(np.mean(R[shield_pixels]))}
            shield_resolution=resolve_shield_readability(
                "shield", response, dark_tail_cause="direct_diffuse_collapse")
            if shield_resolution["enabled"]:
                equipment_pixels=shield_pixels;equipment_diffuse_irradiance_floor=float(shield_resolution["floor"]);equipment_floor_transition=float(shield_resolution["transition_width"])
    Vfield=np.broadcast_to(V,N.shape); reflected=normalize(2*np.sum(N*Vfield,axis=-1,keepdims=True)*N-Vfield)
    cube_dirs=reflected@Renv@transform
    env=cube_sample(load_cube(REC/"s_environment.dds"),cube_dirs,(1-S)*8)
    ndotl=np.maximum(0,np.sum(N*L,axis=-1)); angle=np.arccos(np.clip(np.sum(reflected*L,axis=-1),-1,1)); drop=np.float32(math.cos(math.radians(1)))
    surface=R+(1-R)*np.maximum(0,np.sum(L*(-Vfield),axis=-1))**60
    direct_refl=np.clip((np.sum(N*L,axis=-1)+drop)/drop,0,1)*facet_fraction(S,angle)*surface
    env_surface=R+(1-R)*np.maximum(0,np.sum(reflected*(-Vfield),axis=-1))**60
    env_refl=np.maximum(R,np.clip((np.sum(N*reflected,axis=-1)+drop)/drop,0,1)*facet_fraction(S,np.zeros_like(S))*env_surface)
    direct_spec=direct_refl[...,None]*F*SUN_COLOUR
    direct_diff=D*ndotl[...,None]*SUN_COLOUR*.004*(1-np.maximum(direct_refl,R))[...,None]
    Nenv=N@Renv;Na=normalize(Nenv*np.array((1,4,1),np.float32)); weights=Na*Na; amb=np.zeros_like(N)
    for axis_i in range(3): amb+=weights[...,axis_i,None]*np.where((Na[...,axis_i]<0)[...,None],AMBIENT[axis_i,1],AMBIENT[axis_i,0])
    ambient_diff=amb*D*.004*(1-R)[...,None]
    # Optional production-policy diagnostic: an orientation-independent diffuse
    # readability floor.  Zero preserves the captured runtime equations exactly.
    readability_weight=np.full(shape,np.float32(readability_fill),np.float32)
    if equipment_mask is not None:readability_weight+=np.asarray(equipment_mask,bool)*np.float32(equipment_readability)
    # Legacy default invariant: readability_diff=D*np.float32(readability_fill)
    readability_diff=D*readability_weight[...,None]
    env_spec=env*env_refl[...,None]*F*2.5
    diffuse_lighting=ambient_diff+direct_diff+readability_diff
    equipment_shadow_fill=np.zeros_like(diffuse_lighting)
    equipment_floor_state=None
    if equipment_diffuse_irradiance_floor is not None and np.any(equipment_pixels):
        # Smooth maximum in pre-albedo irradiance space. It is exactly inactive
        # above floor+transition, so already-bright equipment is unchanged.
        direct_irradiance=ndotl[...,None]*SUN_COLOUR*.004*(1-np.maximum(direct_refl,R))[...,None]
        ambient_irradiance=amb*.004*(1-R)[...,None]
        base_irradiance=direct_irradiance+ambient_irradiance+readability_weight[...,None]
        irradiance_luminance=base_irradiance@np.array((.2126,.7152,.0722),np.float32)
        floor=np.float32(equipment_diffuse_irradiance_floor);width=np.float32(equipment_floor_transition)
        gap=floor-irradiance_luminance
        delta=np.where(gap>=width,gap,np.where(gap<=-width,0,(gap+width)**2/(4*width)))
        equipment_floor_state=np.where(gap>=width,2,np.where(gap<=-width,0,1))
        equipment_shadow_fill[equipment_pixels]=D[equipment_pixels]*delta[equipment_pixels,None]
        diffuse_lighting+=equipment_shadow_fill
    hdr=np.maximum(0,diffuse_lighting+env_spec+direct_spec)
    if np.any(skin_pixels):
        nd=np.sum(N*L,axis=-1)
        wrap=np.clip(nd[...,None]*np.array((.8,.9,.3),np.float32)+np.array((.3,.5,.3),np.float32),0,1)*np.array((.694444,.694444,.444444),np.float32)
        warm=wrap[...,1,None]*np.array((.612066,.456263,.05),np.float32); remain=np.clip(1-(nd*wrap[...,0]+.3),0,1)
        curve=remain[...,None]*warm
        scatter=wrap[...,2,None]*np.array((.32,.05,.006),np.float32)*(1-nd*wrap[...,0])[...,None]
        curve=scatter*(1-remain[...,None]*warm)+curve+(nd*wrap[...,0])[...,None]
        skin_nd=np.clip(nd[...,None]+F[...,1,None]*(curve-nd[...,None]),0,1)
        skin_direct_diff=D*skin_nd*SUN_COLOUR*.004*.9
        back_n=np.maximum(0,np.sum(N*(-L),axis=-1))**2; back_v=np.maximum(0,np.sum((-Vfield)*L,axis=-1))**4
        back_weight=back_n*back_v*F[...,2]
        back_sun=SUN_COLOUR*(1-F[...,1,None]*np.array((.3,1,1),np.float32))
        skin_back=D*back_weight[...,None]*back_sun*.004*.9
        skin_ambient_diff=D*amb*360*.0024
        exponent=S*S*127+1.6; sun_refl=normalize((-L)+2*N*nd[...,None])
        skin_spec_weight=np.maximum(0,np.sum(sun_refl*Vfield,axis=-1))**exponent*R
        skin_direct_spec=SUN_COLOUR*.004*skin_spec_weight[...,None]*2
        ndv=np.sum(Vfield*N,axis=-1); ambient_refl=normalize(Vfield-2*N*ndv[...,None]); Ar=normalize((ambient_refl@Renv)*np.array((1,4,1),np.float32)); ramb=np.zeros_like(N)
        for axis_i in range(3): ramb+=Ar[...,axis_i,None]**2*np.where((Ar[...,axis_i]<0)[...,None],AMBIENT[axis_i,1],AMBIENT[axis_i,0])
        grazing=np.clip(1-ndv,0,1)**2*F[...,0]*1.5; lifted=normalize(N+np.array((0,.75,0),np.float32)); skin_ambient_scatter=ramb*grazing[...,None]*np.maximum(0,lifted[...,1,None])
        skin_hdr=np.maximum(0,skin_ambient_diff+skin_ambient_scatter+skin_direct_diff+skin_back+skin_direct_spec+readability_diff)
        hdr=np.where(skin_pixels[...,None],skin_hdr,hdr)
    if diagnostics:
        np.save(AOV/"hdr_linear.npy",hdr.astype(np.float32))
        debug_rgba("debug-a-base-normal.png",base*.5+.5,alpha,active)
        debug_rgba("debug-b-final-normal.png",N*.5+.5,alpha,active)
        debug_rgba("debug-c-ndotl.png",np.repeat(ndotl[...,None],3,axis=-1),alpha,active)
        debug_rgba("debug-d-reflection.png",reflected*.5+.5,alpha,active)
        debug_rgba("debug-e-diffuse-only.png",diffuse_lighting/np.maximum(1+diffuse_lighting,1e-8),alpha,active)
        debug_rgba("debug-f-environment-specular-only.png",env_spec/np.maximum(1+env_spec,1e-8),alpha,active)
    lut=np.frombuffer((REC/"g_scurve_texture_sampler.bin").read_bytes(),dtype='<f2').astype(np.float32)
    # Captured event-2341 RGB <-> XYZ/Yxy matrices.
    xyz=hdr@np.array(((.4124564,.2126729,.0193339),(.3575761,.7151522,.1191920),(.1804375,.0721750,.9503041)),np.float32)
    total=np.maximum(np.sum(xyz,axis=-1),1e-8); Y=np.clip(xyz[...,1],0,15.5625); x=xyz[...,0]/total; y=np.maximum(xyz[...,1]/total,1e-8)
    log_black=np.float32(-3); log_white=np.float32(1.1630859375); black=np.float32(.0009994507); white=np.float32(15.5625)
    coord=np.clip((np.log10(np.maximum(Y,.011))-log_black)/(log_white-log_black),0,1); pos=coord*255; p0=np.floor(pos).astype(int); p1=np.minimum(p0+1,255); curve=lut[p0]*(1-(pos-p0))+lut[p1]*(pos-p0)
    mapped_log=curve*(log_white-log_black)+log_black
    mapped=(np.power(np.float32(10),mapped_log)-black)/(white-black)
    X=mapped*x/y; Z=mapped*(1-x-y)/y; yxy=np.stack((X,mapped,Z),axis=-1)
    rgb=yxy@np.array(((3.2404542,-.9692660,.0556434),(-1.5371385,1.8760108,-.2040259),(-.4985314,.0415560,1.0572252)),np.float32)
    rgb=np.sqrt(np.clip(rgb*1.2,0,1))*np.array((.964706,.996078,1),np.float32)
    rgb[~active]=0; rgba=np.concatenate((rgb,np.clip(alpha,0,1)),axis=-1)
    if canvas_offset is not None:
        x0,y0=canvas_offset;full=np.zeros((RESOLUTION,RESOLUTION,4),np.float32);full[y0:y0+rgba.shape[0],x0:x0+rgba.shape[1]]=rgba;png_rgba(OUT/output_name,full)
    else: png_rgba(OUT/output_name,rgba)
    luminance=np.sum(rgb*np.array((.2126,.7152,.0722),np.float32),axis=-1)
    def stats(mask):
        values=luminance[mask&active]
        if not len(values): return {"pixels":0,"p10":None,"median":None,"p90":None}
        p=np.percentile(values,(10,50,90));return {"pixels":int(len(values)),"mean":float(values.mean()),"p10":float(p[0]),"median":float(p[1]),"p90":float(p[2])}
    metrics={"yaw":float(environment_yaw_degrees+illumination_yaw_offset_degrees),"sun_direction":L.tolist(),"readability_fill":float(readability_fill),"body_luminance":stats(active),"dark_pixel_percentage":float(100*np.count_nonzero(active&(luminance<.08))/max(np.count_nonzero(active),1)),"highlight_p95":float(np.percentile(luminance[active],95)) if np.any(active) else None,"clipped_pixel_percentage":float(100*np.count_nonzero(active&np.any(rgb>=.999,axis=-1))/max(np.count_nonzero(active),1))}
    metrics["equipment_readability"]=float(equipment_readability)
    metrics["equipment_diffuse_irradiance_floor"]=None if equipment_diffuse_irradiance_floor is None else float(equipment_diffuse_irradiance_floor)
    metrics["shield_readability_resolution"]=shield_resolution
    if equipment_floor_state is not None:
        eligible=equipment_pixels&active;total=max(int(np.count_nonzero(eligible)),1)
        metrics["equipment_shadow_fill_coverage"]={"pixels":int(np.count_nonzero(eligible)),"zero_percent":float(100*np.count_nonzero(eligible&(equipment_floor_state==0))/total),"transition_percent":float(100*np.count_nonzero(eligible&(equipment_floor_state==1))/total),"full_percent":float(100*np.count_nonzero(eligible&(equipment_floor_state==2))/total)}
    if metric_masks:
        def contribution(source,mask):
            values=(source@np.array((.2126,.7152,.0722),np.float32))[mask&active]
            return {"mean_linear_luminance":float(values.mean()) if len(values) else None,"pixels":int(len(values))}
        def scalar_stats(source,mask):
            values=np.asarray(source)[mask&active];return {"mean":float(values.mean()),"median":float(np.median(values)),"p10":float(np.percentile(values,10)),"p90":float(np.percentile(values,90))} if len(values) else None
        metrics["component_contributions"]={name:{"diffuse_input":contribution(D,mask),"specular_input":contribution(F,mask),"smoothness":scalar_stats(S,mask),"reflectivity":scalar_stats(R,mask),"direct_diffuse":contribution(direct_diff,mask),"ambient_diffuse":contribution(ambient_diff,mask),"readability":contribution(readability_diff,mask),"equipment_shadow_fill":contribution(equipment_shadow_fill,mask),"environment_specular":contribution(env_spec,mask),"direct_specular":contribution(direct_spec,mask),"final_display":stats(mask)} for name,mask in metric_masks.items()}
    if region_aov is not None:
        metrics["cuirass_luminance"]=stats((region_aov[...,0]>.5)&(region_aov[...,1]<.5))
        metrics["skin_luminance"]=stats((region_aov[...,1]>.5)&(region_aov[...,0]<.5))
        metrics["tunic_luminance"]=stats((region_aov[...,2]>.5)&(region_aov[...,0]<.5)&(region_aov[...,1]<.5))
    return metrics


def main():
    OUT.mkdir(parents=True,exist_ok=True); AOV.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True); root,_=cu.import_unit("hastati"); cu.configure_camera(bpy.context.scene,FACET_AZIMUTH,30,8.5,12)
    scene=bpy.context.scene; scene.render.engine="BLENDER_EEVEE"; scene.render.resolution_x=scene.render.resolution_y=RESOLUTION; scene.render.resolution_percentage=100; scene.render.film_transparent=True
    scene.render.image_settings.file_format="OPEN_EXR"; scene.render.image_settings.color_mode="RGBA"; scene.render.image_settings.color_depth="32"; scene.render.image_settings.exr_codec="ZIP"
    scene.display_settings.display_device="sRGB"; scene.view_settings.view_transform="Raw"; scene.view_settings.look="None"; scene.view_settings.exposure=0; scene.view_settings.gamma=1
    previous=OUT/"runtime-parity-f03-pre-skin.png"
    current=OUT/"runtime-parity-f03.png"
    if current.exists() and not previous.exists(): previous.write_bytes(current.read_bytes())
    pre_shield=OUT/"runtime-parity-f03-pre-shield.png"
    if current.exists() and not pre_shield.exists(): pre_shield.write_bytes(current.read_bytes())
    pre_bridge=OUT/"runtime-parity-f03-pre-shared-backend.png"
    if current.exists() and not pre_bridge.exists(): pre_bridge.write_bytes(current.read_bytes())
    raw_passes=("basis_normal","basis_tangent","basis_bitangent","diffuse_raw","specular_raw","gloss_raw","normal_sample","normal_alpha","mask_raw","dirt_raw","dirt_alpha","dirt_mask_raw","dirt_mask_alpha","family")
    arrays={name:render_aov(scene,root,name) for name in raw_passes}; shade(scene,arrays)
    report={"format":"rome2aoe2.runtime-parity-proof","version":5,"facet":3,"azimuth":FACET_AZIMUTH,"resolution":RESOLUTION,"production_bridge":"Blender raw texture/basis AOVs -> shared runtime_material_preparation.py -> frozen lighting/display","raw_passes":list(raw_passes),"normal_uv":{"WeightedSkinDirtmap":"UVMap.001 / glTF TEXCOORD_1","other_supported_families":"UVMap / glTF TEXCOORD_0"},"coordinate_conversion":{"rome_to_blender":[[1,0,0],[0,0,-1],[0,1,0]],"instance_rotation":"identity in captured target draws","camera_yaw_adjustment":"none"},"material_paths":["Weighted","WeightedDirtmap","WeightedSkinDirtmap","DecalDirtmap"],"material_lighting_routes":{"Weighted":"event-1915 standard","WeightedDirtmap":"event-1915 standard","WeightedSkinDirtmap":"event-1926 skin","DecalDirtmap":"event-1915 standard"},"unsupported_paths":["DefaultMaterial exact runtime permutations"],"skin_dirt_instance_offset":"generic zero offset with captured UV scale 4; no Hastati-specific values","decal_dirt_instance_offset":"generic zero offset with captured UV scale 1; no Hastati-specific values","decal_array_state":"captured shield selection has zero active decal alpha; generic decal equations are recovered but contribute zero for this state","ssao":"captured neutral; omitted","shadows":"omitted in no-shadow base proof","bloom":"omitted","tone":{"log_black":-3,"log_white":1.1630859375,"white":15.5625,"brightness":1.2,"gamma":.5,"matrix":[.964706,.996078,1]},"output":"runtime-parity-f03.png","bridge_before":"runtime-parity-f03-pre-shared-backend.png"}
    (OUT/"report.json").write_text(json.dumps(report,indent=2)+"\n")


if __name__=="__main__": main()
