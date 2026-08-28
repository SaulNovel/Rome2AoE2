from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"build/python-deps/sld-authoring"),str(ROOT/"src"),str(ROOT/"third_party/python-deps")]
from aoe2.sld import LAYER_PLAYERCOLOR,parse_sld,serialize_sld
from aoe2_genie_tooling import GenieWorkspace
BASE=ROOT/"build/local-integration/rome2/tunic-semantic-color";MOD=BASE/"ROME2AOE2_HASTATI_TUNIC_SEMANTIC";G=MOD/"resources/_common/drs/graphics"
def main():
 p=json.loads((BASE/"hastati-tunic-semantic-report.json").read_text());cs=p["candidates"]
 assert [c["id"] for c in cs]==[f"R0{i}" for i in range(6)]
 assert len({c["unit_id"] for c in cs})==len({c["graphic_id"] for c in cs})==len({c["stem"] for c in cs})==6
 ws=GenieWorkspace.load(MOD/"resources/_common/dat/empires2_x2_p1.dat")
 for c in cs:
  gr=ws.graphic_manager.get(c["graphic_id"]);u=ws.unit_manager.get(c["unit_id"])
  assert (gr.angle_count,gr.frame_count,gr.file_name)==(16,1,c["stem"]) and u.standing_sprite_id1==gr.id
  for z,canvas,hot in (("x1",200,100),("x2",400,200)):
   raw=(G/f"{c['stem']}_{z}.sld").read_bytes();s=parse_sld(raw)
   assert serialize_sld(s)==raw and len(s.frames)==16 and [f.frame_index for f in s.frames]==list(range(16))
   assert all((f.canvas_width,f.canvas_height,f.center_x,f.center_y)==(canvas,canvas,hot,hot) for f in s.frames)
   assert not any(f.frame_type&LAYER_PLAYERCOLOR for f in s.frames)
 assert p["source_trace"]["channel_remap"].startswith("identity") and p["source_trace"]["colors"]["C0"]=="A62416"
 assert p["mask_channel_measurements"]["R"]["mean"]>.5 and p["mask_channel_measurements"]["G"]["mean"]<.01 and p["mask_channel_measurements"]["B"]["mean"]<.01
 # BC1 must not be the semantic-color loss stage: R04 pre/decode chroma stays close.
 pre=p["pipeline_stages"]["E R04 x2 pre-SLD"]["chroma"];post=p["pipeline_stages"]["F R04 decoded x2"]["chroma"];assert abs(pre-post)<.005
 assert (MOD/"resources/_common/dat/empires2_x2_p1.dat").is_file() and not (MOD/"mod").exists()
 for n in ("hastati-tunic-color-pipeline.png","hastati-tunic-semantic-color-uhd.png","hastati-tunic-semantic-color-4x.png","LEGEND.txt","Rome2HastatiTunicSemantic.aoe2scenario"):assert (BASE/n).is_file()
 print("HASTATI TUNIC SEMANTIC PASS")
if __name__=="__main__":main()
