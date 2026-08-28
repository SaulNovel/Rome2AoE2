"""Build a one-frame-per-direction SMPX v2 runtime control from frozen frames."""
from __future__ import annotations
import hashlib, json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path[:0] = [str(ROOT / "build/python-deps/pillow"), str(ROOT / "third_party/python-deps")]
from PIL import Image
from aoe2_genie_tooling import GenieWorkspace
from smx_staging import make_pillow_palette, read_jasc_palette
from smx_v2 import write_smx_v2

BASE = ROOT / "build/local-integration/final-idle-vertical-slice"
OUT = ROOT / "build/local-integration/dat-crash-isolation/Rome2AoE2 Isolation F Hastati SMPX V2 Control"
DAT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\dat\empires2_x2_p1.dat")
PAL = Path(r"C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\Tools_Builds\Sprites\_palettes\b_scen.pal")
STEM = "rome2aoe2_hastati_v2_control_x1"

report = json.loads((BASE / "full-render-report.json").read_text(encoding="utf-8"))
records = {(r["direction"], r["output_frame"]): r for r in report["records"]}
images = [Image.open(records[(direction, 0)]["x1"]).convert("RGBA") for direction in range(16)]
palette = make_pillow_palette(read_jasc_palette(PAL))
graphics = OUT / "resources/_common/drs/graphics"
smx = graphics / f"{STEM}.smx"
smx_report = write_smx_v2(smx, images, palette, tuple(report["hotspots"]["0"]["x1"]))

ws = GenieWorkspace.load(DAT)
u = ws.unit_manager.clone_into(2081, 74, on_conflict="error", fill_gaps="placeholder")
u.name = "Rome II Hastati SMPX v2 control"
g = ws.graphic_manager.copy(ws.unit_manager.get(74).standing_sprite_id1, 17068)
g.name = "Rome II Hastati SMPX v2 control"
g.file_name = STEM
g.frame_count = 1
g.angle_count = 16
g.frame_duration = 1.0
g.speed_multiplier = 0.0
g.replay_delay = 0.0
g.sequence_type = 0
g.mirroring_mode = 0
u.standing_sprite_id1 = u.standing_sprite_id2 = 17068
dat_out = OUT / "resources/_common/dat/empires2_x2_p1.dat"
dat_out.parent.mkdir(parents=True, exist_ok=True)
ws.save(dat_out)
scenario = OUT / "Rome2AoE2IsolationF.aoe2scenario"
shutil.copy2(BASE / "package/Rome2AoE2FinalHastatiIdle.aoe2scenario", scenario)
(OUT / "info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,
 "Title":"Rome2AoE2 Isolation F Hastati SMPX V2 Control",
 "Description":"Frozen Hastati frame, SMPX v2 decoder control."}, indent=2)+"\n")
result={"smx":str(smx),"smx_sha256":hashlib.sha256(smx.read_bytes()).hexdigest(),
        "smx_header":smx_report,"dat":str(dat_out),"scenario":str(scenario),
        "frames_per_facet":1,"facets":16,"source":"frozen final x1 frame 0 of each direction"}
(OUT/"control-report.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result,indent=2))
