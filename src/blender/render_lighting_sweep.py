"""Render the controlled L00-L13 Praetorian lighting sweep.

Materials, chainmail C, pose, camera, exposure, textures, and geometry remain
identical. Only the explicitly reported world/sun/area-light definitions vary.
L00 calls the existing V4 environment and sun helpers unchanged.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build" / "local-integration" / "rome2" / "lighting-sweep"
BLEND_IN = ROOT / "build" / "local-integration" / "rome2" / "textured" / "sws_stand_textured.blend"
PROFILE_PATH = ROOT / "config" / "render_profiles" / "aoe2_de_infantry_v4_material_fidelity_candidate.json"
EXPOSURE = 0.65

sys.path.insert(0, str(ROOT / "src" / "blender"))
from render_rome2_v4_candidate import build_material, configure_camera, set_environment, setup_sun  # noqa: E402


def area(name, position, energy, size, color=(1.0, 1.0, 1.0)):
    return {"name": name, "type": "AREA", "position": list(position), "energy_watts": energy,
            "size": size, "color_linear_rgb": list(color)}


CANDIDATES = [
    {"id":"L00","name":"Current V4","description":"Unchanged V4 control.","world":{"mode":"v4_env3"},
     "sun":{"strength":2.6,"azimuth":135,"elevation":60,"angular_size":12},"areas":[]},
    {"id":"L01","name":"Neutral Sky","description":"Brighter neutral sky.","world":{"mode":"neutral","strength":1.45,"color":[0.82,0.84,0.86]},
     "sun":{"strength":2.6,"azimuth":135,"elevation":60,"angular_size":12},"areas":[]},
    {"id":"L02","name":"Sky Warm Ground","description":"Bright neutral upper light with warm ground bounce.","world":{"mode":"hemisphere","upper_strength":1.45,"upper_color":[0.82,0.84,0.86],"lower_strength":0.55,"lower_color":[0.34,0.23,0.15]},
     "sun":{"strength":2.6,"azimuth":135,"elevation":60,"angular_size":12},"areas":[]},
    {"id":"L03","name":"Soft Environment","description":"Very bright soft environment and weak sun.","world":{"mode":"neutral","strength":2.25,"color":[0.84,0.85,0.86]},
     "sun":{"strength":0.75,"azimuth":135,"elevation":60,"angular_size":25},"areas":[]},
    {"id":"L04","name":"Front Fill","description":"Current V4 plus one camera-side soft fill.","world":{"mode":"v4_env3"},
     "sun":{"strength":2.6,"azimuth":135,"elevation":60,"angular_size":12},"areas":[area("front_fill",(6,6,6),700,5.0)]},
    {"id":"L05","name":"Twin Front Fills","description":"Two broad camera-side fills.","world":{"mode":"v4_env3"},
     "sun":{"strength":2.6,"azimuth":135,"elevation":60,"angular_size":12},"areas":[area("front_left",(7,3,5),430,4.5),area("front_right",(3,7,5),430,4.5)]},
    {"id":"L06","name":"Three Point","description":"Readable key, broad front fill, and restrained rim.","world":{"mode":"neutral","strength":0.65,"color":[0.82,0.83,0.84]},
     "sun":{"strength":1.45,"azimuth":145,"elevation":58,"angular_size":16},"areas":[area("front_fill",(6,6,5),650,5.5),area("rear_rim",(-5,-3,6),320,3.0,(1.0,0.88,0.72))]},
    {"id":"L07","name":"Overhead Softbox","description":"Large high camera-side softbox, weak sun, broad environment.","world":{"mode":"neutral","strength":1.05,"color":[0.83,0.84,0.85]},
     "sun":{"strength":0.65,"azimuth":135,"elevation":60,"angular_size":25},"areas":[area("overhead_front",(4,4,9),1150,6.5)]},
    {"id":"L08","name":"Four Light Surround","description":"Dominant front-left plus three weaker broad surround lights.","world":{"mode":"neutral","strength":0.45,"color":[0.82,0.83,0.84]},
     "sun":{"strength":0.35,"azimuth":135,"elevation":60,"angular_size":25},"areas":[area("front_left",(7,3,5),520,4.5),area("front_right",(3,7,5),360,4.5),area("back_left",(-5,2,7),260,4.0),area("back_right",(2,-5,7),210,4.0)]},
    {"id":"L09","name":"Strong Key Fill","description":"Strong directional key with strong neutral fill.","world":{"mode":"neutral","strength":1.35,"color":[0.82,0.83,0.84]},
     "sun":{"strength":4.0,"azimuth":135,"elevation":60,"angular_size":8},"areas":[area("front_fill",(6,6,5),700,5.5)]},
    {"id":"L10","name":"Soft Key Fill","description":"Soft moderate sun with strong neutral fill.","world":{"mode":"neutral","strength":1.35,"color":[0.82,0.83,0.84]},
     "sun":{"strength":1.45,"azimuth":135,"elevation":60,"angular_size":30},"areas":[area("front_fill",(6,6,5),760,6.0)]},
    {"id":"L11","name":"Warm Key Neutral Fill","description":"Slightly warm key with neutral broad fill and environment.","world":{"mode":"neutral","strength":1.15,"color":[0.82,0.83,0.84]},
     "sun":{"strength":2.15,"azimuth":135,"elevation":60,"angular_size":16,"color":[1.0,0.78,0.58]},"areas":[area("front_fill",(6,6,5),620,5.5)]},
    {"id":"L12","name":"Studio Readable","description":"Diagnostic gameplay-readable studio upper bound.","world":{"mode":"neutral","strength":0.30,"color":[0.82,0.83,0.84]},
     "sun":{"strength":0.25,"azimuth":135,"elevation":60,"angular_size":30},"areas":[area("broad_key",(6,2,7),1350,5.5),area("front_fill",(5,7,4),950,6.5),area("rim",(-4,-4,6),300,3.0)]},
    {"id":"L13","name":"Almost Shadowless","description":"Extreme broad illumination with only weak directionality.","world":{"mode":"neutral","strength":2.60,"color":[0.84,0.85,0.86]},
     "sun":{"strength":0.20,"azimuth":135,"elevation":60,"angular_size":35},"areas":[area("huge_front",(6,6,6),1200,8.0)]},
]


def clear_lights(scene):
    for obj in list(scene.objects):
        if obj.type == "LIGHT": bpy.data.objects.remove(obj, do_unlink=True)


def set_world(scene, definition):
    if definition["mode"] == "v4_env3": return set_environment(scene, 3)
    if scene.world is None: scene.world = bpy.data.worlds.new("lighting_sweep_world")
    scene.world.use_nodes = True; nodes=scene.world.node_tree.nodes; links=scene.world.node_tree.links
    nodes.clear(); out=nodes.new("ShaderNodeOutputWorld"); bg=nodes.new("ShaderNodeBackground")
    if definition["mode"] == "neutral":
        bg.inputs["Color"].default_value=(*definition["color"],1); bg.inputs["Strength"].default_value=definition["strength"]
    else:
        tex=nodes.new("ShaderNodeTexCoord"); sep=nodes.new("ShaderNodeSeparateXYZ"); ramp=nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation="CONSTANT"; ramp.color_ramp.elements[0].position=.499
        lower=[v*definition["lower_strength"] for v in definition["lower_color"]]
        upper=[v*definition["upper_strength"] for v in definition["upper_color"]]
        ramp.color_ramp.elements[0].color=(*lower,1); ramp.color_ramp.elements[1].position=.5; ramp.color_ramp.elements[1].color=(*upper,1)
        links.new(tex.outputs["Normal"],sep.inputs["Vector"]); links.new(sep.outputs["Z"],ramp.inputs["Fac"]); links.new(ramp.outputs["Color"],bg.inputs["Color"])
        bg.inputs["Strength"].default_value=1.0
    links.new(bg.outputs["Background"],out.inputs["Surface"])


def add_sun(scene, definition):
    data=bpy.data.lights.new("sweep_sun","SUN"); obj=bpy.data.objects.new("sweep_sun",data); scene.collection.objects.link(obj)
    az=math.radians(definition["azimuth"]); el=math.radians(definition["elevation"])
    obj.location=(10*math.cos(el)*math.cos(az),10*math.cos(el)*math.sin(az),10*math.sin(el))
    obj.rotation_euler=(Vector((0,0,1))-obj.location).to_track_quat("-Z","Y").to_euler()
    data.energy=definition["strength"]; data.angle=math.radians(definition["angular_size"])
    if "color" in definition: data.color=definition["color"]


def add_area(scene, definition):
    data=bpy.data.lights.new(definition["name"],"AREA"); obj=bpy.data.objects.new(definition["name"],data); scene.collection.objects.link(obj)
    obj.location=definition["position"]; obj.rotation_euler=(Vector((0,0,0))-obj.location).to_track_quat("-Z","Y").to_euler()
    data.energy=definition["energy_watts"]; data.shape="DISK"; data.size=definition["size"]; data.color=definition["color_linear_rgb"]


def render(scene, path):
    scene.render.engine="CYCLES"; scene.cycles.samples=48; scene.cycles.use_denoising=False
    scene.render.resolution_x=800; scene.render.resolution_y=800; scene.render.resolution_percentage=100
    scene.render.film_transparent=True; scene.render.image_settings.file_format="PNG"; scene.render.image_settings.color_mode="RGBA"
    scene.view_settings.view_transform="Standard"; scene.view_settings.look="None"; scene.view_settings.exposure=EXPOSURE; scene.view_settings.gamma=1.0
    scene.render.filepath=str(path.resolve()); bpy.ops.render.render(write_still=True)


def run():
    OUT.mkdir(parents=True,exist_ok=True); profile=json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    (OUT/"lighting-definitions.json").write_text(json.dumps({"exposure":EXPOSURE,"candidates":CANDIDATES},indent=2,sort_keys=True)+"\n",encoding="utf-8")
    for candidate in CANDIDATES:
        bpy.ops.wm.open_mainfile(filepath=str(BLEND_IN.resolve())); scene=bpy.context.scene; scene.frame_set(0)
        configure_camera(scene,45.0,30.0,8.5,12.0)
        for mat in bpy.data.materials:
            if mat.use_nodes: build_material(mat,"C")
        clear_lights(scene); set_world(scene,candidate["world"])
        if candidate["id"] == "L00": setup_sun(scene,profile)
        else: add_sun(scene,candidate["sun"])
        for definition in candidate["areas"]: add_area(scene,definition)
        path=OUT/f'{candidate["id"]}.png'; render(scene,path); print(f'rendered {candidate["id"]}: {path}',flush=True)

if __name__ == "__main__": run()
