from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .catalog import Catalog, load_default_catalog
from .capabilities import conversion_capabilities
from .dependencies import DEFAULT_ASSET_CACHE, DependencyResolver, canonical_path
from .errors import ConverterError, ErrorCode
from .indexer import DEFAULT_HELPER, SourceIndexer
from .manifest import SUPPORTED_MATERIALS, select_components


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "build/conversions"
DEFAULT_BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
STATIC_POSE = ROOT / "build/local-integration/rome2/animation-v5/sws_stand-frame-0.pose.json"
CONVERTER_VERSION = 1


def deterministic_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"


def manifest_digest(document: dict[str, Any]) -> str:
    compact = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(compact).hexdigest()


@dataclass(frozen=True)
class ConversionRequest:
    manifest: dict[str, Any]
    manifest_hash: str
    unit: Any
    selections: dict[str, Any]
    output_directory: Path


def load_and_validate_manifest(path: Path, catalog: Catalog | None = None,
                               output_root: Path = DEFAULT_OUTPUT_ROOT) -> ConversionRequest:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConverterError(ErrorCode.MANIFEST_SCHEMA_UNSUPPORTED, "Manifest is not valid JSON",
                             path=str(path), error=str(error)) from error
    if document.get("schema_version") not in (1, 2):
        raise ConverterError(ErrorCode.MANIFEST_SCHEMA_UNSUPPORTED, "Unsupported conversion manifest schema",
                             schema_version=document.get("schema_version"), supported=[1, 2])
    source = document.get("source")
    components = document.get("components")
    animation = document.get("animation")
    if not isinstance(source, dict) or not isinstance(components, dict) or not isinstance(animation, dict):
        raise ConverterError(ErrorCode.MANIFEST_SCHEMA_UNSUPPORTED,
                             "Manifest requires source, components, and animation objects")
    catalog = catalog or load_default_catalog()
    resolved = catalog.resolve(source.get("main_unit", ""), source.get("faction"))
    expected = {"main_unit": resolved.definition.main_unit, "land_unit": resolved.land_unit,
                "variant": resolved.variant, "root_vmd": resolved.root_vmd,
                "faction": resolved.definition.faction_key}
    mismatches = {key: {"manifest": source.get(key), "resolved": value}
                  for key, value in expected.items() if source.get(key) != value}
    if mismatches or animation.get("skeleton") != resolved.animation.skeleton or animation.get("family") != resolved.animation.family:
        raise ConverterError(ErrorCode.MANIFEST_UNIT_MISMATCH, "Manifest identity differs from authoritative resolution",
                             unit=source.get("main_unit"), mismatches=mismatches,
                             manifest_animation=animation,
                             resolved_animation={"skeleton": resolved.animation.skeleton, "family": resolved.animation.family})
    if document["schema_version"] == 2:
        from .animation import CATEGORIES, file_sha256
        animations = document.get("animations")
        if not isinstance(animations, dict) or set(animations) != set(CATEGORIES):
            raise ConverterError(ErrorCode.MANIFEST_SCHEMA_UNSUPPORTED,
                                 "Animated manifest requires exact idle/walk/attack/death selections")
        for category in CATEGORIES:
            row = animations[category]
            if (not isinstance(row, dict) or row.get("category") != category
                    or not isinstance(row.get("resolved_asset"), str)):
                raise ConverterError(ErrorCode.MANIFEST_SCHEMA_UNSUPPORTED,
                                     "Frozen animation selection is malformed", category=category)
            canonical = canonical_path(row["resolved_asset"])
            local = DEFAULT_ASSET_CACHE / Path(*canonical.split("/"))
            if not local.is_file():
                # Validation/development caches may preserve an exact canonical asset outside assets-v1.
                from .animation import ASSET_ROOTS, _find_asset
                local = _find_asset(canonical, ASSET_ROOTS)
            if local is None or not local.is_file() or row.get("asset_sha256") != file_sha256(local):
                raise ConverterError(ErrorCode.ANIMATION_DEPENDENCY_MISMATCH,
                                     "Frozen animation dependency is absent or changed",
                                     category=category, asset=canonical)
    known = {slot.key for slot in resolved.component_slots}
    if set(components) != known:
        raise ConverterError(ErrorCode.MANIFEST_COMPONENT_INVALID, "Manifest component slots differ from resolved unit",
                             missing=sorted(known - set(components)), unknown=sorted(set(components) - known))
    choices = {}
    for key, row in components.items():
        if row is None:
            choices[key] = None
        elif isinstance(row, dict) and isinstance(row.get("key"), str):
            if row.get("source_path") and canonical_path(row["source_path"]) != canonical_path(row["key"]):
                raise ConverterError(ErrorCode.MANIFEST_COMPONENT_INVALID,
                                     "Component key and source path identify different assets",
                                     component=key, key=row.get("key"), source_path=row.get("source_path"))
            choices[key] = canonical_path(row["key"])
        else:
            raise ConverterError(ErrorCode.MANIFEST_COMPONENT_INVALID, "Component selection is malformed",
                                 component=key)
    try:
        selected = select_components(resolved, choices)
    except ConverterError as error:
        if error.code == ErrorCode.COMPONENT_NOT_FOUND:
            raise ConverterError(ErrorCode.MANIFEST_COMPONENT_INVALID, error.message, **error.context) from error
        raise
    for key, option in selected.items():
        row = components[key]
        if option is None:
            continue
        selection = row.get("selection")
        expected = {
            "key": option.key, "source_path": option.source_path,
            "definition": option.definition, "socket": option.socket,
            "skeleton": option.skeleton, "material_types": list(option.material_types),
        }
        mismatched = {field: {"manifest": row.get(field), "resolved": value}
                      for field, value in expected.items() if row.get(field) != value}
        if not isinstance(selection, dict) or selection.get("resolved_asset") != option.key:
            mismatched["selection.resolved_asset"] = {
                "manifest": selection.get("resolved_asset") if isinstance(selection, dict) else None,
                "resolved": option.key,
            }
        mode = selection.get("mode") if isinstance(selection, dict) else None
        policy = selection.get("resolution_policy") if isinstance(selection, dict) else None
        slot = next(item for item in resolved.component_slots if item.key == key)
        valid_semantics = (
            mode == "deterministic_source_first" and policy == "first_distinct_source"
            and option.key == slot.default_key
        ) or (mode == "explicit" and policy == "exact_manifest_asset")
        if not valid_semantics:
            mismatched["selection.mode"] = {
                "manifest": {"mode": mode, "resolution_policy": policy},
                "resolved": "deterministic_source_first/first_distinct_source or explicit/exact_manifest_asset",
            }
        if mismatched:
            raise ConverterError(ErrorCode.MANIFEST_COMPONENT_INVALID,
                                 "Manifest component metadata differs from authoritative resolution",
                                 component=key, mismatches=mismatched)
    plan = resolved.raw_identity.get("dependency_plan") if isinstance(resolved.raw_identity, dict) else None
    if resolved.definition.status != "READY" or plan is None:
        raise ConverterError(ErrorCode.MISSING_REQUIRED_ASSET, "Manifest unit lacks a READY validated dependency closure",
                             unit=resolved.definition.main_unit, status=resolved.definition.status)
    digest = manifest_digest(document)
    output = Path(output_root) / resolved.definition.main_unit.casefold() / digest
    return ConversionRequest(document, digest, resolved, selected, output)


