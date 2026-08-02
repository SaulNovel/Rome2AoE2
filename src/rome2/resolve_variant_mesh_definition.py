"""Resolve first-choice VariantMeshDefinition XML dependencies.

This module deliberately operates on already-extracted XML. Pack archive access
belongs to the later RPFM-backed extraction stage.
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional


TEXTURE_ATTRIBUTE_PREFIX = "decal_"


class VariantMeshDefinitionResolutionError(RuntimeError):
    """Base error for a deterministic, user-facing resolver failure."""


class MissingVariantMeshDefinitionError(VariantMeshDefinitionResolutionError):
    """A selected local VARIANT_MESH_REFERENCE did not resolve to a file."""

    def __init__(self, referring_definition, referenced_definition, slot_path, reference_chain):
        self.referring_definition = referring_definition
        self.referenced_definition = referenced_definition
        self.slot_path = slot_path
        self.reference_chain = reference_chain
        super().__init__(
            "Missing referenced VariantMeshDefinition: referring_definition='{}' "
            "referenced_definition='{}' slot_path='{}' reference_chain='{}'".format(
                referring_definition, referenced_definition, slot_path, " -> ".join(reference_chain)
            )
        )


class VariantMeshDefinitionCycleError(VariantMeshDefinitionResolutionError):
    """A selected VARIANT_MESH_REFERENCE would recurse into its active chain."""


def normalized_pack_path(value: str) -> str:
    """Return the case-folded comparison key for a pack-relative path.

    The manifest always retains the original XML spelling separately. This key is
    used only for comparison, deduplication, and cycle detection.
    """
    candidate = value.strip().replace("\\", "/")
    if (
        not candidate
        or candidate.startswith("/")
        or (len(candidate) >= 2 and candidate[1] == ":")
    ):
        raise ValueError("Asset paths must be relative to a pack: {!r}".format(value))
    normalized_path = PurePosixPath(candidate)
    normalized = str(normalized_path)
    if normalized in {"", ".", ".."} or ".." in normalized_path.parts:
        raise ValueError("Asset paths must be relative to a pack: {!r}".format(value))
    return normalized.casefold()


def _portable_pack_path(value: str) -> PurePosixPath:
    """Validate a pack-relative path and return it with forward separators."""
    normalized_pack_path(value)
    return PurePosixPath(value.strip().replace("\\", "/"))


def _tag_name(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _first_variant(slot: ElementTree.Element) -> Optional[ElementTree.Element]:
    for child in slot:
        if _tag_name(child) in {"VARIANT_MESH", "VARIANT_MESH_REFERENCE"}:
            return child
    return None


def _relative_definition_path(definition_path: Path, definition_root: Path) -> str:
    try:
        return definition_path.relative_to(definition_root).as_posix()
    except ValueError:
        raise ValueError(
            "Definition '{}' is outside VariantMeshDefinition root '{}'".format(
                definition_path, definition_root
            )
        )


def _resolve_local_reference(definition_root: Path, reference_path: str) -> Optional[Path]:
    """Map a pack-relative reference to an extracted local XML fixture/file.

    Direct lookup preserves the reference spelling. The case-insensitive fallback
    matches Rome II pack-key comparison without changing the output source path.
    """
    portable_path = _portable_pack_path(reference_path)
    direct = definition_root.joinpath(*portable_path.parts)
    if direct.is_file():
        return direct.resolve()

    candidate = definition_root
    for component in portable_path.parts:
        if not candidate.is_dir():
            return None
        matches = sorted(
            (child for child in candidate.iterdir() if child.name.casefold() == component.casefold()),
            key=lambda child: child.name,
        )
        if len(matches) != 1:
            return None
        candidate = matches[0]
    return candidate.resolve() if candidate.is_file() else None


def resolve(definition_path: Path, definition_root: Optional[Path] = None) -> Dict[str, object]:
    """Resolve selected local XML dependencies into a deterministic manifest.

    ``definition_root`` is the directory representing extracted
    VariantMeshDefinition pack paths. Models and textures are intentionally not
    checked here: their archive extraction is a later stage.
    """
    entry_definition = Path(definition_path).resolve()
    root_directory = Path(definition_root).resolve() if definition_root else entry_definition.parent
    root_definition = _relative_definition_path(entry_definition, root_directory)
    dependencies: Dict[str, Dict[str, object]] = {}
    definitions: Dict[str, Dict[str, str]] = {}
    parsed_definitions: Dict[str, ElementTree.Element] = {}

    def definition_display(path: Path) -> str:
        return _relative_definition_path(path, root_directory)

    def parse_definition(path: Path) -> ElementTree.Element:
        comparison_key = normalized_pack_path(definition_display(path))
        if comparison_key not in parsed_definitions:
            root = ElementTree.parse(path).getroot()
            if _tag_name(root) != "VARIANT_MESH":
                raise ValueError("Expected VARIANT_MESH root in {}".format(path))
            parsed_definitions[comparison_key] = root
        return parsed_definitions[comparison_key]

    def add_definition(path: Path) -> str:
        display_path = definition_display(path)
        comparison_key = normalized_pack_path(display_path)
        definitions.setdefault(
            comparison_key,
            {"path": display_path, "normalized_path": comparison_key},
        )
        return comparison_key

    def add_dependency(
        original_path: str,
        attribute: str,
        definition: str,
        slot_path: List[str],
        reference_chain: List[str],
        attach_point: Optional[str],
    ) -> None:
        comparison_key = normalized_pack_path(original_path)
        dependency = dependencies.setdefault(
            comparison_key,
            {
                "path": original_path,
                "normalized_path": comparison_key,
                "asset_types": set(),
                "origins": [],
            },
        )
        dependency["asset_types"].add("model" if attribute == "model" else "texture")
        dependency["origins"].append(
            {
                "attribute": attribute,
                "attach_point": attach_point,
                "definition": definition,
                "reference_chain": list(reference_chain),
                "slot_path": "/".join(slot_path),
            }
        )

    def visit_definition(
        path: Path,
        slot_path: List[str],
        reference_chain: List[str],
        active_chain: List[str],
        attach_point: Optional[str],
    ) -> None:
        display_path = definition_display(path)
        comparison_key = add_definition(path)
        if comparison_key in active_chain:
            cycle_start = active_chain.index(comparison_key)
            cycle_paths = reference_chain[cycle_start:]
            raise VariantMeshDefinitionCycleError(
                "Recursive VariantMeshDefinition reference detected: {}".format(" -> ".join(cycle_paths))
            )
        visit_variant(
            parse_definition(path),
            display_path,
            slot_path,
            reference_chain,
            active_chain + [comparison_key],
            attach_point,
        )

    def visit_variant(
        variant: ElementTree.Element,
        definition: str,
        slot_path: List[str],
        reference_chain: List[str],
        active_chain: List[str],
        attach_point: Optional[str],
    ) -> None:
        if variant.get("model"):
            add_dependency(
                variant.attrib["model"],
                "model",
                definition,
                slot_path,
                reference_chain,
                attach_point,
            )
        for attribute, value in variant.attrib.items():
            if attribute.startswith(TEXTURE_ATTRIBUTE_PREFIX) and value:
                add_dependency(
                    value,
                    attribute,
                    definition,
                    slot_path,
                    reference_chain,
                    attach_point,
                )

        for child in variant:
            if _tag_name(child) != "SLOT":
                continue
            selected = _first_variant(child)
            if selected is None:
                continue
            selected_slot_path = slot_path + [child.get("name", "<unnamed>")]
            declared_attach_point = child.get("attach_point")
            selected_attach_point = (
                declared_attach_point.strip()
                if declared_attach_point and declared_attach_point.strip()
                else attach_point
            )
            if _tag_name(selected) == "VARIANT_MESH":
                visit_variant(
                    selected,
                    definition,
                    selected_slot_path,
                    reference_chain,
                    active_chain,
                    selected_attach_point,
                )
                continue

            reference_path = selected.get("definition")
            if not reference_path:
                raise ValueError(
                    "VARIANT_MESH_REFERENCE in '{}' at slot '{}' has no definition attribute".format(
                        definition, "/".join(selected_slot_path)
                    )
                )
            target = _resolve_local_reference(root_directory, reference_path)
            if target is None:
                raise MissingVariantMeshDefinitionError(
                    definition,
                    reference_path,
                    "/".join(selected_slot_path),
                    reference_chain + [reference_path],
                )
            visit_definition(
                target,
                selected_slot_path,
                reference_chain + [definition_display(target)],
                active_chain,
                selected_attach_point,
            )

    visit_definition(entry_definition, [], [root_definition], [], None)

    manifest_dependencies = []
    for comparison_key in sorted(dependencies):
        dependency = dependencies[comparison_key]
        manifest_dependencies.append(
            {
                "asset_types": sorted(dependency["asset_types"]),
                "normalized_path": dependency["normalized_path"],
                "origins": sorted(
                    dependency["origins"],
                    key=lambda origin: (
                        tuple(origin["reference_chain"]),
                        origin["definition"],
                        origin["slot_path"],
                        origin["attribute"],
                        origin["attach_point"] or "",
                    ),
                ),
                "path": dependency["path"],
            }
        )

    return {
        "definitions": [definitions[key] for key in sorted(definitions)],
        "dependencies": manifest_dependencies,
        "format_version": 3,
        "root_definition": root_definition,
        "selection_strategy": "first-variant-per-slot",
    }


def manifest_json(manifest: Dict[str, object]) -> str:
    """Serialize a manifest with a fixed layout suitable for reproducible output."""
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def write_manifest(definition_path: Path, output_path: Path, definition_root: Optional[Path] = None) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as output:
        output.write(manifest_json(resolve(definition_path, definition_root)))


def main(arguments: Iterable[str]) -> int:
    arguments = list(arguments)
    if len(arguments) not in {2, 3}:
        print(
            "Usage: resolve_variant_mesh_definition.py <input-variantmeshdefinition> <output-manifest.json> [definition-root]",
            file=sys.stderr,
        )
        return 2
    try:
        write_manifest(
            Path(arguments[0]),
            Path(arguments[1]),
            Path(arguments[2]) if len(arguments) == 3 else None,
        )
    except (OSError, ValueError, ElementTree.ParseError, VariantMeshDefinitionResolutionError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
