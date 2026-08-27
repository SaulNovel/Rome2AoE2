"""Verify the installed complete Hastati DAT, SLD assets, and battle scenario."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "third_party/python-deps"), str(ROOT / "third_party/AoE2ScenarioParser")]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from aoe2_genie_tooling import GenieWorkspace
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario


ASSETS = {
    "idle": "rome2aoe2_hastati_test",
    "walk": "rome2aoe2_hastati_walk",
    "attack": "rome2aoe2_hastati_attack",
    "death": "rome2aoe2_hastati_death",
}
EXPECTED_GRAPHICS = {"idle": 17068, "walk": 17069, "attack": 17070, "death": 17071}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_install_paths(mod: Path) -> tuple[Path, Path]:
    """Derive the frozen install locations from an explicitly supplied mod path."""
    profile = mod.parents[2]
    return (
        profile / "mods/local/Rome2AoE2 Hastati Dev Test",
        profile / "resources/_common/scenario/Rome2AoE2HastatiDevTest.aoe2scenario",
    )


def verify(mod: Path, scenario_path: Path, source_mod: Path) -> dict:
    expected_mod, expected_scenario = expected_install_paths(mod)
    if mod != expected_mod or scenario_path != expected_scenario:
        raise RuntimeError("integration test is not installed at the frozen paths")

    dat_path = mod / "resources/_common/dat/empires2_x2_p1.dat"
    workspace = GenieWorkspace.load(dat_path)
    unit = workspace.unit_manager.get(2081)
    actual = {
        "idle": unit.standing_sprite_id1,
        "walk": unit.walking_graphic_id,
        "attack": unit.attack_graphic_id,
        "death": unit.dying_sprite_id,
    }
    if actual != EXPECTED_GRAPHICS or unit.standing_sprite_id2 != EXPECTED_GRAPHICS["idle"]:
        raise RuntimeError(f"approved unit graphic mappings changed: {actual}")
    if unit.dead_unit_id != 152:
        raise RuntimeError(f"approved corpse unit changed: {unit.dead_unit_id}")

    asset_hashes = {}
    for animation, stem in ASSETS.items():
        asset_hashes[animation] = {}
        for zoom in ("x1", "x2"):
            relative = Path("resources/_common/drs/graphics") / f"{stem}_{zoom}.sld"
            installed = mod / relative
            source = source_mod / relative
            if not installed.is_file() or not source.is_file():
                raise RuntimeError(f"missing approved {animation} {zoom} asset")
            installed_hash = sha256(installed)
            if installed_hash != sha256(source):
                raise RuntimeError(f"installed {animation} {zoom} hash differs from approved source")
            asset_hashes[animation][zoom] = installed_hash

    scenario = AoE2DEScenario.from_file(str(scenario_path))
    counts = {
        str(player): sum(unit.unit_const == 2081 for unit in scenario.unit_manager.units[player])
        for player in (1, 2)
    }
    if counts != {"1": 15, "2": 15}:
        raise RuntimeError(f"installed integration scenario counts changed: {counts}")
    if scenario.player_manager.active_players != 2:
        raise RuntimeError("installed scenario does not have two active players")
    if (scenario.player_manager.players[1].diplomacy[1],
            scenario.player_manager.players[2].diplomacy[0]) != (3, 3):
        raise RuntimeError("installed scenario players are not mutual enemies")

    return {
        "format": "rome2aoe2.hastati-integration-install-verification",
        "version": 1,
        "mod_path": str(mod),
        "scenario_path": str(scenario_path),
        "total_hastati": sum(counts.values()),
        "player_counts": counts,
        "mutual_enemies": True,
        "graphics": actual,
        "corpse_unit_id": unit.dead_unit_id,
        "asset_hashes": asset_hashes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod", type=Path, required=True)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--source-mod", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.mod, args.scenario, args.source_mod)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
