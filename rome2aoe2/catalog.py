from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from .errors import ConverterError, ErrorCode
from .models import AnimationProfile, ComponentOption, ComponentSlot, Faction, ResolvedUnit, UnitDefinition


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = ROOT / "build/local-integration/rome2/runtime-resolution/effective-units.json"


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
    def __init__(self, evidence: dict[str, Any]):
        rows = evidence.get("units", [])
        self._rows = {row["request"]["main_unit"]: row for row in rows}
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[row["request"]["faction"]].append(row)
        self.factions = tuple(self._build_factions(grouped))
        self._units = {
            unit.main_unit: unit for faction in self.factions for unit in faction.units
        }

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
                    catalog_id=next_unit_id,
                    faction_key=faction_key,
                    display_name=row["identity"]["unit_variants"]["name"],
                    main_unit=row["request"]["main_unit"],
                ))
                next_unit_id += 1
            yield Faction(faction_id, faction_key, faction_key, tuple(units))

    def find_unit(self, selector: str | int) -> UnitDefinition:
        text = str(selector).strip()
        for unit in self._units.values():
            if text == str(unit.catalog_id) or text.casefold() in {
                unit.main_unit.casefold(), unit.display_name.casefold()
            }:
                return unit
        raise ConverterError(ErrorCode.UNIT_NOT_FOUND, "No catalog unit matches the selector", selector=text)

    def resolve(self, selector: str | int) -> ResolvedUnit:
        definition = self.find_unit(selector)
        row = self._rows[definition.main_unit]
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


def load_default_catalog(path: Path | None = None) -> Catalog:
    source = path or DEFAULT_EVIDENCE
    if not source.is_file():
        raise ConverterError(
            ErrorCode.MISSING_SOURCE_ASSET,
            "Catalog evidence is missing; run the existing Rome II DB/VMD resolution workflow",
            path=str(source),
        )
    return Catalog(json.loads(source.read_text(encoding="utf-8")))
