from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from .catalog import Catalog, load_default_catalog
from .errors import ConverterError, ErrorCode
from .manifest import AutoSelection, build_manifest
from .models import ComponentSlot, Faction, ResolvedUnit
from .indexer import SourceIndexer, write_cache
from .dependencies import (DependencyResolver, plan_from_json, plan_json,
                           validated_plan_path, write_validated_plan)
from .conversion import convert as convert_manifest
from .animation import CATEGORIES, choose_candidate, discover, enrich_metadata, freeze_animations
from .preview import generate_preview


def print_factions(catalog: Catalog, output: TextIO) -> None:
    for faction in catalog.factions:
        print(f"[{faction.catalog_id}] {faction.display_name} ({faction.key}) - {len(faction.units)} land units", file=output)


def print_catalog(catalog: Catalog, output: TextIO, selected_faction=None) -> None:
    if isinstance(selected_faction, Faction):
        factions = (selected_faction,)
    else:
        factions = (catalog.find_faction(selected_faction),) if selected_faction is not None else catalog.factions
    for faction in factions:
        print(f"{faction.display_name}\n{'-' * len(faction.display_name)}", file=output)
        for unit in faction.units:
            reasons = f" - {', '.join(unit.reason_codes)}" if unit.reason_codes else ""
            print(f"[{unit.catalog_id}] {unit.display_name}\n    {unit.main_unit}\n    {unit.status}{reasons}", file=output)
        print(file=output)


def print_resolved(unit: ResolvedUnit, output: TextIO, verbose: bool = False) -> None:
    print(f"Unit: {unit.definition.display_name}", file=output)
    print(f"Faction: {unit.definition.faction_key}", file=output)
    print(f"DB chain: {unit.definition.main_unit} -> {unit.land_unit} -> {unit.variant}", file=output)
    print(f"Root VMD: {unit.root_vmd}", file=output)
    print(f"Animation: {unit.animation.family} / {unit.animation.skeleton}", file=output)
    print(f"Convertibility: {unit.definition.status}", file=output)
    if unit.definition.reason_codes:
        print(f"Reasons: {', '.join(unit.definition.reason_codes)}", file=output)
    if unit.definition.description:
        print(f"Description: {unit.definition.description}", file=output)
    print("Components:", file=output)
    for slot in unit.component_slots:
        requirement = "required" if slot.required else "optional"
        print(f"  {slot.key} ({requirement}; {len(slot.options)} alternatives)", file=output)
        for index, option in enumerate(slot.options, 1):
            socket = f" socket={option.socket}" if option.socket else ""
            print(f"    [{index}] {option.display_name} | {option.source_path}{socket}", file=output)
    if verbose:
        print("Provenance:", file=output)
        print(json.dumps(unit.definition.provenance, indent=2, sort_keys=True), file=output)
        if unit.definition.variants:
            print("Variant sources:", file=output)
            print(json.dumps(list(unit.definition.variants), indent=2, sort_keys=True), file=output)


def _prompt(prompt: str, input_stream: TextIO, output: TextIO) -> str:
    print(prompt, end="", file=output, flush=True)
    value = input_stream.readline()
    if value == "":
        raise ConverterError(ErrorCode.UNIT_NOT_FOUND, "Input ended before a selection was made")
    return value.strip()


def choose_faction(catalog: Catalog, input_stream: TextIO, output: TextIO):
    print_factions(catalog, output)
    while True:
        selector = _prompt("Select faction: ", input_stream, output)
        try:
            return catalog.find_faction(selector)
        except ConverterError as error:
            print(error, file=output)


def choose_unit(catalog: Catalog, input_stream: TextIO, output: TextIO, faction=None) -> ResolvedUnit:
    faction = faction or choose_faction(catalog, input_stream, output)
    print_catalog(catalog, output, faction)
    while True:
        selector = _prompt("Select unit: ", input_stream, output)
        try:
            return catalog.resolve(selector, faction)
        except ConverterError as error:
            print(error, file=output)


