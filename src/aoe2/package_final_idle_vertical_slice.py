"""Package paired x1/x2 Hastati idle SMPX files, DAT unit 2081, and scenario."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "third_party/python-deps"))
sys.path.insert(0, str(ROOT / "third_party/AoE2ScenarioParser"))
from aoe2_genie_tooling import GenieWorkspace
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

SOURCE_UNIT = 74
UNIT = 2081
STEM = "rome2aoe2_hastati_idle"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dat", type=Path, required=True)
    parser.add_argument("--smx-report", type=Path, required=True)
    parser.add_argument("--template-scenario", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    smx = json.loads(args.smx_report.read_text(encoding="utf-8"))
    outputs = {item["zoom"]: Path(item["smx"]) for item in smx["outputs"]}
    if set(outputs) != {"x1", "x2"}:
        raise RuntimeError("paired x1/x2 SMPX outputs are required")
    workspace = GenieWorkspace.load(args.source_dat)
    source = workspace.unit_manager.get(SOURCE_UNIT)
    source_state = (source.name, source.standing_sprite_id1, source.standing_sprite_id2)
    if workspace.unit_manager.exists(UNIT):
        raise RuntimeError("unit 2081 is occupied in source DAT")
    graphic = workspace.graphic_manager.add_graphic(
        f"{STEM}_x1", name="Rome II Hastati Final Idle", frame_count=67,
        angle_count=16, frame_duration=1 / 24)
    unit = workspace.unit_manager.clone_into(UNIT, SOURCE_UNIT, on_conflict="error", fill_gaps="placeholder")
    unit.name = "Rome II Hastati"
    unit.standing_sprite_id1 = unit.standing_sprite_id2 = graphic.id
    mod = args.output_root / "Rome2AoE2 Final Hastati Idle Data Mod"
    dat = mod / "resources/_common/dat/empires2_x2_p1.dat"
    graphics = mod / "resources/_common/drs/graphics"
    dat.parent.mkdir(parents=True, exist_ok=True)
    graphics.mkdir(parents=True, exist_ok=True)
    workspace.save(dat)
    installed = {}
    for zoom, source_path in outputs.items():
        destination = graphics / f"{STEM}_{zoom}.smx"
        shutil.copy2(source_path, destination)
        installed[zoom] = str(destination)
    (mod / "info.json").write_text(json.dumps({
        "Author": "Rome2AoE2", "CacheStatus": 0,
        "Description": "Final-quality corrected Rome II Hastati complete idle, normal and UHD.",
        "Title": "Rome2AoE2 Final Hastati Idle",
    }, indent=2) + "\n", encoding="utf-8")
    written = GenieWorkspace.load(dat)
    militia = written.unit_manager.get(SOURCE_UNIT)
    check = written.unit_manager.get(UNIT)
    check_graphic = written.graphic_manager.get(check.standing_sprite_id1)
    if (militia.name, militia.standing_sprite_id1, militia.standing_sprite_id2) != source_state:
        raise RuntimeError("Militia 74 changed")
    if (check_graphic.frame_count, check_graphic.angle_count) != (67, 16):
        raise RuntimeError("DAT frame/facet mismatch")
    if abs(check_graphic.frame_duration - 1 / 24) > 1e-7:
        raise RuntimeError("DAT frame duration mismatch")
    scenario = AoE2DEScenario.from_file(str(args.template_scenario))
    placements = [(74, 1, 8.0, 10.0), (2081, 1, 14.0, 10.0)]
    for unit_id, player, x, y in placements:
        scenario.unit_manager.add_unit(player=player, unit_const=unit_id, x=x, y=y)
    scenario_path = args.output_root / "Rome2AoE2FinalHastatiIdle.aoe2scenario"
    scenario.write_to_file(str(scenario_path))
    result = {"format": "rome2aoe2.final-idle-package", "version": 1,
              "source_unit_id": SOURCE_UNIT, "unit_id": UNIT, "graphic_id": graphic.id,
              "graphic_stem": STEM, "frame_count": 67, "facet_count": 16,
              "frame_duration_seconds": 1 / 24, "militia_unchanged": True,
              "mod_root": str(mod), "dat": str(dat), "graphics": installed,
              "scenario": str(scenario_path), "placements": placements,
              "enhanced_graphics_ready": True}
    (args.output_root / "package-report.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