def _call(arguments: list[str]) -> dict[str, Any]:
    result = subprocess.run(arguments, capture_output=True, text=True)
    if result.returncode:
        raise ConverterError(ErrorCode.MISSING_REQUIRED_ASSET, "Conversion subprocess failed",
                             command=arguments, stderr=result.stderr.strip())
    return json.loads(result.stdout) if result.stdout.strip().startswith("{") else {"stdout": result.stdout.strip()}


def _export_assets(request: ConversionRequest, resolver: DependencyResolver, output: Path) -> list[dict[str, Any]]:
    skeleton = resolver.cache_path(f"animations/skeletons/{request.unit.animation.skeleton}.anim")
    inverse = resolver.cache_path(f"animations/skeletons/{request.unit.animation.skeleton}.bone_inv_trans_mats")
    exports = []
    for component, option in sorted(request.selections.items()):
        if option is None:
            continue
        source = resolver.cache_path(option.key)
        target = output / "gltf" / component / f"{Path(option.key).stem}.gltf"
        target.parent.mkdir(parents=True, exist_ok=True)
        arguments = [str(DEFAULT_HELPER), "export-rmv2-gltf", "--input", str(source),
                     "--output", str(target), "--lod", "highest"]
        if option.skeleton:
            arguments += ["--skeleton-anim", str(skeleton), "--inverse-bind", str(inverse)]
        metadata = _call(arguments)
        exports.append({"component": component, "source_path": option.key, "gltf": str(target),
                        "socket": option.socket, "skeleton": option.skeleton,
                        "material_types": list(option.material_types), "export": metadata})
    return exports


