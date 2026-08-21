from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from .errors import ConverterError, ErrorCode
from .models import AnimationProfile, ComponentOption, ComponentSlot, Faction, ResolvedUnit, UnitDefinition


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT / "build/cache/rome2aoe2/catalog-v1.json"
DEFAULT_EFFECTIVE_EVIDENCE = ROOT / "build/local-integration/rome2/runtime-resolution/effective-units.json"


def _category(slot: dict[str, Any]) -> str:
    path = slot["slot_path"].lower()
    leaf = path.rsplit("/", 1)[-1].split("[", 1)[0]
    socket = (slot.get("attach_point") or "").lower()
    if "skin" in path:
        return "body"
    if "armour" in leaf or "armor" in leaf:
        return "armour"
    if "tunic" in leaf:
        return "tunic"
    if "crest" in leaf:
        return "crest"
    if "helmet" in leaf:
        return "helmet"
    if "shield" in path or socket == "weapon_03":
        return "shield"
    if leaf in {"weapon_1", "weapon_2"} or socket in {"weapon_01", "weapon_02"}:
        return "melee_weapon"
    if leaf in {"weapon_3", "weapon_4"} or socket in {"weapon_04", "weapon_05"}:
        return "missile_weapon"
    return leaf or "other"


def _asset_metadata(source_root: Path) -> dict[str, dict[str, Any]]:
    path = source_root / "assets.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {row["source_model"].casefold(): row for row in data.get("exports", [])}


