"""Package the approved 16-facet static shadow proof into the stable dev test."""

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
    reference = workspace.dat.sprites[militia.standing_sprite_id1]
    clone = workspace.unit_manager.clone_into(2081, 74, on_conflict="error", fill_gaps="placeholder")
    clone.name = "Rome II Hastati static SLD shadow gate"
    graphic = workspace.graphic_manager.add_graphic(
        "rome2aoe2_hastati_test", name="Hastati static SLD shadow gate",
        frame_count=1, angle_count=16, frame_duration=1.0,
        old_color_flag=reference.force_player_color, layer=reference.layer,
        force_player_color=reference.color_table,
        transparent_selection=reference.transparent_selection,
        replay_delay=reference.replay_delay, sequence_type=reference.sequence_type,
        mirroring_mode=reference.mirroring_mode,
    )
    clone.standing_sprite_id1 = clone.standing_sprite_id2 = graphic.id
    workspace.save(dat_path)
    written = GenieWorkspace.load(dat_path)
    if (written.unit_manager.get(74).name,
            written.unit_manager.get(74).standing_sprite_id1,
            written.unit_manager.get(74).standing_sprite_id2) != militia_state:
        raise RuntimeError("packaging changed vanilla Militia 74")
    written_unit = written.unit_manager.get(2081)
    written_graphic = written.dat.sprites[written_unit.standing_sprite_id1]
    if (written_graphic.num_frames, written_graphic.num_facets) != (1, 16):
        raise RuntimeError("static shadow DAT frame/facet mismatch")
    inherited = ("layer", "transparent_selection", "sequence_type", "mirroring_mode")
    for field in inherited:
        if getattr(written_graphic, field) != getattr(reference, field):
            raise RuntimeError(f"static shadow DAT lost inherited field {field}")

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
        "Description": "Approved fixed-studio frame-33 main + native SLD shadow gate, x1/x2.",
    }, indent=2) + "\n", encoding="utf-8")
    report = {
        "format": "rome2aoe2.static-shadow-runtime-package", "version": 1,
        "unit_id": 2081, "graphic_id": graphic.id,
        "graphic_stem": "rome2aoe2_hastati_test", "frame_count": 1,
        "facet_count": 16, "layers": ["main", "shadow"],
        "mod": str(mod), "scenario": str(scenario), "assets": assets,
        "manual_gates": ["UHD off resolves x1", "UHD on resolves x2"],
    }
    (output / "package-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
