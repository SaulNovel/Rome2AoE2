from __future__ import annotations

import argparse
import json
import struct
import subprocess
from collections import defaultdict
from pathlib import Path

from .errors import ConverterError, ErrorCode


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME_DATA = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Total War Rome II\data")
DEFAULT_HELPER = ROOT / "tools/rome2_pack/target/release/rome2aoe2-pack.exe"
DEFAULT_SCHEMA = ROOT / "build/local-integration/rpfm-schemas/schema_rom2.ron"
DEFAULT_CACHE = ROOT / "build/cache/rome2aoe2/catalog-v1.json"
TABLES = (
    "factions", "main_units", "land_units", "unit_variants",
    "units_to_exclusive_faction_permissions",
    "units_to_groupings_military_permissions", "groupings_military",
)
LOC_FILES = ("factions", "land_units", "unit_description_short_texts")
MODEL_PACKS = ("models3_rome2.pack", "models2_rome2.pack", "models_rome2.pack")
SUPPORTED_INFANTRY_CATEGORIES = {"inf_melee", "inf_ranged"}


def _run_json(arguments: list[str]) -> dict:
    result = subprocess.run(arguments, capture_output=True, text=True)
    if result.returncode:
        raise ConverterError(
            ErrorCode.MISSING_SOURCE_ASSET, "Rome II metadata helper failed",
            command=arguments, stderr=result.stderr.strip(),
        )
    return json.loads(result.stdout)


def parse_loc(path: Path) -> dict[str, str]:
    data = memoryview(path.read_bytes())
    if data[:6].tobytes() != b"\xff\xfeLOC\x00":
        raise ConverterError(ErrorCode.MISSING_SOURCE_ASSET, "Unsupported Rome II LOC header", path=str(path))
    offset = 10
    count = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    rows = {}
    for _ in range(count):
        key_length = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        key = data[offset:offset + key_length * 2].tobytes().decode("utf-16-le")
        offset += key_length * 2
        value_length = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        value = data[offset:offset + value_length * 2].tobytes().decode("utf-16-le")
        offset += value_length * 2
        offset += 1  # CA tooltip/visibility flag
        rows[key.casefold()] = value
    if offset != len(data):
        raise ConverterError(ErrorCode.MISSING_SOURCE_ASSET, "LOC row decoding did not consume the file", path=str(path))
    return rows


