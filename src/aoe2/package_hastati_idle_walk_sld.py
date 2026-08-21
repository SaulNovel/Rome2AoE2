"""Package approved Hastati idle/walk/attack/death SLDs into the stable dev test."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "third_party/python-deps"), str(ROOT / "third_party/AoE2ScenarioParser")]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from aoe2_genie_tooling import GenieWorkspace
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario


RUNTIME_FIELDS = (
    "force_player_color", "layer", "color_table", "transparent_selection",
    "speed_mult", "replay_delay", "sequence_type", "mirroring_mode",
)

APPROVED_GRAPHIC_IDS = (17068, 17069, 17070, 17071)
APPROVED_CORPSE_UNIT_ID = 152


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clone_graphic(workspace, reference, stem, name, frames, duration):
    return workspace.graphic_manager.add_graphic(
        stem, name=name, frame_count=frames, angle_count=16, frame_duration=duration,
        old_color_flag=reference.force_player_color, layer=reference.layer,
        force_player_color=reference.color_table,
        transparent_selection=reference.transparent_selection,
        replay_delay=reference.replay_delay, sequence_type=reference.sequence_type,
        mirroring_mode=reference.mirroring_mode,
    )


def valid_graphic(workspace, graphic_id):
    return 0 <= graphic_id < len(workspace.dat.sprites) and workspace.dat.sprites[graphic_id] is not None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dat", type=Path, required=True)
    parser.add_argument("--source-scenario", type=Path, required=True)
    parser.add_argument("--idle-x1", type=Path, required=True)
    parser.add_argument("--idle-x2", type=Path, required=True)
    parser.add_argument("--walk-x1", type=Path, required=True)
    parser.add_argument("--walk-x2", type=Path, required=True)
    # Attack SLDs are optional so the pre-approved idle+walk build remains a valid call.
    parser.add_argument("--attack-x1", type=Path)
    parser.add_argument("--attack-x2", type=Path)
    parser.add_argument("--death-x1", type=Path)
    parser.add_argument("--death-x2", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--walk-cycle-duration", type=float, default=1.1)
    parser.add_argument("--attack-cycle-duration", type=float, default=1.3,
                        help="Animate master cycle / 27 native samples per the approved sws_sync_atk_005 timing")
    parser.add_argument("--death-frame-duration", type=float, default=1 / 15,
                        help="Per-sample cadence for the 33-frame native death (do not divide span by samples)")
    args = parser.parse_args()

    attack_requested = args.attack_x1 is not None or args.attack_x2 is not None
    if attack_requested and (args.attack_x1 is None or args.attack_x2 is None):
        raise RuntimeError("--attack-x1 and --attack-x2 must be provided together")
    death_requested = args.death_x1 is not None or args.death_x2 is not None
    if death_requested and (args.death_x1 is None or args.death_x2 is None):
        raise RuntimeError("--death-x1 and --death-x2 must be provided together")
    if death_requested and not attack_requested:
        raise RuntimeError("approved death package requires the approved attack assets")

    output = args.output_root
    mod = output / "Rome2AoE2 Hastati Dev Test"
    graphics = mod / "resources/_common/drs/graphics"
    dat_path = mod / "resources/_common/dat/empires2_x2_p1.dat"
    graphics.mkdir(parents=True, exist_ok=True)
    dat_path.parent.mkdir(parents=True, exist_ok=True)

    workspace = GenieWorkspace.load(args.source_dat)
    militia = workspace.unit_manager.get(74)
    vanilla_state = (militia.name, militia.standing_sprite_id1,
                     militia.standing_sprite_id2, militia.walking_graphic_id,
                     militia.attack_graphic_id, militia.dying_sprite_id, militia.dead_unit_id)
    idle_reference = workspace.dat.sprites[militia.standing_sprite_id1]
    walk_reference = workspace.dat.sprites[militia.walking_graphic_id]
    attack_reference = workspace.dat.sprites[militia.attack_graphic_id]
    death_reference = workspace.dat.sprites[militia.dying_sprite_id]
    if not valid_graphic(workspace, militia.attack_graphic_id):
        raise RuntimeError("militia has no usable attack graphic reference for metadata")
    if not valid_graphic(workspace, militia.dying_sprite_id):
        raise RuntimeError("militia has no usable death graphic reference for metadata")
    clone = workspace.unit_manager.clone_into(2081, 74, on_conflict="error", fill_gaps="placeholder")
    clone.name = "Rome II Hastati native idle + walk + attack + death"
    idle = clone_graphic(workspace, idle_reference, "rome2aoe2_hastati_test",
                         "Hastati approved native idle", 67, 1 / 24)
    walk_duration = args.walk_cycle_duration / 23
    walk = clone_graphic(workspace, walk_reference, "rome2aoe2_hastati_walk",
                         "Hastati AE-native sws_walk_162_cm", 23, walk_duration)
    clone.standing_sprite_id1 = clone.standing_sprite_id2 = idle.id
    clone.walking_graphic_id = walk.id

    attack = None
    attack_duration = 0.0
    if attack_requested:
        attack_duration = args.attack_cycle_duration / 27
        attack = clone_graphic(workspace, attack_reference, "rome2aoe2_hastati_attack",
                               "Hastati AE-native sws_sync_atk_005", 27, attack_duration)
        clone.attack_graphic_id = attack.id
    death = None
    if death_requested:
        death = clone_graphic(workspace, death_reference, "rome2aoe2_hastati_death",
                              "Hastati AE-native sws_cr_death_missile_004", 33,
                              args.death_frame_duration)
        clone.dying_sprite_id = death.id
        if (idle.id, walk.id, attack.id, death.id) != APPROVED_GRAPHIC_IDS:
            raise RuntimeError("approved idle/walk/attack/death graphic IDs changed")
        if clone.dead_unit_id != APPROVED_CORPSE_UNIT_ID:
            raise RuntimeError("approved Militia corpse unit inheritance changed")
    workspace.save(dat_path)

    written = GenieWorkspace.load(dat_path)
    written_militia = written.unit_manager.get(74)
    if (written_militia.name, written_militia.standing_sprite_id1,
            written_militia.standing_sprite_id2, written_militia.walking_graphic_id,
            written_militia.attack_graphic_id, written_militia.dying_sprite_id,
            written_militia.dead_unit_id) != vanilla_state:
        raise RuntimeError("packaging changed vanilla Militia 74")
    written_clone = written.unit_manager.get(2081)
    expected_idle_walk = (idle.id, idle.id, walk.id)
    if (written_clone.standing_sprite_id1, written_clone.standing_sprite_id2,
            written_clone.walking_graphic_id) != expected_idle_walk:
        raise RuntimeError("Hastati idle/walk graphic mapping did not survive DAT round trip")

    for graphic_id, expected, reference in ((idle.id, (67, 16, 1 / 24), idle_reference),
                                            (walk.id, (23, 16, walk_duration), walk_reference)):
        graphic = written.graphic_manager.get(graphic_id)
        if (graphic.frame_count, graphic.angle_count) != expected[:2] or abs(graphic.frame_duration - expected[2]) > 1e-7:
            raise RuntimeError(f"graphic {graphic_id} metadata mismatch")
        raw = written.dat.sprites[graphic_id]
        for field in RUNTIME_FIELDS:
            if getattr(raw, field) != getattr(reference, field):
                raise RuntimeError(f"graphic {graphic_id} lost inherited runtime field {field}")

    if attack_requested:
        if written_clone.attack_graphic_id != attack.id:
            raise RuntimeError("Hastati attack graphic mapping did not survive DAT round trip")
        attack_graphic = written.graphic_manager.get(attack.id)
        if (attack_graphic.frame_count, attack_graphic.angle_count) != (27, 16) or abs(attack_graphic.frame_duration - attack_duration) > 1e-7:
            raise RuntimeError("attack graphic metadata mismatch")
        attack_raw = written.dat.sprites[attack.id]
        for field in RUNTIME_FIELDS:
            if getattr(attack_raw, field) != getattr(attack_reference, field):
                raise RuntimeError(f"attack graphic {attack.id} lost inherited runtime field {field}")
    if death_requested:
        if written_clone.dying_sprite_id != death.id:
            raise RuntimeError("Hastati death graphic mapping did not survive DAT round trip")
        if written_clone.dead_unit_id != militia.dead_unit_id:
            raise RuntimeError("Hastati lost inherited vanilla infantry corpse replacement")
        death_graphic = written.graphic_manager.get(death.id)
        if (death_graphic.frame_count, death_graphic.angle_count) != (33, 16):
            raise RuntimeError("death graphic frame/facet metadata mismatch")
        if abs(death_graphic.frame_duration - args.death_frame_duration) > 1e-7:
            raise RuntimeError("death graphic frame duration mismatch")
        death_raw = written.dat.sprites[death.id]
        if (death_raw.sequence_type, death_raw.mirroring_mode, death_raw.layer,
                death_raw.replay_delay, death_raw.speed_mult) != (11, 6, 20, 0, 0):
            raise RuntimeError("approved death runtime metadata changed")
        for field in RUNTIME_FIELDS:
            if getattr(death_raw, field) != getattr(death_reference, field):
                raise RuntimeError(f"death graphic {death.id} lost inherited runtime field {field}")

    assets = []
    entries = (
        ("idle", "x1", args.idle_x1, "rome2aoe2_hastati_test_x1.sld"),
        ("idle", "x2", args.idle_x2, "rome2aoe2_hastati_test_x2.sld"),
        ("walk", "x1", args.walk_x1, "rome2aoe2_hastati_walk_x1.sld"),
        ("walk", "x2", args.walk_x2, "rome2aoe2_hastati_walk_x2.sld"),
    )
    if attack_requested:
        entries = entries + (
            ("attack", "x1", args.attack_x1, "rome2aoe2_hastati_attack_x1.sld"),
            ("attack", "x2", args.attack_x2, "rome2aoe2_hastati_attack_x2.sld"),
        )
    if death_requested:
        entries = entries + (
            ("death", "x1", args.death_x1, "rome2aoe2_hastati_death_x1.sld"),
            ("death", "x2", args.death_x2, "rome2aoe2_hastati_death_x2.sld"),
        )
    for animation, zoom, source, stem in entries:
        destination = graphics / stem
        shutil.copy2(source, destination)
        assets.append({"animation": animation, "zoom": zoom, "path": str(destination),
                       "sha256": digest(destination)})

    scenario = output / "Rome2AoE2HastatiDevTest.aoe2scenario"
    document = AoE2DEScenario.from_file(str(args.source_scenario))
    document.unit_manager.add_unit(player=1, unit_const=74, x=8, y=10, rotation=0)
    document.unit_manager.add_unit(player=1, unit_const=2081, x=14, y=10, rotation=0)
    document.write_to_file(str(scenario))
    (mod / "info.json").write_text(json.dumps({
        "Author": "Rome2AoE2", "CacheStatus": 0,
        "Title": "Rome2AoE2 Hastati Dev Test",
        "Description": "Approved native idle, walk, attack, and sws_cr_death_missile_004; x1/x2 SLD.",
    }, indent=2) + "\n", encoding="utf-8")
    report = {
        "format": "rome2aoe2.hastati-idle-walk-attack-death-package", "version": 1,
        "unit_id": 2081, "idle_graphic_id": idle.id, "walk_graphic_id": walk.id,
        "idle": {"frames": 67, "facets": 16, "frame_duration": 1 / 24,
                 "source_hashes": {"x1": digest(args.idle_x1), "x2": digest(args.idle_x2)}},
        "walk": {"clip": "sws_walk_162_cm", "frames": 23, "facets": 16,
                 "cycle_duration": args.walk_cycle_duration, "frame_duration": walk_duration,
                 "authoritative_path": "Asset Editor native glTF -> Blender imported Action unchanged"},
        "mod": str(mod), "dat": str(dat_path), "scenario": str(scenario), "assets": assets,
    }
    if attack_requested:
        report["attack"] = {
            "clip": "sws_sync_atk_005", "frames": 27, "facets": 16,
            "cycle_duration": args.attack_cycle_duration, "frame_duration": attack_duration,
            "authoritative_path": "Asset Editor native glTF -> Blender imported Action unchanged",
            "impact_sample_index": 10, "impact_phase": 10 / 26, "impact_source_seconds": 0.5,
        }
        report["attack_graphic_id"] = attack.id
    if death_requested:
        report["death"] = {
            "clip": "sws_cr_death_missile_004", "frames": 33, "facets": 16,
            "source_fps": 15, "source_pose_span_seconds": 32 / 15,
            "frame_duration": args.death_frame_duration,
            "aoe_sequence_duration": 33 * args.death_frame_duration,
            "sequence_type": death_reference.sequence_type,
            "mirroring_mode": death_reference.mirroring_mode,
            "render_layer": death_reference.layer,
            "replay_delay": death_reference.replay_delay,
            "speed_multiplier": death_reference.speed_mult,
            "dead_unit_id": written_clone.dead_unit_id,
            "terminal_policy": "Militia dying semantics; non-looping death then inherited dead-unit corpse",
            "authoritative_path": "Asset Editor native glTF -> Blender imported Action unchanged",
        }
        report["death_graphic_id"] = death.id
    output.mkdir(parents=True, exist_ok=True)
    (output / "package-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
