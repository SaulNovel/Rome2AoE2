"""Generate the trigger-free 15-vs-15 complete Hastati integration scenario."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "third_party/python-deps"), str(ROOT / "third_party/AoE2ScenarioParser")]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from AoE2ScenarioParser.datasets.trigger_lists import DiplomacyState
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario


UNIT_ID = 2081
PLAYERS = (1, 2)
UNITS_PER_PLAYER = 15


def placements():
    rows = (44.0, 54.0, 64.0)
    result = []
    for player, base_x, nominal_facing in ((1, 34.0, 0.0), (2, 76.0, math.pi)):
        for group, base_y in enumerate(rows):
            for column in range(5):
                # Small facing variations expose several initial facets while
                # retaining readable five-unit formations.
                facing = nominal_facing + (column - 2) * (math.pi / 8)
                x = base_x + column * 1.8 if player == 1 else base_x - column * 1.8
                result.append({
                    "player": player,
                    "group": group + 1,
                    "column": column + 1,
                    "unit_id": UNIT_ID,
                    "x": x,
                    "y": base_y,
                    "rotation": facing % (2 * math.pi),
                })
    return result


def generate(template: Path, output: Path, report_path: Path) -> dict:
    scenario = AoE2DEScenario.from_file(str(template))
    scenario.player_manager.active_players = 2
    scenario.player_manager.players[1].set_player_diplomacy([2], DiplomacyState.ENEMY)
    scenario.player_manager.players[2].set_player_diplomacy([1], DiplomacyState.ENEMY)
    for player in PLAYERS:
        view = scenario.player_manager.players[player]
        view.initial_player_view_x = 55
        view.initial_player_view_y = 54

    expected = placements()
    for item in expected:
        scenario.unit_manager.add_unit(
            player=item["player"], unit_const=item["unit_id"],
            x=item["x"], y=item["y"], rotation=item["rotation"],
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    scenario.write_to_file(str(output))
    written = AoE2DEScenario.from_file(str(output))
    counts = {
        str(player): sum(unit.unit_const == UNIT_ID for unit in written.unit_manager.units[player])
        for player in PLAYERS
    }
    if counts != {"1": UNITS_PER_PLAYER, "2": UNITS_PER_PLAYER}:
        raise RuntimeError(f"integration scenario unit counts changed: {counts}")
    if written.player_manager.active_players != 2:
        raise RuntimeError("integration scenario does not have two active opposing players")
    if (written.player_manager.players[1].diplomacy[1],
            written.player_manager.players[2].diplomacy[0]) != (3, 3):
        raise RuntimeError("players 1 and 2 are not mutual enemies")

    report = {
        "format": "rome2aoe2.hastati-integration-scenario",
        "version": 1,
        "scenario": str(output),
        "unit_id": UNIT_ID,
        "total_hastati": sum(counts.values()),
        "player_counts": counts,
        "mutual_enemies": True,
        "triggers_added": 0,
        "placements": expected,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.template, args.output, args.report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
