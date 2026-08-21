from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ConverterError, ErrorCode
from .indexer import DEFAULT_GAME_DATA, DEFAULT_HELPER, MODEL_PACKS
from .manifest import SUPPORTED_MATERIALS
from .models import (
    AnimationProfile, ComponentOption, ComponentSlot, Dependency, DependencyPlan,
    ResolvedUnit, UnitDefinition,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSET_CACHE = ROOT / "build/cache/rome2aoe2/assets-v1"
PACK_PRECEDENCE = (*MODEL_PACKS, "models2.pack", "models.pack", "greeks.pack", "data_rome2.pack", "data.pack")
SHADER_DEFAULT_TEXTURES = {"test_black.dds", "test_mask.dds"}


def canonical_path(value: str) -> str:
    candidate = value.strip().replace("\\", "/")
    path = PurePosixPath(candidate)
    if not candidate or path.is_absolute() or ".." in path.parts:
        raise ConverterError(ErrorCode.MISSING_SOURCE_ASSET, "Invalid Rome II dependency path", path=value)
    return str(path).casefold()


def _run(helper: Path, arguments: list[str]) -> dict[str, Any]:
    result = subprocess.run([str(helper), *arguments], capture_output=True, text=True)
    if result.returncode:
        raise ConverterError(ErrorCode.MISSING_SOURCE_ASSET, "Rome II pack helper failed",
                             command=arguments, stderr=result.stderr.strip())
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ConverterError(ErrorCode.MISSING_SOURCE_ASSET, "Rome II pack helper returned invalid JSON",
                             command=arguments, error=str(error)) from error


class PackIndex:
    def __init__(self, game_data: Path = DEFAULT_GAME_DATA, helper: Path = DEFAULT_HELPER,
                 pack_names: tuple[str, ...] = PACK_PRECEDENCE):
        self.game_data = Path(game_data)
        self.helper = Path(helper)
        self.packs = tuple(self.game_data / name for name in pack_names if (self.game_data / name).is_file())
        self._paths: dict[str, tuple[Path, str]] | None = None

    def build(self) -> dict[str, tuple[Path, str]]:
        if self._paths is None:
            paths = {}
            for pack in self.packs:
                for source_path in _run(self.helper, ["list", "--pack", str(pack)])["paths"]:
                    paths.setdefault(canonical_path(source_path), (pack, source_path))
            self._paths = paths
        return self._paths

    def locate(self, path: str) -> tuple[Path, str] | None:
        return self.build().get(canonical_path(path))


class DependencyResolver:
    def __init__(self, pack_index: PackIndex | None = None, cache_root: Path = DEFAULT_ASSET_CACHE):
        self.pack_index = pack_index or PackIndex()
        self.cache_root = Path(cache_root)

    def cache_path(self, path: str) -> Path:
        return self.cache_root.joinpath(*canonical_path(path).split("/"))

    def _dependency(self, path: str, kind: str, parent: str, required: bool = True,
                    metadata: dict[str, Any] | None = None) -> Dependency:
        located = self.pack_index.locate(path)
        cached = self.cache_path(path).is_file()
        shader_default = kind == "TEXTURE" and PurePosixPath(canonical_path(path)).name in SHADER_DEFAULT_TEXTURES
        return Dependency(
            path=canonical_path(located[1] if located else path), kind=kind,
            source_pack=located[0].name if located else None, parent=parent,
            required=required and not shader_default, cache_state="hit" if cached else "virtual" if shader_default else "missing",
            validation_state="valid" if shader_default or cached and located else "missing" if not located else "pending",
            metadata={**(metadata or {}), **({"shader_default": True} if shader_default else {})},
        )

    def _extract_one(self, dependency: Dependency) -> Dependency:
        if dependency.source_pack is None:
            return dependency if dependency.metadata.get("shader_default") else replace(dependency, validation_state="missing")
        target = self.cache_path(dependency.path)
        if target.is_file():
            return replace(dependency, cache_state="hit", validation_state="valid")
        pack = self.pack_index.game_data / dependency.source_pack
        result = _run(self.pack_index.helper, ["extract", "--pack", str(pack), "--path", dependency.path,
                                               "--output-root", str(self.cache_root)])
        output = Path(result["output_path"])
        if not output.is_file():
            raise ConverterError(ErrorCode.MISSING_SOURCE_ASSET, "Pack extraction did not create the dependency",
                                 path=dependency.path, pack=dependency.source_pack)
        return replace(dependency, cache_state="extracted", validation_state="valid")

    @staticmethod
    def _tag(element: ET.Element) -> str:
        return element.tag.rsplit("}", 1)[-1]

    def _acquire_vmd_tree(self, root_path: str) -> tuple[list[Dependency], list[dict[str, Any]], list[Dependency]]:
        vmds: dict[str, Dependency] = {}
        assets: dict[tuple[str, str], Dependency] = {}
        slots: list[dict[str, Any]] = []
        active: list[str] = []

        def visit(path: str, parent: str, inherited_slot: str = "root", inherited_socket: str | None = None) -> None:
            key = canonical_path(path)
            if key in active:
                raise ConverterError(ErrorCode.INCOMPATIBLE_ATTACHMENT, "Recursive VMD reference",
                                     path=key, chain=active + [key])
            dependency = self._extract_one(self._dependency(path, "VMD", parent))
            vmds.setdefault(key, dependency)
            if dependency.validation_state != "valid":
                raise ConverterError(ErrorCode.UNRESOLVED_VMD, "Referenced VMD is absent from configured packs",
                                     path=key, parent=parent)
            active.append(key)
            root = ET.parse(self.cache_path(key)).getroot()

            def walk(node: ET.Element, slot_path: str, socket: str | None) -> None:
                for slot_index, slot in enumerate(child for child in node if self._tag(child) == "SLOT"):
                    name = slot.get("name") or f"slot-{slot_index}"
                    here = f"{slot_path}/{name}"
                    attach = (slot.get("attach_point") or socket or "").strip() or None
                    entries = []
                    for index, child in enumerate(slot):
                        tag = self._tag(child)
                        if tag == "VARIANT_MESH":
                            model = child.get("model")
                            entry = {"index": index, "kind": "model", "model": model,
                                     "definition": key, "attach_point": attach}
                            entries.append(entry)
                            if model:
                                dep = self._dependency(model, "RMV2", f"{key}:{here}[{index}]",
                                                       required=slot.get("probability") in (None, "", "1", "1.0"),
                                                       metadata={"slot_path": here, "attach_point": attach,
                                                                 "definition": key, "entry_index": index})
                                assets.setdefault((dep.kind, dep.path), dep)
                            for attr, value in child.attrib.items():
                                if attr.startswith("decal_") and value:
                                    texture_path = value if Path(value).suffix else value + ".texture_array"
                                    dep = self._dependency(texture_path, "TEXTURE", f"{key}:{here}[{index}]",
                                                           required=False, metadata={"semantic": attr})
                                    assets.setdefault((dep.kind, dep.path), dep)
                            walk(child, f"{here}[{index}]", attach)
                        elif tag == "VARIANT_MESH_REFERENCE" and child.get("definition"):
                            reference = child.get("definition")
                            entries.append({"index": index, "kind": "definition", "definition": reference,
                                            "attach_point": attach})
                            visit(reference, f"{key}:{here}[{index}]", here, attach)
                    slots.append({"definition": key, "slot_path": here, "attach_point": attach,
                                  "probability": slot.get("probability"), "entries": entries})
            walk(root, inherited_slot, inherited_socket)
            active.pop()

        visit(root_path, "catalog.root_vmd")
        return list(vmds.values()), slots, list(assets.values())

    def plan(self, definition: UnitDefinition) -> DependencyPlan:
        variant = next((item for item in definition.variants if item.get("source_pack")), None)
        if variant is None:
            raise ConverterError(ErrorCode.UNRESOLVED_VMD, "Catalog unit has no source-owned root VMD",
                                 unit=definition.main_unit)
        vmds, slots, assets = self._acquire_vmd_tree(variant["path"])
        skeleton_path = f"animations/skeletons/{definition.skeleton}.anim"
        inverse_path = f"animations/skeletons/{definition.skeleton}.bone_inv_trans_mats"
        family_path = f"animations/animation_fragments/{definition.animation_family}_fragment.txt"
        metadata = [
            self._dependency(skeleton_path, "SKELETON", "land_units.man_animation"),
            self._dependency(inverse_path, "SKELETON", skeleton_path),
            self._dependency(family_path, "ANIMATION_METADATA", "land_units.man_animation"),
        ]
        dependencies = tuple(sorted((*vmds, *assets, *metadata), key=lambda item: (item.kind, item.path, item.parent)))
        return DependencyPlan(definition, dependencies, tuple(slots), definition.animation_family,
                              definition.skeleton or "", str(self.cache_root))

    def _rmv2_metadata(self, dependency: Dependency) -> dict[str, Any]:
        return _run(self.pack_index.helper, ["inspect-rmv2", "--input", str(self.cache_path(dependency.path)), "--decode"])

    def extract(self, plan: DependencyPlan) -> DependencyPlan:
        extracted = [self._extract_one(item) for item in plan.dependencies]
        textures: dict[str, Dependency] = {}
        enriched = []
        for dependency in extracted:
            if dependency.kind != "RMV2" or dependency.validation_state != "valid":
                enriched.append(dependency)
                continue
            metadata = self._rmv2_metadata(dependency)
            lods = metadata.get("lods", [])
            highest = next((lod for lod in lods if lod.get("index") == metadata.get("highest_detail_lod", 0)),
                           lods[0] if lods else {"meshes": []})
            meshes = highest.get("meshes", [])
            material_types = sorted({mesh.get("material_type_name") for mesh in meshes
                                     if mesh.get("material_type_name")})
            skeleton = metadata.get("skeleton_id")
            enriched.append(replace(dependency, metadata={**dependency.metadata,
                                                          "inspection": {"rmv2_version": metadata.get("rmv2_version"),
                                                                         "lod_count": metadata.get("lod_count")},
                                                          "material_types": material_types,
                                                          "skeleton": skeleton}))
            for mesh in meshes:
                material = mesh.get("material", {})
                for texture in material.get("textures", []):
                    path = texture.get("path")
                    if path:
                        item = self._dependency(path, "TEXTURE", dependency.path, required=True,
                                                metadata={"semantic": texture.get("type_name"),
                                                          "material": material.get("name")})
                        textures.setdefault(item.path, item)
        extracted_textures = [self._extract_one(item) for item in textures.values()]
        array_entries: dict[str, Dependency] = {}
        for item in (*enriched, *extracted_textures):
            if item.path.endswith(".texture_array") and item.validation_state == "valid":
                for line in self.cache_path(item.path).read_text(encoding="utf-8").splitlines():
                    value = line.strip()
                    if not value:
                        continue
                    path = value if Path(value).suffix else value + ".dds"
                    entry = self._dependency(path, "TEXTURE", item.path, required=False,
                                             metadata={"texture_array_entry": True})
                    array_entries.setdefault(entry.path, entry)
        extracted_textures.extend(self._extract_one(item) for item in array_entries.values())
        enriched.extend(extracted_textures)
        return replace(plan, dependencies=tuple(sorted(enriched, key=lambda item: (item.kind, item.path, item.parent))))

    def validate(self, plan: DependencyPlan) -> tuple[str, tuple[str, ...]]:
        reasons = set()
        for item in plan.dependencies:
            if item.required and item.validation_state != "valid":
                reasons.add(ErrorCode.MISSING_REQUIRED_ASSET.value)
            if item.kind == "RMV2" and item.validation_state == "valid":
                unsupported = set(item.metadata.get("material_types", ())) - SUPPORTED_MATERIALS
                if unsupported:
                    reasons.add(ErrorCode.UNSUPPORTED_MATERIAL.value)
                skeleton = item.metadata.get("skeleton")
                if skeleton and skeleton != plan.skeleton:
                    reasons.add(ErrorCode.SKELETON_MISMATCH.value)
                socket = item.metadata.get("attach_point")
                if socket and not socket.startswith(("weapon_", "crest_")):
                    reasons.add(ErrorCode.INCOMPATIBLE_ATTACHMENT.value)
        return ("READY" if not reasons else "PARTIAL", tuple(sorted(reasons)))

    def resolved_unit(self, plan: DependencyPlan) -> ResolvedUnit:
        status, reasons = self.validate(plan)
        definition = replace(plan.unit, status=status, reason_codes=reasons)
        models = {item.path: item for item in plan.dependencies if item.kind == "RMV2"}
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for slot in plan.slots:
            if any(entry.get("kind") == "model" and entry.get("model") for entry in slot["entries"]):
                groups[self._slot_category(slot)].append(slot)
        component_slots = []
        for key, slots in sorted(groups.items()):
            options = []
            seen = set()
            for slot in slots:
                for entry in slot["entries"]:
                    source = entry.get("model")
                    if not source or canonical_path(source) in seen:
                        continue
                    seen.add(canonical_path(source)); dependency = models.get(canonical_path(source))
                    options.append(ComponentOption(
                        key=canonical_path(source), source_path=source.replace("\\", "/"),
                        definition=slot["definition"], socket=slot.get("attach_point"),
                        skeleton=dependency.metadata.get("skeleton") if dependency else None,
                        material_types=tuple(dependency.metadata.get("material_types", ())) if dependency else (),
                        source_exists=bool(dependency and dependency.validation_state == "valid"),
                    ))
            required = all(slot.get("probability") in (None, "", "1", "1.0") for slot in slots)
            component_slots.append(ComponentSlot(key, tuple(sorted({slot["slot_path"] for slot in slots})),
                                                 required, options[0].key if options else None, tuple(options),
                                                 "runtime_weighted_or_random_source_order; no_authoritative_default_marker"))
        variant = next(item for item in definition.variants if item.get("source_pack"))
        return ResolvedUnit(definition, definition.land_unit, variant["variant"], variant["path"],
                            tuple(component_slots), AnimationProfile(plan.skeleton, plan.animation_family),
                            str(self.cache_root), {"dependency_plan": plan})

    @staticmethod
    def _slot_category(slot: dict[str, Any]) -> str:
        leaf = slot["slot_path"].rsplit("/", 1)[-1].split("[", 1)[0].casefold()
        socket = (slot.get("attach_point") or "").casefold()
        if "skin" in leaf: return "body"
        if "tunic" in leaf or "cloth" in leaf: return "tunic"
        if "armour" in leaf or "armor" in leaf: return "armour"
        if "helmet" in leaf: return "helmet"
        if "crest" in leaf: return "crest"
        if "shield" in leaf or socket == "weapon_03": return "shield"
        if leaf in {"weapon_1", "weapon_2"} or socket in {"weapon_01", "weapon_02"}: return "melee_weapon"
        if leaf in {"weapon_3", "weapon_4"} or socket in {"weapon_04", "weapon_05"}: return "missile_weapon"
        return leaf or "other"


def plan_json(plan: DependencyPlan) -> dict[str, Any]:
    return {
        "format": "rome2aoe2.dependency-plan", "version": 1,
        "unit": plan.unit.main_unit, "animation": {"family": plan.animation_family, "skeleton": plan.skeleton},
        "cache_root": plan.cache_root, "cache_hits": plan.cache_hits, "cache_misses": plan.cache_misses,
        "dependencies": [
            {"path": item.path, "kind": item.kind, "source_pack": item.source_pack,
             "parent": item.parent, "required": item.required, "cache_state": item.cache_state,
             "validation_state": item.validation_state, "metadata": item.metadata}
            for item in plan.dependencies
        ],
        "slots": list(plan.slots),
    }


def plan_from_json(value: dict[str, Any], unit: UnitDefinition) -> DependencyPlan:
    if value.get("format") != "rome2aoe2.dependency-plan" or value.get("version") != 1:
        raise ConverterError(ErrorCode.MISSING_SOURCE_ASSET, "Unsupported dependency plan format",
                             unit=unit.main_unit)
    dependencies = tuple(Dependency(
        path=item["path"], kind=item["kind"], source_pack=item.get("source_pack"),
        parent=item["parent"], required=item["required"], cache_state=item["cache_state"],
        validation_state=item["validation_state"], metadata=item.get("metadata", {}),
    ) for item in value["dependencies"])
    animation = value["animation"]
    return DependencyPlan(unit, dependencies, tuple(value["slots"]), animation["family"],
                          animation["skeleton"], value["cache_root"])


def validated_plan_path(unit_key: str, cache_root: Path = DEFAULT_ASSET_CACHE) -> Path:
    return Path(cache_root).parent / "validated-units-v1" / f"{unit_key.casefold()}.json"


def write_validated_plan(plan: DependencyPlan) -> Path:
    output = validated_plan_path(plan.unit.main_unit, Path(plan.cache_root))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan_json(plan), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