def choose_component(slot: ComponentSlot, input_stream: TextIO, output: TextIO) -> str | None:
    print(f"\n{slot.key} ({'required' if slot.required else 'optional'})", file=output)
    print("[A] Auto (deterministic source-first)", file=output)
    if not slot.required:
        print("[0] None", file=output)
    for index, option in enumerate(slot.options, 1):
        socket = f" socket={option.socket}" if option.socket else ""
        print(f"[{index}] {option.display_name} | {option.source_path}{socket}", file=output)
    while True:
        value = _prompt("Select component: ", input_stream, output)
        if value.casefold() == "a":
            return AutoSelection(slot.default_key)
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
    faction = choose_faction(catalog, input_stream, output)
    unit = choose_unit(catalog, input_stream, output, faction)
    choices = {
        slot.key: choose_component(slot, input_stream, output)
        for slot in unit.component_slots
    }
    manifest = build_manifest(unit, choices)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # The same selected, materialized soldier is the native preview input.
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    convert_manifest(output_path, catalog)
    manifest = configure_animation_choices(unit, manifest, input_stream, output)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Manifest: {output_path}", file=output)
    return manifest


def _print_candidate(index, candidate, output):
    loop = "loop" if candidate.looping else "non-loop"
    print(f"[{index}] {Path(candidate.resolved_asset).name}", file=output)
    print(f"    states: {', '.join(candidate.states)}", file=output)
    print(f"    {candidate.frame_count} frames | {candidate.fps:g} FPS | {candidate.duration:.2f} s | {loop}", file=output)
    if candidate.category == "walk":
        print(f"    displacement: {candidate.root_displacement} | horizontal {candidate.horizontal_displacement:.3f} m | speed {candidate.locomotion_speed:.3f} m/s", file=output)
    print(f"    tags: {', '.join(candidate.context_tags) or 'none derived'}", file=output)
    print(f"    preview: {candidate.preview_path}", file=output)


def configure_animation_choices(unit: ResolvedUnit, manifest: dict, input_stream: TextIO, output: TextIO) -> dict:
    print("\n------------------------------------------------------------\nANIMATION CONFIGURATION\n------------------------------------------------------------", file=output)
    groups = enrich_metadata(discover(unit))
    selections = {}
    for category in CATEGORIES:
        group = groups[category]
        if not group.candidates:
            raise ConverterError(ErrorCode.ANIMATION_CATEGORY_UNSUPPORTED, "No compatible candidates for required category", category=category)
        rendered = []
        for candidate in group.shortlist:
            candidate, cache_hit, _ = generate_preview(manifest, candidate)
            rendered.append(candidate)
            print(f"Preview {'cache hit' if cache_hit else 'generated'}: {candidate.preview_path}", file=output)
        group = group.__class__(category, tuple(rendered) + group.additional, group.shortlist_size)
        print(f"\n{category.title()} candidates found: {len(group.candidates)} (showing {len(group.shortlist)}, additional {len(group.additional)})", file=output)
        for index, candidate in enumerate(group.shortlist, 1):
            _print_candidate(index, candidate, output)
        print(f"[A] Auto — recommended: [1] {Path(group.recommendation.resolved_asset).name}", file=output)
        if group.additional:
            print("[M] Show more candidates", file=output)
        while True:
            value = _prompt(f"Select {category}: ", input_stream, output)
            if value.casefold() == "m" and group.additional:
                for index, candidate in enumerate(group.additional, len(group.shortlist) + 1):
                    candidate, cache_hit, _ = generate_preview(manifest, candidate)
                    _print_candidate(index, candidate, output)
                continue
            try:
                selections[category] = choose_candidate(group, value)
                break
            except ConverterError as error:
                print(error, file=output)
    return freeze_animations(manifest, selections)