def _texture_manifest(exports: list[dict[str, Any]], resolver: DependencyResolver) -> dict[str, Any]:
    materials = []
    for export in exports:
        document = json.loads(Path(export["gltf"]).read_text(encoding="utf-8"))
        for material in document.get("materials", []):
            extra = material.get("extras", {}).get("rome2aoe2", {})
            material_type = extra.get("type")
            if material_type not in SUPPORTED_MATERIALS:
                raise ConverterError(ErrorCode.UNSUPPORTED_MATERIAL, "Exported material is unsupported",
                                     asset=export["source_path"], material=material.get("name"), material_type=material_type)
            textures = []
            for texture in extra.get("textures", []):
                source_path = canonical_path(texture["path"])
                cached = resolver.cache_path(source_path)
                sentinel = Path(source_path).name in {"test_black.dds", "test_mask.dds"}
                textures.append({
                    "semantic": texture["type"], "source_path": source_path,
                    "status": "shader_default" if sentinel else "resolved",
                    **({"default_rgba": [0, 0, 0, 0]} if sentinel else
                       {"extracted_path": source_path, "resolved_path": source_path,
                        "color_space": "sRGB" if texture["type"] in {"Diffuse", "Specular", "DecalDiffuse"} else "Non-Color"}),
                })
                if not sentinel and not cached.is_file():
                    raise ConverterError(ErrorCode.MISSING_REQUIRED_ASSET, "Material texture is absent from shared cache",
                                         asset=export["source_path"], texture=source_path)
            materials.append({"material_name": material["name"], "material_type": material_type,
                              "source_models": [export["source_path"]], "textures": textures,
                              "parameters": extra.get("parameters", {"float": [], "integer": [], "string": [], "vector4": []}),
                              "shader_flags": {"dirt": "Dirtmap" in material_type, "alpha_test": material.get("alphaMode") == "MASK"}})
    return {"format": "rome2aoe2.texture-manifest", "version": 1, "materials": materials}


def _faction_colours(unit) -> dict[str, Any]:
    indexer = SourceIndexer()
    overrides = [row for row in indexer._table("unit_variants_colours")
                 if row.get("unit_variant") == unit.variant and row.get("faction") in {unit.definition.faction_key, ""}]
    exact = next((row for row in overrides if row.get("faction") == unit.definition.faction_key), None)
    default = next((row for row in overrides if not row.get("faction")), None)
    uniform = next((row for row in indexer._table("faction_uniform_colours")
                    if row.get("faction_name") == unit.definition.faction_key), None)
    selected = exact or default or uniform
    if selected is None:
        raise ConverterError(ErrorCode.MISSING_REQUIRED_ASSET, "Faction colour source did not resolve",
                             faction=unit.definition.faction_key, variant=unit.variant)
    return {"primary": selected["primary_colour_hex"], "secondary": selected["secondary_colour_hex"],
            "tertiary": selected["tertiary_colour_hex"],
            "source": "unit_variants_colours:faction" if exact else
                      "unit_variants_colours:default" if default else "faction_uniform_colours",
            "source_key": unit.definition.faction_key if uniform else unit.variant}


