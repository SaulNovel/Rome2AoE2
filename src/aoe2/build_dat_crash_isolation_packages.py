"""Build one-variable-at-a-time DAT/graphic crash-isolation packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "third_party/python-deps"))
from aoe2_genie_tooling import GenieWorkspace

UNIT_ID = 2081
SOURCE_ID = 74
GRAPHIC_ID = 17068
STEM = "rome2aoe2_hastati_idle"
KNOWN_GOOD_GRAPHIC_ID = 2889  # Paladin (Idle), 45 frames x 16 facets.


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(source_dat, output_root, label, mode, x1=None, x2=None):
    workspace = GenieWorkspace.load(source_dat)
    militia = workspace.unit_manager.get(SOURCE_ID)
    militia_state = (militia.name, militia.standing_sprite_id1, militia.standing_sprite_id2)
    militia_graphic_id = militia.standing_sprite_id1
    militia_graphic = workspace.graphic_manager.get(militia_graphic_id)
    if workspace.unit_manager.exists(UNIT_ID):
        raise RuntimeError("unit 2081 is occupied")
    clone = workspace.unit_manager.clone_into(UNIT_ID, SOURCE_ID, on_conflict="error", fill_gaps="placeholder")
    clone.name = f"Rome II Hastati isolation {label}"
    graphic = None
    if mode in ("vanilla_graphic_copy", "custom"):
        graphic = workspace.graphic_manager.copy(militia_graphic_id, GRAPHIC_ID)
        if mode == "custom":
            graphic.name = "Rome II Hastati Final Idle"
            # AoE2 DAT graphics name the normal asset explicitly with _x1;
            # Enhanced Graphics substitutes the paired _x2 asset at runtime.
            graphic.file_name = f"{STEM}_x1"
            graphic.frame_count = 67
            graphic.angle_count = 16
            graphic.frame_duration = 1 / 24
            graphic.speed_multiplier = 0.0
            graphic.replay_delay = 0.0
            graphic.sequence_type = 0
            graphic.mirroring_mode = 0
        clone.standing_sprite_id1 = clone.standing_sprite_id2 = GRAPHIC_ID
    mod = output_root / f"Rome2AoE2 Isolation {label}"
    dat = mod / "resources/_common/dat/empires2_x2_p1.dat"
    graphics_dir = mod / "resources/_common/drs/graphics"
    dat.parent.mkdir(parents=True, exist_ok=True)
    graphics_dir.mkdir(parents=True, exist_ok=True)
    workspace.save(dat)
    installed = {}
    if x1:
        destination = graphics_dir / f"{STEM}_x1.smx"
        shutil.copy2(x1, destination)
        installed["x1"] = str(destination)
    if x2:
        destination = graphics_dir / f"{STEM}_x2.smx"
        shutil.copy2(x2, destination)
        installed["x2"] = str(destination)
    (mod / "info.json").write_text(json.dumps({
        "Author": "Rome2AoE2", "CacheStatus": 0,
        "Title": f"Rome2AoE2 Isolation {label}",
        "Description": f"Crash isolation package {label}; test only this data mod.",
    }, indent=2) + "\n", encoding="utf-8")
    check = GenieWorkspace.load(dat)
    written_militia = check.unit_manager.get(SOURCE_ID)
    written_clone = check.unit_manager.get(UNIT_ID)
    if (written_militia.name, written_militia.standing_sprite_id1,
            written_militia.standing_sprite_id2) != militia_state:
        raise RuntimeError("Militia 74 changed")
    result = {
        "label": label, "mode": mode, "mod_root": str(mod), "dat": str(dat),
        "dat_size": dat.stat().st_size, "dat_sha256": digest(dat),
        "source_dat_sha256": digest(source_dat), "militia_unchanged": True,
        "unit_id": UNIT_ID, "unit_standing_graphics": [written_clone.standing_sprite_id1,
                                                          written_clone.standing_sprite_id2],
        "source_militia_graphic_id": militia_graphic_id,
        "graphic_id_added": GRAPHIC_ID if graphic else None,
        "graphic_file_name": check.graphic_manager.get(GRAPHIC_ID).file_name if graphic else None,
        "graphics_files": installed,
    }
    (output_root / f"package-{label.lower()}-report.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def roundtrip_control(source_dat, output_root):
    workspace = GenieWorkspace.load(source_dat)
    mod = output_root / "Rome2AoE2 Isolation R Roundtrip"
    dat = mod / "resources/_common/dat/empires2_x2_p1.dat"
    dat.parent.mkdir(parents=True, exist_ok=True)
    workspace.save(dat)
    (mod / "info.json").write_text(json.dumps({
        "Author": "Rome2AoE2", "CacheStatus": 0,
        "Title": "Rome2AoE2 Isolation R Roundtrip",
        "Description": "No-edit DAT parser/writer roundtrip control.",
    }, indent=2) + "\n", encoding="utf-8")
    GenieWorkspace.load(dat)
    result = {"label": "R Roundtrip", "mode": "no_edit_roundtrip", "mod_root": str(mod),
              "dat": str(dat), "dat_size": dat.stat().st_size, "dat_sha256": digest(dat),
              "source_dat_sha256": digest(source_dat)}
    (output_root / "package-r-roundtrip-report.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def known_good_smx_control(source_dat, output_root, known_good_x1):
    """Resolve a proven SMPX v2 asset through a current-DAT graphic record."""
    workspace = GenieWorkspace.load(source_dat)
    militia = workspace.unit_manager.get(SOURCE_ID)
    militia_state = (militia.name, militia.standing_sprite_id1, militia.standing_sprite_id2)
    clone = workspace.unit_manager.clone_into(
        UNIT_ID, SOURCE_ID, on_conflict="error", fill_gaps="placeholder")
    clone.name = "Rome II Hastati isolation E known-good SMPX v2"
    reference = workspace.graphic_manager.get(KNOWN_GOOD_GRAPHIC_ID)
    clone.standing_sprite_id1 = clone.standing_sprite_id2 = KNOWN_GOOD_GRAPHIC_ID
    mod = output_root / "Rome2AoE2 Isolation E Known Good SMPX V2"
    dat = mod / "resources/_common/dat/empires2_x2_p1.dat"
    graphics_dir = mod / "resources/_common/drs/graphics"
    dat.parent.mkdir(parents=True, exist_ok=True)
    graphics_dir.mkdir(parents=True, exist_ok=True)
    workspace.save(dat)
    destination = graphics_dir / f"{reference.file_name}.smx"
    shutil.copy2(known_good_x1, destination)
    # Make this decoder control self-contained instead of relying on a
    # scenario generated for a different DAT package.
    source_scenario = (ROOT / "build/local-integration/final-idle-vertical-slice/package/"
                       "Rome2AoE2FinalHastatiIdle.aoe2scenario")
    scenario_path = mod / "Rome2AoE2IsolationE.aoe2scenario"
    shutil.copy2(source_scenario, scenario_path)
    (mod / "info.json").write_text(json.dumps({
        "Author": "Rome2AoE2", "CacheStatus": 0,
        "Title": "Rome2AoE2 Isolation E Known Good SMPX V2",
        "Description": "Known-good subscribed Paladin SMPX v2 decoder control.",
    }, indent=2) + "\n", encoding="utf-8")
    check = GenieWorkspace.load(dat)
    written_militia = check.unit_manager.get(SOURCE_ID)
    if (written_militia.name, written_militia.standing_sprite_id1,
            written_militia.standing_sprite_id2) != militia_state:
        raise RuntimeError("Militia 74 changed")
    result = {
        "label": "E Known Good SMPX V2", "mode": "known_good_smpx_v2",
        "mod_root": str(mod), "dat": str(dat), "dat_sha256": digest(dat),
        "unit_id": UNIT_ID, "graphic_id": KNOWN_GOOD_GRAPHIC_ID,
        "graphic_file_name": reference.file_name,
        "frame_count": reference.frame_count, "facet_count": reference.angle_count,
        "smx": str(destination), "smx_sha256": digest(destination),
        "scenario": str(scenario_path),
        "placements": [{"unit_id": SOURCE_ID, "x": 8.0, "y": 10.0},
                       {"unit_id": UNIT_ID, "x": 14.0, "y": 10.0}],
    }
    (output_root / "package-e-known-good-smx-v2-report.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-dat", type=Path, required=True)
    parser.add_argument("--fixture-dat", type=Path, required=True)
    parser.add_argument("--x1-smx", type=Path, required=True)
    parser.add_argument("--x2-smx", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--known-good-x1-smx", type=Path)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    raw = args.installed_dat.read_bytes()
    workspace = GenieWorkspace.load(args.installed_dat)
    comparison = {
        "installed": {"path": str(args.installed_dat), "size": len(raw),
                      "sha256": digest(args.installed_dat),
                      "compressed_prefix_bytes": raw[:8].hex(),
                      "parsed_file_version": workspace.dat.file_version.decode("ascii", errors="replace").rstrip("\0"),
                      "parser_target_version": str(workspace.target_version),
                      "unit_count": len(workspace.dat.civilizations[0].units),
                      "graphic_count": len(workspace.dat.sprites)},
        "fixture": {"path": str(args.fixture_dat), "size": args.fixture_dat.stat().st_size,
                    "sha256": digest(args.fixture_dat)},
    }
    comparison["byte_identical"] = comparison["installed"]["sha256"] == comparison["fixture"]["sha256"]
    (args.output_root / "dat-comparison.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    packages = [
        roundtrip_control(args.installed_dat, args.output_root),
        prepare(args.installed_dat, args.output_root, "A Clone Only", "clone_only"),
        prepare(args.installed_dat, args.output_root, "B Vanilla Graphic", "vanilla_graphic_copy"),
        prepare(args.installed_dat, args.output_root, "C X1 Only", "custom", args.x1_smx),
        prepare(args.installed_dat, args.output_root, "D X1 X2 UHD", "custom", args.x1_smx, args.x2_smx),
    ]
    if args.known_good_x1_smx:
        packages.append(known_good_smx_control(
            args.installed_dat, args.output_root, args.known_good_x1_smx))
    print(json.dumps({"comparison": comparison, "packages": packages}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
