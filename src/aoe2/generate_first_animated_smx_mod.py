"""Package the first complete animated SMX as standing graphic for unit 2081."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "third_party" / "python-deps"))
sys.path.insert(0, str(ROOT / "third_party" / "AoE2ScenarioParser"))
from aoe2_genie_tooling import GenieWorkspace
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

SOURCE_UNIT_ID = 74
UNIT_ID = 2081
STEM = "rome2aoe2_hastati_idle"


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dat", type=Path, required=True)
    parser.add_argument("--smx", type=Path, required=True)
    parser.add_argument("--smx-report", type=Path, required=True)
    parser.add_argument("--template-scenario", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main():
    args = arguments()
    smx = json.loads(args.smx_report.read_text(encoding="utf-8"))
    frames, facets = smx["frames_per_facet"], smx["facet_count"]
    duration = 1.0 / 24.0
    workspace = GenieWorkspace.load(args.source_dat)
    source = workspace.unit_manager.get(SOURCE_UNIT_ID)
    source_state = (source.name, source.standing_sprite_id1, source.standing_sprite_id2)
    if workspace.unit_manager.exists(UNIT_ID):
        raise ValueError("unit 2081 is already occupied in the source DAT")
    graphic = workspace.graphic_manager.add_graphic(
        STEM, name="Rome II Hastati Idle", frame_count=frames,
        angle_count=facets, frame_duration=duration)
    clone = workspace.unit_manager.clone_into(UNIT_ID, SOURCE_UNIT_ID, on_conflict="error", fill_gaps="placeholder")
    clone.name = "Rome II Hastati"
    clone.standing_sprite_id1 = graphic.id
    clone.standing_sprite_id2 = graphic.id
    mod = args.output_root / "Rome2AoE2 Generated Data Mod"
    dat = mod / "resources" / "_common" / "dat" / "empires2_x2_p1.dat"
    graphics = mod / "resources" / "_common" / "drs" / "graphics"
    dat.parent.mkdir(parents=True, exist_ok=True)
    graphics.mkdir(parents=True, exist_ok=True)
    workspace.save(dat)
    destination = graphics / f"{STEM}_x1.smx"
    shutil.copy2(args.smx, destination)
    (mod / "info.json").write_text(json.dumps({
        "Author": "Rome2AoE2", "CacheStatus": 0,
        "Description": "First complete animated Rome II Hastati SMX proof.",
        "Title": "Rome2AoE2 Generated Data Mod",
    }, indent=2) + "\n", encoding="utf-8")
    written = GenieWorkspace.load(dat)
    militia = written.unit_manager.get(SOURCE_UNIT_ID)
    unit = written.unit_manager.get(UNIT_ID)
    written_graphic = written.graphic_manager.get(unit.standing_sprite_id1)
    if (militia.name, militia.standing_sprite_id1, militia.standing_sprite_id2) != source_state:
        raise RuntimeError("Militia 74 changed")
    if (written_graphic.frame_count, written_graphic.angle_count) != (frames, facets):
        raise RuntimeError("written DAT graphic frame/facet mismatch")
    if abs(written_graphic.frame_duration - duration) > 1e-7:
        raise RuntimeError("written DAT graphic timing mismatch")
    scenario = AoE2DEScenario.from_file(str(args.template_scenario))
    placements = [(74, 1, 8.0, 10.0), (2081, 1, 12.0, 10.0)]
    for unit_id, player, x, y in placements:
        scenario.unit_manager.add_unit(player=player, unit_const=unit_id, x=x, y=y)
    scenario_path = args.output_root / "Rome2AoE2FirstAnimatedHastati.aoe2scenario"
    scenario.write_to_file(str(scenario_path))
    result = {
        "format": "rome2aoe2.first-animated-smx-mod", "version": 1,
        "source_unit_id": SOURCE_UNIT_ID, "unit_id": UNIT_ID,
        "graphic_id": graphic.id, "graphic_stem": STEM,
        "frame_count": frames, "facet_count": facets, "frame_duration_seconds": duration,
        "mod_root": str(mod), "dat": str(dat), "smx": str(destination),
        "scenario": str(scenario_path), "placements": placements,
    }
    (args.output_root / "package-report.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                                                          encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
