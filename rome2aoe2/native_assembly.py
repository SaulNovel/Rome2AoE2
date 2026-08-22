from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .animation import AnimationCandidate, file_sha256
from .conversion import DEFAULT_BLENDER, DEFAULT_OUTPUT_ROOT, manifest_digest
from .errors import ConverterError, ErrorCode


ROOT = Path(__file__).resolve().parents[1]
ASSET_CACHE = ROOT / "build/cache/rome2aoe2/assets-v1"
RUNNER = ROOT / "build/community_tool_investigation/asset-editor-animation-runner/bin/Release/net10.0-windows/AssetEditorAnimationRunner.exe"
SKELETON = ASSET_CACHE / "animations/skeletons/rome_man_game.anim"
EXPORTER_ID = "AssetEditorAnimationRunner-RmvToGltfExporter-20260820"
ASSEMBLY_VERSION = "asset-editor-native-basis-v2-category-preview-framing"
EXPORT_CACHE = ROOT / "build/cache/rome2aoe2/native-weighted-exports-v1"


def static_visual_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Return the schema-v1 identity used by static conversion artifacts."""
    document = json.loads(json.dumps(manifest))
    document.pop("animations", None)
    document["schema_version"] = 1
    return document


@dataclass(frozen=True)
class ClassifiedComponent:
    component: str
    source_path: str
    deformation: str
    skeleton: str | None
    socket: str | None
    evidence: str


def classify_components(manifest: Mapping[str, Any]) -> tuple[ClassifiedComponent, ...]:
    result = []
    expected = manifest["animation"]["skeleton"]
    for component, row in sorted(manifest["components"].items()):
        if row is None:
            continue
        skeleton, socket = row.get("skeleton"), row.get("socket")
        if skeleton == expected and not socket:
            deformation, evidence = "weighted", "RMV2 weighted skeleton identity matches selected animation skeleton"
        elif socket:
            deformation, evidence = "rigid", "resolved VMD attach-point/socket"
        else:
            raise ConverterError(ErrorCode.INCOMPATIBLE_NATIVE_REST_BASIS,
                                 "Component deformation type cannot be established from source data",
                                 component=component, skeleton=skeleton, socket=socket)
        result.append(ClassifiedComponent(component, row["source_path"], deformation, skeleton, socket, evidence))
    return tuple(result)


def _asset(source_path: str) -> Path:
    return ASSET_CACHE / Path(*source_path.replace("\\", "/").split("/"))


def export_identity(component: ClassifiedComponent, candidate: AnimationCandidate) -> str:
    source = _asset(component.source_path)
    payload = {"rmv2": file_sha256(source), "skeleton": file_sha256(SKELETON),
               "animation": file_sha256(Path(candidate.local_asset)), "exporter": EXPORTER_ID,
               "options": "mesh+skin+animation/no-textures"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def export_weighted(component: ClassifiedComponent, candidate: AnimationCandidate) -> tuple[Path, bool, dict]:
    if component.deformation != "weighted":
        raise ValueError("native weighted export requested for rigid component")
    identity = export_identity(component, candidate)
    directory, output, report = EXPORT_CACHE / identity, EXPORT_CACHE / identity / "native.gltf", EXPORT_CACHE / identity / "export.json"
    if output.is_file() and report.is_file():
        document = json.loads(report.read_text())
        raw_label = document.get("runner_reported_clip", document.get("clip"))
        document.update({"runner_reported_clip": raw_label,
                         "requested_animation_clip": candidate.resolved_asset,
                         "basis_export_clip": candidate.resolved_asset,
                         "canonical_action_clip": candidate.resolved_asset,
                         "requested_animation_sha256": file_sha256(Path(candidate.local_asset)),
                         "asset_editor_invocation": [str(RUNNER), str(_asset(component.source_path)), str(SKELETON),
                                                     candidate.local_asset, str(output)]})
        document.pop("clip", None)
        report.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
        return output, True, document
    source = _asset(component.source_path)
    directory.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([str(RUNNER), str(source), str(SKELETON), candidate.local_asset, str(output)],
                            capture_output=True, text=True)
    if result.returncode:
        raise ConverterError(ErrorCode.PREVIEW_GENERATION_FAILED, "Native weighted component export failed",
                             component=component.component, stderr=result.stderr[-2000:])
    document = json.loads(result.stdout)
    raw_label = document.pop("clip", None)
    document.update({"cache_identity": identity, "component": component.component,
                     "source_path": component.source_path, "exporter": EXPORTER_ID,
                     "runner_reported_clip": raw_label,
                     "requested_animation_clip": candidate.resolved_asset,
                     "basis_export_clip": candidate.resolved_asset,
                     "canonical_action_clip": candidate.resolved_asset,
                     "requested_animation_sha256": file_sha256(Path(candidate.local_asset)),
                     "asset_editor_invocation": [str(RUNNER), str(source), str(SKELETON), candidate.local_asset, str(output)]})
    report.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return output, False, document


def assemble_native(manifest: Mapping[str, Any], candidate: AnimationCandidate,
                    blender: Path = DEFAULT_BLENDER) -> tuple[Path, dict]:
    classified = classify_components(manifest)
    exports = []
    for component in classified:
        if component.deformation == "weighted":
            gltf, hit, report = export_weighted(component, candidate)
            exports.append({"component": component.component, "source_path": component.source_path,
                            "gltf": str(gltf), "cache_hit": hit, "export": report})
    visual_manifest = static_visual_manifest(manifest)
    identity = hashlib.sha256(json.dumps({"manifest": manifest_digest(visual_manifest),
                                          "clip": candidate.resolved_asset, "version": ASSEMBLY_VERSION},
                                         sort_keys=True).encode()).hexdigest()
    directory = ROOT / "build/validation/rome2aoe2/native-basis-proof" / identity
    output, report = directory / "native-unit.blend", directory / "assembly-report.json"
    static = DEFAULT_OUTPUT_ROOT / manifest["source"]["main_unit"].casefold() / manifest_digest(visual_manifest) / "static-unit.blend"
    input_doc = {"format": "rome2aoe2.native-basis-assembly-input", "version": 1,
                 "assembly_version": ASSEMBLY_VERSION, "static_blend": str(static),
                 "classification": [item.__dict__ for item in classified], "native_exports": exports,
                 "output_blend": str(output), "report": str(report),
                 "category": candidate.category, "clip": candidate.resolved_asset}
    directory.mkdir(parents=True, exist_ok=True)
    input_path = directory / "input.json"
    input_path.write_text(json.dumps(input_doc, indent=2, sort_keys=True) + "\n")
    result = subprocess.run([str(blender), "--background", "--python", str(ROOT / "src/blender/assemble_native_basis_animation.py"),
                             "--", "--input", str(input_path)], capture_output=True, text=True)
    if result.returncode or "Traceback (most recent call last)" in result.stdout:
        raise ConverterError(ErrorCode.INCOMPATIBLE_NATIVE_REST_BASIS, "Native-basis Blender assembly failed",
                             stdout=result.stdout[-4000:], stderr=result.stderr[-2000:])
    return output, json.loads(report.read_text())
