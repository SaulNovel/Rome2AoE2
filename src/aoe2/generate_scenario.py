"""Generate and verify the Stage 1 AoE2 DE demonstration scenario."""

from __future__ import annotations

import sys
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "third_party" / "python-deps"))
sys.path.insert(0, str(PROJECT_ROOT / "third_party" / "AoE2ScenarioParser"))

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario


def contains_unit(
    scenario: AoE2DEScenario, unit_id: int, player_id: int, x: float, y: float
) -> bool:
    return any(
        unit.unit_const == unit_id and unit.x == x and unit.y == y
        for unit in scenario.unit_manager.units[player_id]
    )


def parse_units(arguments):
    if len(arguments) % 4 != 0:
        raise ValueError("Unit placements must be supplied as <unit-id> <player-id> <x> <y>.")

    return [
        (int(arguments[index]), int(arguments[index + 1]), float(arguments[index + 2]), float(arguments[index + 3]))
        for index in range(0, len(arguments), 4)
    ]


def generate(template_path: Path, output_path: Path, units) -> None:
    if template_path.resolve() == output_path.resolve():
        raise ValueError("The output scenario must not overwrite the template.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    scenario = AoE2DEScenario.from_file(str(template_path))
    for unit_id, player_id, x, y in units:
        scenario.unit_manager.add_unit(
            player=player_id,
            unit_const=unit_id,
            x=x,
            y=y,
        )
    scenario.write_to_file(str(output_path))

    written_scenario = AoE2DEScenario.from_file(str(output_path))
    for unit_id, player_id, x, y in units:
        if not contains_unit(written_scenario, unit_id, player_id, x, y):
            raise RuntimeError("Generated scenario does not contain an expected unit.")


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "Usage: generate_scenario.py <template> <output> "
            "<unit-id> <player-id> <x> <y> [<unit-id> <player-id> <x> <y> ...]",
            file=sys.stderr,
        )
        return 2

    generate(Path(sys.argv[1]), Path(sys.argv[2]), parse_units(sys.argv[3:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
