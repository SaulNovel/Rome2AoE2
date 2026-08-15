"""Package the frozen full-idle SLD pair into the stable Hastati dev test."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "third_party" / "python-deps"))
sys.path.insert(0, str(ROOT / "third_party" / "AoE2ScenarioParser"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from aoe2_genie_tooling import GenieWorkspace
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dat", required=True)
    parser.add_argument("--source-scenario", required=True)
    parser.add_argument("--sld-x1", required=True)
    parser.add_argument("--sld-x2", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    output = Path(args.output_root)
    mod = output / "Rome2AoE2 Hastati Dev Test"
    graphics = mod / "resources" / "_common" / "drs" / "graphics"
    dat_path = mod / "resources" / "_common" / "dat" / "empires2_x2_p1.dat"
    graphics.mkdir(parents=True, exist_ok=True)
    dat_path.parent.mkdir(parents=True, exist_ok=True)

    workspace = GenieWorkspace.load(Path(args.source_dat))
    militia = workspace.unit_manager.get(74)
    militia_state = (militia.name, militia.standing_sprite_id1, militia.standing_sprite_id2)
    clone = workspace.unit_manager.clone_into(2081, 74, on_conflict="error", fill_gaps="placeholder")
    clone.name = "Rome II Hastati full idle SLD"
    graphic = workspace.graphic_manager.add_graphic(
        "rome2aoe2_hastati_test", name="Hastati full idle SLD main-only",
        frame_count=67, angle_count=16, frame_duration=1 / 24,
    )
    clone.standing_sprite_id1 = clone.standing_sprite_id2 = graphic.id
    workspace.save(dat_path)
    written = GenieWorkspace.load(dat_path)
    written_militia = written.unit_manager.get(74)
    if (written_militia.name, written_militia.standing_sprite_id1, written_militia.standing_sprite_id2) != militia_state:
        raise RuntimeError("packaging changed vanilla Militia 74")
    written_clone = written.unit_manager.get(2081)
    written_graphic = written.graphic_manager.get(written_clone.standing_sprite_id1)
    if (written_graphic.frame_count, written_graphic.angle_count) != (67, 16):
        raise RuntimeError("packaging lost full-idle frame/facet metadata")
    if abs(written_graphic.frame_duration - 1 / 24) > 1e-7:
        raise RuntimeError("packaging lost 24 FPS timing")

    assets = []
    for zoom, source in (("x1", Path(args.sld_x1)), ("x2", Path(args.sld_x2))):
        destination = graphics / f"rome2aoe2_hastati_test_{zoom}.sld"
        shutil.copy2(source, destination)
        assets.append({"zoom": zoom, "path": str(destination), "sha256": digest(destination)})
    scenario = output / "Rome2AoE2HastatiDevTest.aoe2scenario"
    document = AoE2DEScenario.from_file(str(Path(args.source_scenario)))
    document.unit_manager.add_unit(player=1, unit_const=74, x=8, y=10, rotation=0)
    document.unit_manager.add_unit(player=1, unit_const=2081, x=14, y=10, rotation=0)
    document.write_to_file(str(scenario))
    (mod / "info.json").write_text(json.dumps({
        "Author": "Rome2AoE2", "CacheStatus": 0,
        "Title": "Rome2AoE2 Hastati Dev Test",
        "Description": "Frozen-scale 67 x 16 Hastati idle; native main-colour-only SLD x1/x2.",
    }, indent=2) + "\n", encoding="utf-8")
    report = {
        "format": "rome2aoe2.full-idle-sld-package", "version": 1,
        "unit_id": 2081, "graphic_id": graphic.id, "graphic_stem": "rome2aoe2_hastati_test",
        "frame_count": 67, "facet_count": 16, "total_sld_frames": 1072,
        "frame_duration_seconds": 1 / 24, "main_colour_only": True,
        "mod": str(mod), "dat": str(dat_path), "scenario": str(scenario), "assets": assets,
    }
    (output / "package-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