class Catalog:
    def __init__(self, evidence: dict[str, Any], effective_evidence: dict[str, Any] | None = None,
                 validated_evidence: bool = True):
        self.source_index = evidence
        self._effective_rows = {
            row["request"]["main_unit"]: row for row in (effective_evidence or {}).get("units", [])
        }
        if evidence.get("format") == "rome2aoe2.source-catalog":
            units = {row["main_unit"]: row for row in evidence["units"]}
            self.factions = tuple(self._source_factions(evidence["factions"], units))
        else:
            rows = evidence.get("units", [])
            self._effective_rows = {row["request"]["main_unit"]: row for row in rows}
            grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                grouped[row["request"]["faction"]].append(row)
            self.factions = tuple(self._build_factions(grouped))
        if self._effective_rows:
            self.factions = tuple(self._apply_effective_status(faction) for faction in self.factions)
        if validated_evidence:
            self.factions = tuple(self._apply_validated_status(faction) for faction in self.factions)
        self._units = defaultdict(list)
        for faction in self.factions:
            for unit in faction.units:
                self._units[unit.main_unit].append(unit)

    def _apply_effective_status(self, faction: Faction) -> Faction:
        units = []
        for unit in faction.units:
            if unit.main_unit in self._effective_rows and unit.status != "UNSUPPORTED":
                remaining = tuple(code for code in unit.reason_codes if code != "MISSING_REQUIRED_ASSET")
                units.append(replace(unit, status="READY" if not remaining else "PARTIAL", reason_codes=remaining))
            else:
                units.append(unit)
        return replace(faction, units=tuple(units))

    @staticmethod
    def _apply_validated_status(faction: Faction) -> Faction:
        validated_root = ROOT / "build/cache/rome2aoe2/validated-units-v1"
        units = []
        for unit in faction.units:
            path = validated_root / f"{unit.main_unit.casefold()}.json"
            if path.is_file() and unit.status != "UNSUPPORTED":
                value = json.loads(path.read_text(encoding="utf-8"))
                missing = [item for item in value.get("dependencies", [])
                           if item.get("required") and item.get("validation_state") != "valid"]
                units.append(replace(unit, status="READY" if not missing else "PARTIAL",
                                     reason_codes=() if not missing else ("MISSING_REQUIRED_ASSET",)))
            else:
                units.append(unit)
        return replace(faction, units=tuple(units))

    @staticmethod
    def _source_factions(factions: list[dict[str, Any]], units: dict[str, dict[str, Any]]) -> Iterable[Faction]:
        ordered_factions = sorted(factions, key=lambda row: (row["display_name"].casefold(), row["key"]))
        for faction_id, row in enumerate(ordered_factions, 1):
            source_units = sorted(
                (units[key] for key in row["unit_keys"] if key in units),
                key=lambda unit: (unit["display_name"].casefold(), unit["main_unit"]),
            )
            definitions = tuple(UnitDefinition(
                catalog_id=index, faction_key=row["key"], display_name=unit["display_name"],
                main_unit=unit["main_unit"], land_unit=unit["land_unit"] or "",
                status=unit["status"], reason_codes=tuple(unit["reason_codes"]),
                description=unit.get("description"), variants=tuple(unit["variants"]),
                animation_family=unit.get("animation_family", ""), skeleton=unit.get("skeleton"),
                provenance=unit.get("provenance", {}),
            ) for index, unit in enumerate(source_units, 1))
            yield Faction(faction_id, row["key"], row["display_name"], definitions, row.get("provenance", {}))

    @staticmethod
    def _build_factions(grouped: dict[str, list[dict[str, Any]]]) -> Iterable[Faction]:
        next_unit_id = 1
        for faction_id, faction_key in enumerate(sorted(grouped, key=str.casefold), 1):
            units = []
            ordered = sorted(
                grouped[faction_key],
                key=lambda row: (row["identity"]["unit_variants"]["name"].casefold(), row["request"]["main_unit"]),
            )
            for row in ordered:
                units.append(UnitDefinition(
                    catalog_id=len(units) + 1,
                    faction_key=faction_key,
                    display_name=row["identity"]["unit_variants"]["name"],
                    main_unit=row["request"]["main_unit"],
                ))
            yield Faction(faction_id, faction_key, faction_key, tuple(units))

    def find_faction(self, selector: str | int) -> Faction:
        text = str(selector).strip()
        for faction in self.factions:
            if text == str(faction.catalog_id) or text.casefold() in {faction.key.casefold(), faction.display_name.casefold()}:
                return faction
        raise ConverterError(ErrorCode.FACTION_NOT_FOUND, "No catalog faction matches the selector", selector=text)

    def find_unit(self, selector: str | int, faction: Faction | str | int | None = None) -> UnitDefinition:
        text = str(selector).strip()
        if faction is None and text.isdigit():
            raise ConverterError(ErrorCode.UNIT_NOT_FOUND, "Numeric unit IDs are local to a selected faction",
                                 selector=text, faction=None)
        pool = self.find_faction(faction).units if faction is not None and not isinstance(faction, Faction) else (
            faction.units if isinstance(faction, Faction) else tuple(unit for f in self.factions for unit in f.units)
        )
        if faction is None:
            exact = [unit for unit in pool if text.casefold() == unit.main_unit.casefold()]
            preferred_faction = self._effective_rows.get(text, {}).get("request", {}).get("faction")
            preferred = next((unit for unit in exact if unit.faction_key == preferred_faction), None)
            if preferred or exact:
                return preferred or exact[0]
        for unit in pool:
            if text == str(unit.catalog_id) or text.casefold() in {
                unit.main_unit.casefold(), unit.display_name.casefold()
            }:
                return unit
        raise ConverterError(ErrorCode.UNIT_NOT_FOUND, "No catalog unit matches the selector", selector=text,
                             faction=faction.key if isinstance(faction, Faction) else faction)

    def resolve(self, selector: str | int, faction: Faction | str | int | None = None) -> ResolvedUnit:
        definition = self.find_unit(selector, faction)
        row = self._effective_rows.get(definition.main_unit)
        if row is None:
            from .dependencies import DependencyResolver, plan_from_json, validated_plan_path
            validated = validated_plan_path(definition.main_unit)
            if validated.is_file():
                plan = plan_from_json(json.loads(validated.read_text(encoding="utf-8")), definition)
                return DependencyResolver(cache_root=Path(plan.cache_root)).resolved_unit(plan)
            chosen = next((item for item in definition.variants if item.get("source_pack")),
                          definition.variants[0] if definition.variants else None)
            if chosen is None:
                raise ConverterError(ErrorCode.UNRESOLVED_VMD, "Unit has no resolved VMD", unit=definition.main_unit)
            if not definition.animation_family or not definition.skeleton:
                raise ConverterError(ErrorCode.UNRESOLVED_ANIMATION_FAMILY,
                                     "Unit animation metadata is incomplete", unit=definition.main_unit)
            return ResolvedUnit(definition, definition.land_unit, chosen["variant"], chosen["path"], (),
                                AnimationProfile(definition.skeleton, definition.animation_family), "", definition.provenance)
        identity = row["identity"]
        land = identity["land_units"]
        family = land.get("man_animation", "").strip()
        if not family:
            raise ConverterError(
                ErrorCode.UNRESOLVED_ANIMATION_FAMILY,
                "land_units did not resolve a man_animation family",
                unit=definition.main_unit,
                land_unit=land.get("key"),
            )
        source_root = Path(row["vmd"]["root"])
        metadata = _asset_metadata(source_root)
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for slot in row["vmd"].get("slots", []):
            if any(entry.get("kind") == "model" and entry.get("model") for entry in slot.get("entries", [])):
                groups[_category(slot)].append(slot)
        component_slots = tuple(
            self._component_slot(key, slots, metadata)
            for key, slots in sorted(groups.items())
        )
        skeletons = Counter(
            option.skeleton for slot in component_slots for option in slot.options if option.skeleton
        )
        if not skeletons:
            raise ConverterError(
                ErrorCode.SKELETON_MISMATCH, "No skeleton was resolved from weighted source assets",
                unit=definition.main_unit, root_vmd=identity["variant_filename"],
            )
        return ResolvedUnit(
            definition=definition,
            land_unit=land["key"],
            variant=identity["unit_variants"]["variant"],
            root_vmd=identity["variant_filename"],
            component_slots=component_slots,
            animation=AnimationProfile(skeletons.most_common(1)[0][0], family),
            source_root=str(source_root),
            raw_identity=identity,
        )

    @staticmethod
    def _component_slot(key: str, slots: list[dict[str, Any]], metadata: dict[str, dict[str, Any]]) -> ComponentSlot:
        options: dict[str, ComponentOption] = {}
        for slot in slots:
            for entry in slot["entries"]:
                source = entry.get("model")
                if not source:
                    continue
                stable_key = source.replace("\\", "/").casefold()
                asset = metadata.get(stable_key, {})
                info = asset.get("metadata", {})
                origin_socket = next(
                    (origin.get("attach_point") for origin in asset.get("origins", [])
                     if origin.get("attach_point")), None,
                )
                materials = tuple(sorted({item["type"] for item in info.get("material_types", [])}))
                options.setdefault(stable_key, ComponentOption(
                    key=stable_key,
                    source_path=source.replace("\\", "/"),
                    definition=slot["definition"].replace("\\", "/"),
                    socket=slot.get("attach_point") or origin_socket,
                    skeleton=info.get("skeleton_id") or None,
                    material_types=materials,
                    source_exists=bool(asset),
                ))
        # VMD source order is semantically significant: Rome II's default is
        # the first declared alternative, not lexical asset order.
        ordered = tuple(options.values())
        required = all(slot.get("probability") in (None, "", "1", "1.0") for slot in slots)
        return ComponentSlot(
            key=key,
            source_slot_paths=tuple(sorted({slot["slot_path"] for slot in slots})),
            required=required,
            default_key=ordered[0].key if ordered else None,
            options=ordered,
        )


def load_default_catalog(path: Path | None = None, effective_path: Path | None = None) -> Catalog:
    source = path or DEFAULT_CACHE
    if not source.is_file():
        raise ConverterError(
            ErrorCode.MISSING_SOURCE_ASSET,
            "Derived source catalog is missing; run 'python -m rome2aoe2 catalog rebuild'",
            path=str(source),
        )
    effective_source = effective_path or DEFAULT_EFFECTIVE_EVIDENCE
    effective = json.loads(effective_source.read_text(encoding="utf-8")) if effective_source.is_file() else None
    return Catalog(json.loads(source.read_text(encoding="utf-8")), effective)
