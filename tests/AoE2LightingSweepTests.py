"""Validate the installed-ready L00-L13 lighting sweep."""
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"third_party"/"python-deps")]
V=ROOT/"build"/"python-deps"/"sld-authoring"
if V.is_dir(): sys.path.insert(0,str(V))
from aoe2.sld import parse_sld,serialize_sld  # noqa: E402
from aoe2.analyze_sld import decode_frame  # noqa: E402
from aoe2_genie_tooling import GenieWorkspace  # noqa: E402

SWEEP=ROOT/"build"/"local-integration"/"rome2"/"lighting-sweep"
REPORT=SWEEP/"lighting-sweep.json"; MOD=SWEEP/"ROME2AOE2_LIGHTING_SWEEP"
GRAPHICS=MOD/"resources"/"_common"/"drs"/"graphics"; DAT=SWEEP/"lighting_sweep.dat"

def candidates(): return json.loads(REPORT.read_text(encoding="utf-8"))["candidates"]
def load(candidate,zoom):
    data=(GRAPHICS/f'{candidate["stem"]}_{zoom}.sld').read_bytes(); sld=parse_sld(data)
    assert serialize_sld(sld)==data
    return sld
def nearest_alpha(image,x,y):
    points=[(i%image.width,i//image.width) for i,p in enumerate(image.convert("RGBA").getdata()) if p[3]>8]
    assert points
    return min((px-x)**2+(py-y)**2 for px,py in points)

def test_candidate_identifiers_unique():
    cs=candidates(); assert [c["id"] for c in cs]==[f"L{i:02d}" for i in range(14)]
    for key in ("unit_id","graphic_id","stem","display_name"): assert len({c[key] for c in cs})==14
def test_all_slds_strict_and_anchored():
    for c in candidates():
        for zoom,canvas,hotspot,scale in (("x1",200,(100,100),1),("x2",400,(200,200),2)):
            sld=load(c,zoom); assert len(sld.frames)==16; assert [f.frame_index for f in sld.frames]==list(range(16))
            assert all((f.canvas_width,f.canvas_height)==(canvas,canvas) for f in sld.frames)
            assert all((f.center_x,f.center_y)==hotspot for f in sld.frames)
            # Every duplicated frame has main and shadow contact near the same logical feet anchor.
            for index in range(16):
                main,shadow=decode_frame(sld,index)
                assert nearest_alpha(main,*hotspot)<=(4*scale)**2
                assert nearest_alpha(shadow,*hotspot)<=(4*scale)**2
def test_x1_x2_logical_equivalence():
    for c in candidates():
        a,b=load(c,"x1"),load(c,"x2")
        for f1,f2 in zip(a.frames,b.frames):
            assert (f2.center_x,f2.center_y)==(2*f1.center_x,2*f1.center_y)
            for l1,l2 in zip(f1.layers,f2.layers):
                if l1.layer_type in (1,2):
                    for x,y in zip((l1.offset_x1,l1.offset_y1,l1.offset_x2,l1.offset_y2),(l2.offset_x1,l2.offset_y1,l2.offset_x2,l2.offset_y2)):
                        assert abs(y-2*x)<=8
def test_dat_semantics_and_names():
    workspace=GenieWorkspace.load(DAT)
    for c in candidates():
        unit=workspace.unit_manager.get(c["unit_id"]); assert unit.name==c["display_name"]
        assert unit.standing_sprite_id1==unit.standing_sprite_id2==c["graphic_id"]
        graphic=workspace.graphic_manager.get(c["graphic_id"]); assert graphic.file_name==c["stem"]
        assert graphic.angle_count==16 and graphic.frame_count==1
def test_canonical_flat_mod_layout():
    files={p.relative_to(MOD).as_posix() for p in MOD.rglob("*") if p.is_file()}
    assert "info.json" in files and "resources/_common/dat/empires2_x2_p1.dat" in files
    assert not any(path.startswith("mod/") for path in files)
    assert not any(path.endswith("lighting_sweep.dat") for path in files)
    assert len([p for p in files if p.endswith(".sld")])==28
def test_fixed_inputs_and_no_proprietary_outputs():
    script=(ROOT/"src"/"blender"/"render_lighting_sweep.py").read_text(encoding="utf-8")
    assert 'build_material(mat,"C")' in script and "EXPOSURE = 0.65" in script
    assert "configure_camera(scene,45.0,30.0,8.5,12.0)" in script and "scene.frame_set(0)" in script
    assert not any(p.suffix.lower() in {".dat",".sld",".png",".aoe2scenario"} for p in ROOT.glob("src/**/*"))
    gi=(ROOT/".gitignore").read_text(encoding="utf-8"); assert "build/" in gi and "test_data/empires2_x2_p1.dat" in gi

def run_all():
    tests=[test_candidate_identifiers_unique,test_all_slds_strict_and_anchored,test_x1_x2_logical_equivalence,test_dat_semantics_and_names,test_canonical_flat_mod_layout,test_fixed_inputs_and_no_proprietary_outputs]
    for test in tests: test(); print(f"ok - {test.__name__}")
    print(f"PASS ({len(tests)} checks)")
if __name__=="__main__": run_all()