class SourceIndexer:
    def __init__(self, game_data: Path = DEFAULT_GAME_DATA, helper: Path = DEFAULT_HELPER,
                 schema: Path = DEFAULT_SCHEMA, work_root: Path | None = None):
        self.game_data = Path(game_data)
        self.helper = Path(helper)
        self.schema = Path(schema)
        self.work_root = work_root or ROOT / "build/cache/rome2aoe2/source"

    def _require_sources(self) -> None:
        for path in (self.helper, self.schema, self.game_data / "data_rome2.pack", self.game_data / "local_en.pack"):
            if not path.is_file():
                raise ConverterError(ErrorCode.MISSING_SOURCE_ASSET, "Required catalog source is missing", path=str(path))

    def _extract(self, pack: Path, source_path: str) -> Path:
        _run_json([str(self.helper), "extract", "--pack", str(pack), "--path", source_path,
                   "--output-root", str(self.work_root)])
        return self.work_root.joinpath(*source_path.split("/"))

    def _table(self, name: str) -> list[dict]:
        relative = f"db/{name}_tables/{name}"
        path = self._extract(self.game_data / "data_rome2.pack", relative)
        result = _run_json([str(self.helper), "decode-db", "--input", str(path),
                            "--schema", str(self.schema), "--table", f"{name}_tables"])
        return result["rows"]

    def _localization(self) -> dict[str, str]:
        result = {}
        pack = self.game_data / "local_en.pack"
        for name in LOC_FILES:
            result.update(parse_loc(self._extract(pack, f"text/db/{name}.loc")))
        return result

    def _vmd_index(self) -> dict[str, str]:
        result = {}
        for pack_name in MODEL_PACKS:
            pack = self.game_data / pack_name
            if not pack.is_file():
                continue
            listing = _run_json([str(self.helper), "list", "--pack", str(pack)])
            for path in listing["paths"]:
                key = path.casefold()
                if key.startswith("variantmeshes/variantmeshdefinitions/") and key.endswith(".variantmeshdefinition"):
                    result.setdefault(key, pack_name)
        return result

    def build(self) -> dict:
        self._require_sources()
        tables = {name: self._table(name) for name in TABLES}
        localization = self._localization()
        vmd_index = self._vmd_index()
        land_by_key = {row["key"]: row for row in tables["land_units"]}
        variants_by_unit = defaultdict(list)
        for row in tables["unit_variants"]:
            variants_by_unit[row["unit"]].append(row)
        main_by_key = {row["unit"]: row for row in tables["main_units"] if row.get("is_naval") != "true"}
        faction_rows = {row["key"]: row for row in tables["factions"]}
        factions_by_group = defaultdict(list)
        for row in faction_rows.values():
            if row.get("military_group"):
                factions_by_group[row["military_group"]].append(row["key"])
        memberships = defaultdict(set)
        for row in tables["units_to_groupings_military_permissions"]:
            if row["unit"] in main_by_key:
                memberships[row["unit"]].update(factions_by_group.get(row["military_group"], ()))
        for row in tables["units_to_exclusive_faction_permissions"]:
            if row.get("allowed") == "true" and row["key"] in main_by_key:
                memberships[row["key"]].add(row["faction"])

        units = []
        for main_key in sorted(main_by_key, key=str.casefold):
            main = main_by_key[main_key]
            land = land_by_key.get(main.get("land_unit"))
            variants = sorted(variants_by_unit.get(main.get("land_unit"), []), key=lambda row: (row["variant"].casefold(), row["name"]))
            reasons = []
            status = "PARTIAL"
            if land is None:
                reasons.append("MISSING_REQUIRED_ASSET")
            elif land.get("category") not in SUPPORTED_INFANTRY_CATEGORIES or land.get("animal"):
                status = "UNSUPPORTED"
                reasons.append("UNSUPPORTED_UNIT_CLASS")
            if not variants:
                reasons.append("UNRESOLVED_VMD")
            vmds = []
            for variant in variants:
                path = f"variantmeshes/variantmeshdefinitions/{variant['variant'].lower()}.variantmeshdefinition"
                vmds.append({"variant_key": variant["name"], "variant": variant["variant"],
                             "path": path, "source_pack": vmd_index.get(path.casefold())})
            if variants and not any(item["source_pack"] for item in vmds):
                reasons.append("UNRESOLVED_VMD")
            family = land.get("man_animation", "") if land else ""
            if land and not family:
                reasons.append("UNRESOLVED_ANIMATION_FAMILY")
            elif land and not family.startswith("rome_man_"):
                reasons.append("UNSUPPORTED_SKELETON")
            if status != "UNSUPPORTED":
                # Root metadata is sufficient for discovery, but READY requires
                # selected-unit dependency/material validation. A later
                # extraction cache may promote the record without defining it.
                reasons.append("MISSING_REQUIRED_ASSET")
            name_key = f"land_units_onscreen_name_{main.get('land_unit', '')}".casefold()
            description_key = f"unit_description_short_texts_text_{(land or {}).get('short_description_text', '')}".casefold()
            source_name = variants[0]["name"] if variants else main_key
            units.append({
                "main_unit": main_key, "land_unit": main.get("land_unit"),
                "display_name": localization.get(name_key) or source_name or main_key,
                "display_source": "localized" if localization.get(name_key) else ("unit_variants.name" if variants else "main_units.unit"),
                "description": localization.get(description_key), "animation_family": family,
                "skeleton": "rome_man_game" if family.startswith("rome_man_") else None,
                "variants": vmds, "factions": sorted(memberships.get(main_key, ()), key=str.casefold),
                "status": status, "reason_codes": sorted(set(reasons)),
                "provenance": {
                    "main_units": {"pack": "data_rome2.pack", "table": "main_units", "key": main_key},
                    "land_units": {"pack": "data_rome2.pack", "table": "land_units", "key": main.get("land_unit")},
                    "unit_variants": {"pack": "data_rome2.pack", "table": "unit_variants", "keys": [row["name"] for row in variants]},
                    "faction_membership": {"pack": "data_rome2.pack", "tables": ["units_to_groupings_military_permissions", "units_to_exclusive_faction_permissions"]},
                    "localization": {"pack": "local_en.pack", "key": name_key if localization.get(name_key) else None},
                },
            })
        units_by_faction = defaultdict(list)
        for unit in units:
            for faction in unit["factions"]:
                units_by_faction[faction].append(unit["main_unit"])
        factions = []
        for key in sorted(units_by_faction, key=str.casefold):
            row = faction_rows[key]
            loc_key = f"factions_screen_name_{key}".casefold()
            source_name = row.get("screen_name") or key
            factions.append({
                "key": key, "display_name": localization.get(loc_key) or source_name or key,
                "display_source": "localized" if localization.get(loc_key) else ("factions.screen_name" if source_name != key else "factions.key"),
                "unit_keys": sorted(units_by_faction[key], key=str.casefold),
                "provenance": {"pack": "data_rome2.pack", "table": "factions", "key": key,
                               "localization_pack": "local_en.pack", "localization_key": loc_key if localization.get(loc_key) else None},
            })
        return {
            "format": "rome2aoe2.source-catalog", "schema_version": 1,
            "source": {
                "game": "Total War Rome II", "db_pack": "data_rome2.pack", "localization_pack": "local_en.pack",
                "model_pack_precedence": list(MODEL_PACKS),
                "pack_sizes": {name: (self.game_data / name).stat().st_size for name in ("data_rome2.pack", "local_en.pack", *MODEL_PACKS)},
                "schema": self.schema.name, "schema_size": self.schema.stat().st_size,
            },
            "factions": factions, "units": units,
        }


def write_cache(index: dict, output: Path = DEFAULT_CACHE) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild the derived Rome II faction/unit source index")
    parser.add_argument("--game-data", type=Path, default=DEFAULT_GAME_DATA)
    parser.add_argument("--helper", type=Path, default=DEFAULT_HELPER)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args(argv)
    index = SourceIndexer(args.game_data, args.helper, args.schema).build()
    write_cache(index, args.output)
    print(json.dumps({"cache": str(args.output), "factions": len(index["factions"]),
                      "units": len(index["units"])}, indent=2))
    return 0