def _git_commit() -> str | None:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def convert(manifest_path: Path, catalog: Catalog | None = None, output_root: Path = DEFAULT_OUTPUT_ROOT,
            blender: Path = DEFAULT_BLENDER, execute_blender: bool = True,
            blade_capability: str = "one_handed_blade_v3_source_frame_forward_corrected") -> dict[str, Any]:
    request = load_and_validate_manifest(manifest_path, catalog, output_root)
    from .native_assembly import static_assembly_identity
    output = output_root / request.unit.definition.main_unit.casefold() / static_assembly_identity(
        request.manifest, blade_capability)
    output.mkdir(parents=True, exist_ok=True)
    resolver = DependencyResolver(cache_root=Path(request.unit.source_root))
    exports = _export_assets(request, resolver, output)
    textures = _texture_manifest(exports, resolver)
    capabilities = conversion_capabilities(
        (row["material_type"] for row in textures["materials"]), blade_capability)
    texture_path = output / "texture-manifest.json"
    texture_path.write_text(deterministic_json(textures), encoding="utf-8")
    colours = _faction_colours(request.unit)
    assembly_input = {
        "format": "rome2aoe2.static-assembly-input", "version": 1,
        "unit": request.unit.definition.main_unit, "manifest_hash": request.manifest_hash,
        "exports": exports, "texture_manifest": str(texture_path), "texture_root": str(resolver.cache_root),
        "faction_colours": colours, "static_pose": str(STATIC_POSE),
        "one_handed_blade_capability": blade_capability,
        "directions": [45, 135, 225, 315],
    }
    assembly_path = output / "static-assembly-input.json"
    assembly_path.write_text(deterministic_json(assembly_input), encoding="utf-8")
    blender_report = output / "static-assembly-report.json"
    if execute_blender:
        if not blender.is_file():
            raise ConverterError(ErrorCode.MISSING_REQUIRED_ASSET, "Blender executable is missing", path=str(blender))
        command = [str(blender), "--background", "--python", str(ROOT / "src/blender/assemble_manifest_static.py"),
                   "--", "--input", str(assembly_path), "--output", str(output), "--report", str(blender_report)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            raise ConverterError(ErrorCode.MISSING_REQUIRED_ASSET, "Static Blender assembly failed",
                                 command=command, stdout=result.stdout[-4000:], stderr=result.stderr[-4000:])
        if not blender_report.is_file():
            raise ConverterError(ErrorCode.MISSING_REQUIRED_ASSET,
                                 "Blender exited without producing the required static assembly report",
                                 command=command, stdout=result.stdout[-4000:], stderr=result.stderr[-4000:])
    assembly = json.loads(blender_report.read_text(encoding="utf-8")) if blender_report.is_file() else None
    plan = request.unit.raw_identity["dependency_plan"]
    receipt = {
        "format": "rome2aoe2.conversion-receipt", "version": 1, "converter_version": CONVERTER_VERSION,
        "git_commit": _git_commit(), "manifest_schema_version": request.manifest["schema_version"],
        "manifest_hash": request.manifest_hash, "unit": request.unit.definition.main_unit,
        "selected_assets": {key: None if value is None else value.key for key, value in request.selections.items()},
        "dependency_plan": {"unit": plan.unit.main_unit, "dependencies": len(plan.dependencies),
                            "cache_hits": plan.cache_hits, "cache_acquisitions": plan.cache_misses},
        "source_pack_provenance": sorted({item.source_pack for item in plan.dependencies if item.source_pack}),
        "exports": exports, "material_validation": {"supported": True,
                    "families": sorted({kind for row in exports for kind in row["material_types"]})},
        "faction_colours": colours, "attachment_validation": assembly.get("attachments") if assembly else None,
        "capabilities": capabilities,
        "outputs": assembly.get("outputs") if assembly else {"assembly_input": str(assembly_path)},
    }
    receipt_path = output / "conversion-receipt.json"
    receipt["receipt_path"] = str(receipt_path)
    receipt_path.write_text(deterministic_json(receipt), encoding="utf-8")
    return receipt
