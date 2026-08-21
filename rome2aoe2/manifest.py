from __future__ import annotations

from typing import Mapping

from .errors import ConverterError, ErrorCode
from .models import ComponentOption, ResolvedUnit


SUPPORTED_MATERIALS = {
    "DefaultMaterial", "DecalDirtmap", "Weighted", "WeightedDirtmap",
    "WeightedSkinDirtmap", "Weighted_Decal", "Weighted_Texture_Blend",
}


def select_components(unit: ResolvedUnit, choices: Mapping[str, str | None] | None = None) -> dict[str, ComponentOption | None]:
    choices = choices or {}
    selected = {}
    for slot in unit.component_slots:
        requested = choices.get(slot.key, slot.default_key)
        if requested is None:
            if slot.required:
                raise ConverterError(
                    ErrorCode.REQUIRED_COMPONENT_MISSING, "A required VMD slot cannot be None",
                    unit=unit.definition.main_unit, component=slot.key,
                    source_slots=slot.source_slot_paths,
                )
            selected[slot.key] = None
            continue
        option = next((item for item in slot.options if item.key == requested), None)
        if option is None:
            raise ConverterError(
                ErrorCode.COMPONENT_NOT_FOUND, "Component alternative is not present in the resolved VMD slot",
                unit=unit.definition.main_unit, component=slot.key, option=requested,
            )
        _validate_option(unit, slot.key, option)
        selected[slot.key] = option
    unknown = sorted(set(choices) - {slot.key for slot in unit.component_slots})
    if unknown:
        raise ConverterError(
            ErrorCode.COMPONENT_NOT_FOUND, "Manifest contains unknown component slots",
            unit=unit.definition.main_unit, components=unknown,
        )
    return selected


def _validate_option(unit: ResolvedUnit, component: str, option: ComponentOption) -> None:
    if not option.source_exists:
        raise ConverterError(
            ErrorCode.MISSING_SOURCE_ASSET, "Selected model is not present in extracted source evidence",
            unit=unit.definition.main_unit, component=component, path=option.source_path,
        )
    if option.skeleton and option.skeleton != unit.animation.skeleton:
        raise ConverterError(
            ErrorCode.SKELETON_MISMATCH, "Selected weighted model uses a different skeleton",
            unit=unit.definition.main_unit, component=component, path=option.source_path,
            expected=unit.animation.skeleton, actual=option.skeleton,
        )
    unsupported = sorted(set(option.material_types) - SUPPORTED_MATERIALS)
    if unsupported:
        raise ConverterError(
            ErrorCode.UNSUPPORTED_MATERIAL, "Selected model contains unsupported material types",
            unit=unit.definition.main_unit, component=component, path=option.source_path,
            material_types=unsupported,
        )
    if option.socket and not option.socket.startswith(("weapon_", "crest_")):
        raise ConverterError(
            ErrorCode.INCOMPATIBLE_ATTACHMENT, "Selected rigid attachment uses an unsupported socket",
            unit=unit.definition.main_unit, component=component, path=option.source_path,
            socket=option.socket,
        )


def build_manifest(unit: ResolvedUnit, choices: Mapping[str, str | None] | None = None) -> dict:
    selected = select_components(unit, choices)
    components = {}
    for key, option in sorted(selected.items()):
        components[key] = None if option is None else {
            "key": option.key,
            "source_path": option.source_path,
            "definition": option.definition,
            "socket": option.socket,
            "skeleton": option.skeleton,
            "material_types": list(option.material_types),
        }
    return {
        "schema_version": 1,
        "source": {
            "faction": unit.definition.faction_key,
            "main_unit": unit.definition.main_unit,
            "land_unit": unit.land_unit,
            "variant": unit.variant,
            "root_vmd": unit.root_vmd,
        },
        "components": components,
        "animation": {
            "skeleton": unit.animation.skeleton,
            "family": unit.animation.family,
        },
    }
