"""Package the one-frame main-only SLD gate using the proven isolation unit."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "third_party" / "python-deps"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from aoe2_genie_tooling import GenieWorkspace


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
    mod = output / "Rome2AoE2 Static Hastati SLD Main Gate"
    graphics = mod / "resources" / "_common" / "drs" / "graphics"
    dat_path = mod / "resources" / "_common" / "dat" / "empires2_x2_p1.dat"
    graphics.mkdir(parents=True, exist_ok=True)
    dat_path.parent.mkdir(parents=True, exist_ok=True)

    workspace = GenieWorkspace.load(Path(args.source_dat))
    militia = workspace.unit_manager.get(74)
    militia_state = (militia.name, militia.standing_sprite_id1, militia.standing_sprite_id2)
    clone = workspace.unit_manager.clone_into(2081, 74, on_conflict="error", fill_gaps="placeholder")
    clone.name = "Rome II Hastati static SLD main gate"
    graphic = workspace.graphic_manager.add_graphic(
        "rome2aoe2_hastati_test", name="Hastati static SLD main gate",
        frame_count=1, angle_count=1, frame_duration=1.0,
    )
    clone.standing_sprite_id1 = clone.standing_sprite_id2 = graphic.id
    workspace.save(dat_path)
    written = GenieWorkspace.load(dat_path)
    written_militia = written.unit_manager.get(74)
    if (written_militia.name, written_militia.standing_sprite_id1, written_militia.standing_sprite_id2) != militia_state:
        raise RuntimeError("packaging changed vanilla Militia 74")
    written_clone = written.unit_manager.get(2081)
    if (written_clone.standing_sprite_id1, written_clone.standing_sprite_id2) != (graphic.id, graphic.id):
        raise RuntimeError("packaging lost static Hastati standing mapping")

    destinations = []
    for zoom, source in (("x1", Path(args.sld_x1)), ("x2", Path(args.sld_x2))):
        destination = graphics / f"rome2aoe2_hastati_test_{zoom}.sld"
        shutil.copy2(source, destination)
        destinations.append({"zoom": zoom, "path": str(destination), "sha256": digest(destination)})
    scenario = output / "Rome2AoE2StaticHastatiSLDMainGate.aoe2scenario"
    shutil.copy2(Path(args.source_scenario), scenario)
    (mod / "info.json").write_text(json.dumps({
        "Author": "Rome2AoE2", "CacheStatus": 0,
        "Title": "Rome2AoE2 Static Hastati SLD Main Gate",
        "Description": "One frozen accepted frame; native main-colour-only SLD x1/x2 transport gate.",
    }, indent=2) + "\n", encoding="utf-8")
    report = {
        "format": "rome2aoe2.static-sld-main-gate-package", "version": 1,
        "unit_id": 2081, "graphic_id": graphic.id, "graphic_stem": "rome2aoe2_hastati_test",
        "frame_count": 1, "facet_count": 1, "main_colour_only": True,
        "mod": str(mod), "dat": str(dat_path), "scenario": str(scenario), "assets": destinations,
        "required_tests": ["UHD off resolves x1", "UHD on resolves x2"],
    }
    (output / "package-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