def reconfigure_animations(catalog: Catalog, source_path: Path, output_path: Path,
                           input_stream: TextIO, output: TextIO) -> dict:
    original = json.loads(source_path.read_text(encoding="utf-8"))
    unit = catalog.resolve(original["source"]["main_unit"], original["source"]["faction"])
    visual = {key: value for key, value in original.items() if key != "animations"}
    visual["schema_version"] = 1
    result = configure_animation_choices(unit, visual, input_stream, output)
    if output_path.resolve() == source_path.resolve():
        raise ConverterError(ErrorCode.MANIFEST_SCHEMA_UNSUPPORTED, "Reconfiguration requires a distinct output unless overwrite semantics are added")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Manifest: {output_path}", file=output)
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="python -m rome2aoe2")
    result.add_argument("--catalog", type=Path, help="effective-units JSON evidence override")
    commands = result.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list-units")
    listing.add_argument("--faction")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("unit")
    inspect.add_argument("--faction")
    inspect.add_argument("--verbose", action="store_true")
    inspect.add_argument("--dependencies", action="store_true")
    configure_command = commands.add_parser("configure")
    configure_command.add_argument("--output", type=Path, default=Path("rome2aoe2-manifest.json"))
    reconfigure = commands.add_parser("configure-animations")
    reconfigure.add_argument("manifest", type=Path)
    reconfigure.add_argument("--output", type=Path, required=True)
    convert = commands.add_parser("convert")
    convert.add_argument("manifest", type=Path)
    catalog_command = commands.add_parser("catalog")
    catalog_command.add_argument("action", choices=("rebuild",))
    extract = commands.add_parser("extract")
    extract.add_argument("unit")
    extract.add_argument("--faction")
    extract.add_argument("--manifest", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "convert":
            print(json.dumps(convert_manifest(args.manifest), indent=2, sort_keys=True))
            return 0
        if args.command == "configure-animations":
            catalog = load_default_catalog(args.catalog)
            reconfigure_animations(catalog, args.manifest, args.output, sys.stdin, sys.stdout)
            return 0
        if args.command == "catalog":
            index = SourceIndexer().build()
            write_cache(index)
            print(json.dumps({"cache": "build/cache/rome2aoe2/catalog-v1.json",
                              "factions": len(index["factions"]), "units": len(index["units"])}, indent=2))
            return 0
        catalog = load_default_catalog(args.catalog)
        if args.command == "list-units":
            print_catalog(catalog, sys.stdout, args.faction)
        elif args.command == "inspect":
            if args.dependencies:
                definition = catalog.find_unit(args.unit, args.faction)
                validated = validated_plan_path(definition.main_unit)
                plan = (plan_from_json(json.loads(validated.read_text(encoding="utf-8")), definition)
                        if validated.is_file() else DependencyResolver().plan(definition))
                print(json.dumps(plan_json(plan), indent=2, sort_keys=True))
            else:
                print_resolved(catalog.resolve(args.unit, args.faction), sys.stdout, args.verbose)
        elif args.command == "extract":
            definition = catalog.find_unit(args.unit, args.faction)
            resolver = DependencyResolver()
            plan = resolver.extract(resolver.plan(definition))
            status, reasons = resolver.validate(plan)
            if status != "READY":
                raise ConverterError(ErrorCode.MISSING_SOURCE_ASSET,
                                     "Selected unit dependency closure did not validate",
                                     unit=definition.main_unit, status=status, reasons=reasons)
            plan_path = write_validated_plan(plan)
            unit = resolver.resolved_unit(plan)
            manifest = build_manifest(unit)
            manifest_path = args.manifest or plan_path.with_name(f"{definition.main_unit.casefold()}-auto-manifest.json")
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"status": status, "plan": str(plan_path), "manifest": str(manifest_path),
                              "cache_hits": plan.cache_hits, "cache_misses": plan.cache_misses,
                              "dependencies": len(plan.dependencies)}, indent=2))
        else:
            configure(catalog, args.output, sys.stdin, sys.stdout)
        return 0
    except ConverterError as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
