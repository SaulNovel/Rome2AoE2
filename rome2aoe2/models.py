from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AnimationProfile:
    skeleton: str
    family: str


@dataclass(frozen=True)
class ComponentOption:
    key: str
    source_path: str
    definition: str
    socket: str | None = None
    skeleton: str | None = None
    material_types: tuple[str, ...] = ()
    source_exists: bool = False

    @property
    def display_name(self) -> str:
        return Path(self.source_path).stem


@dataclass(frozen=True)
class ComponentSlot:
    key: str
    source_slot_paths: tuple[str, ...]
    required: bool
    default_key: str | None
    options: tuple[ComponentOption, ...]


@dataclass(frozen=True)
class UnitDefinition:
    catalog_id: int
    faction_key: str
    display_name: str
    main_unit: str
    land_unit: str = ""
    status: str = "PARTIAL"
    reason_codes: tuple[str, ...] = ()
    description: str | None = None
    variants: tuple[dict[str, Any], ...] = ()
    animation_family: str = ""
    skeleton: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class Faction:
    catalog_id: int
    key: str
    display_name: str
    units: tuple[UnitDefinition, ...]
    provenance: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class ResolvedUnit:
    definition: UnitDefinition
    land_unit: str
    variant: str
    root_vmd: str
    component_slots: tuple[ComponentSlot, ...]
    animation: AnimationProfile
    source_root: str
    raw_identity: dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class Dependency:
    path: str
    kind: str
    source_pack: str | None
    parent: str
    required: bool = True
    cache_state: str = "missing"
    validation_state: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class DependencyPlan:
    unit: UnitDefinition
    dependencies: tuple[Dependency, ...]
    slots: tuple[dict[str, Any], ...]
    animation_family: str
    skeleton: str
    cache_root: str

    @property
    def cache_hits(self) -> int:
        return sum(item.cache_state == "hit" for item in self.dependencies)

    @property
    def cache_misses(self) -> int:
        return sum(item.cache_state not in {"hit", "virtual"} for item in self.dependencies)
