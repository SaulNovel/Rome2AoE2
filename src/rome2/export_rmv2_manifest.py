"""Batch-export extracted RMV2 assets while preserving dependency provenance."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Callable


class InputError(ValueError):
    """The extraction manifest or command line is malformed."""


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InputError("Invalid asset-extraction manifest '{}': {}".format(path, error)) from error
    if not isinstance(value, dict) or value.get("format") != "rome2aoe2.asset-extraction" or value.get("version") != 1 or not isinstance(value.get("assets"), list):
        raise InputError("Asset-extraction manifest must have format rome2aoe2.asset-extraction version 1 and an assets list")
    return value


def _relative_output(normalized_path: str) -> PurePosixPath:
    path = PurePosixPath(normalized_path.replace("\\", "/"))
    suffix = ".rigid_model_v2"
    if path.is_absolute() or ".." in path.parts or not path.name.casefold().endswith(suffix):
        raise InputError("Unsafe or non-RMV2 model identity '{}'".format(normalized_path))
    parts = list(path.parts)
    if [part.casefold() for part in parts[:3]] == ["variantmeshes", "_variantmodels", "man"]:
        parts = parts[3:]
    parts[-1] = parts[-1][:-len(suffix)] + ".gltf"
    return PurePosixPath(*parts)


def _invoke(helper: Path, arguments: list[str]) -> dict[str, Any]:
    completed = subprocess.run([str(helper), *arguments], text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError("helper exit {}: {}".format(completed.returncode, completed.stderr.strip()))
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("helper returned invalid JSON: {}".format(error)) from error
    if not isinstance(result, dict) or result.get("format") != "rome2aoe2.rmv2-gltf-export":
        raise RuntimeError("helper returned an invalid RMV2 glTF export result")
    return result


def export_manifest(manifest_path: Path, helper: Path, output_root: Path, lod: str = "highest", invoke: Callable = _invoke) -> dict[str, Any]:
    source = _read_manifest(manifest_path)
    exports: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    models = sorted(source["assets"], key=lambda asset: str(asset.get("normalized_path", "")).casefold())
    for index, asset in enumerate(models):
        if not isinstance(asset, dict) or not all(isinstance(asset.get(key), str) for key in ("normalized_path", "output_path")) or not isinstance(asset.get("asset_types"), list) or not isinstance(asset.get("origins", []), list):
            raise InputError("Asset entry {} has invalid identity, extraction path, or origins".format(index))
        provenance = {"source_model_path": asset["normalized_path"], "origins": asset.get("origins", [])}
        if asset["asset_types"] != ["model"] or not asset["normalized_path"].casefold().endswith(".rigid_model_v2"):
            skipped.append({**provenance, "reason": "not an extracted RMV2 model"})
            continue
        relative = _relative_output(asset["normalized_path"])
        output_path = output_root.joinpath(*relative.parts)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        input_path = Path(asset["output_path"])
        if not input_path.is_absolute() and not input_path.is_file():
            input_path = manifest_path.parent / input_path
        try:
            metadata = invoke(helper, ["export-rmv2-gltf", "--input", str(input_path), "--output", str(output_path), "--lod", lod])
            exports.append({
                **provenance,
                "output_path": relative.as_posix(),
                "selected_lod": metadata["selected_lod"],
                "mesh_count": metadata["mesh_count"],
                "vertex_count": metadata["vertex_count"],
                "triangle_count": metadata["triangle_count"],
                "rmv2_version": metadata.get("rmv2_version"),
                "skeleton_id": metadata.get("skeleton_id"),
                "materials": metadata.get("materials", metadata.get("material_types", [])),
            })
        except (KeyError, OSError, RuntimeError) as error:
            failed.append({**provenance, "output_path": relative.as_posix(), "failure_kind": "export-failed", "error": str(error)})
    status = "failed" if failed and not exports else "success-with-skips" if failed or skipped else "success"
    return {"format": "rome2aoe2.rmv2-batch-export", "version": 1, "status": status, "source_manifest": manifest_path.name, "lod": lod, "exports": exports, "skipped": skipped, "failed": failed}


def main(arguments: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--helper", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--export-manifest", required=True, type=Path)
    parser.add_argument("--lod", default="highest")
    args = parser.parse_args(arguments)
    result = export_manifest(args.manifest, args.helper, args.output_root, args.lod)
    args.export_manifest.parent.mkdir(parents=True, exist_ok=True)
    args.export_manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (OSError, InputError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(2)
