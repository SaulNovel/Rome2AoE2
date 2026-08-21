from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from .catalog import Catalog, load_default_catalog
from .errors import ConverterError, ErrorCode
from .manifest import build_manifest
from .models import ComponentSlot, ResolvedUnit


def print_catalog(catalog: Catalog, output: TextIO) -> None:
    for faction in catalog.factions:
        print(f"{faction.display_name}\n{'-' * len(faction.display_name)}", file=output)
        for unit in faction.units:
            print(f"[{unit.catalog_id}] {unit.display_name} ({unit.main_unit})", file=output)
        print(file=output)


def print_resolved(unit: ResolvedUnit, output: TextIO) -> None:
    print(f"Unit: {unit.definition.display_name}", file=output)
    print(f"Faction: {unit.definition.faction_key}", file=output)
    print(f"DB chain: {unit.definition.main_unit} -> {unit.land_unit} -> {unit.variant}", file=output)
    print(f"Root VMD: {unit.root_vmd}", file=output)
    print(f"Animation: {unit.animation.family} / {unit.animation.skeleton}", file=output)
    print("Components:", file=output)
    for slot in unit.component_slots:
        requirement = "required" if slot.required else "optional"
        print(f"  {slot.key} ({requirement}; {len(slot.options)} alternatives)", file=output)
        for index, option in enumerate(slot.options, 1):
            socket = f" socket={option.socket}" if option.socket else ""
            print(f"    [{index}] {option.display_name} | {option.source_path}{socket}", file=output)


def _prompt(prompt: str, input_stream: TextIO, output: TextIO) -> str:
    print(prompt, end="", file=output, flush=True)
    value = input_stream.readline()
    if value == "":
        raise ConverterError(ErrorCode.UNIT_NOT_FOUND, "Input ended before a selection was made")
    return value.strip()


def choose_unit(catalog: Catalog, input_stream: TextIO, output: TextIO) -> ResolvedUnit:
    print_catalog(catalog, output)
    while True:
        selector = _prompt("Select unit: ", input_stream, output)
        try:
            return catalog.resolve(selector)
        except ConverterError as error:
            print(error, file=output)


def choose_component(slot: ComponentSlot, input_stream: TextIO, output: TextIO) -> str | None:
    print(f"\n{slot.key} ({'required' if slot.required else 'optional'})", file=output)
    print("[D] Rome II default", file=output)
    if not slot.required:
        print("[0] None", file=output)
    for index, option in enumerate(slot.options, 1):
        socket = f" socket={option.socket}" if option.socket else ""
        print(f"[{index}] {option.display_name} | {option.source_path}{socket}", file=output)
    while True:
        value = _prompt("Select component: ", input_stream, output)
        if value.casefold() == "d":
            return slot.default_key
        if value == "0":
            if slot.required:
                print(f"{ErrorCode.REQUIRED_COMPONENT_MISSING.value}: {slot.key} is required", file=output)
                continue
            return None
        try:
            index = int(value)
        except ValueError:
            index = -1
        if 1 <= index <= len(slot.options):
            return slot.options[index - 1].key
        print(f"{ErrorCode.COMPONENT_NOT_FOUND.value}: invalid option {value!r} for {slot.key}", file=output)


def configure(catalog: Catalog, output_path: Path, input_stream: TextIO, output: TextIO) -> dict:
    unit = choose_unit(catalog, input_stream, output)
    choices = {
        slot.key: choose_component(slot, input_stream, output)
        for slot in unit.component_slots
    }
    manifest = build_manifest(unit, choices)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Manifest: {output_path}", file=output)
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="python -m rome2aoe2")
    result.add_argument("--catalog", type=Path, help="effective-units JSON evidence override")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("list-units")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("unit")
    configure_command = commands.add_parser("configure")
    configure_command.add_argument("--output", type=Path, default=Path("rome2aoe2-manifest.json"))
    convert = commands.add_parser("convert")
    convert.add_argument("manifest", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "convert":
            raise ConverterError(
                ErrorCode.CONVERSION_NOT_IMPLEMENTED,
                "Conversion orchestration is intentionally outside the catalog/configuration milestone",
                manifest=str(args.manifest),
            )
        catalog = load_default_catalog(args.catalog)
        if args.command == "list-units":
            print_catalog(catalog, sys.stdout)
        elif args.command == "inspect":
            print_resolved(catalog.resolve(args.unit), sys.stdout)
        else:
            configure(catalog, args.output, sys.stdin, sys.stdout)
        return 0
    except ConverterError as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
