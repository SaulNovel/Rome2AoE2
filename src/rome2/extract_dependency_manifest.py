"""Extract supported resolved VMD dependencies through rome2aoe2-pack."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class InputError(ValueError):
    """The dependency manifest or command line is malformed."""


def _call_helper(helper: Path, arguments: list[str]) -> dict[str, Any]:
    completed = subprocess.run([str(helper), *arguments], text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError("helper exit {}: {}".format(completed.returncode, completed.stderr.strip()))
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("helper returned invalid JSON: {}".format(error)) from error
    if not isinstance(value, dict):
        raise RuntimeError("helper contract violation: result is not an object")
    return value


def _validate_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InputError("Invalid dependency manifest '{}': {}".format(path, error)) from error
    if not isinstance(manifest, dict) or manifest.get("format_version") not in {2, 3} or not isinstance(manifest.get("dependencies"), list):
        raise InputError("Dependency manifest '{}' must be resolver format_version 2 or 3 with a dependencies list".format(path))
    for index, dependency in enumerate(manifest["dependencies"]):
        if not isinstance(dependency, dict) or not all(isinstance(dependency.get(key), str) for key in ("path", "normalized_path")) or not isinstance(dependency.get("asset_types"), list) or not all(isinstance(kind, str) for kind in dependency["asset_types"]) or not isinstance(dependency.get("origins"), list):
            raise InputError("Dependency manifest entry {} has invalid path, normalized_path, asset_types, or origins".format(index))
        if manifest["format_version"] == 3:
            for origin_index, origin in enumerate(dependency["origins"]):
                if not isinstance(origin, dict) or "attach_point" not in origin or origin["attach_point"] is not None and not isinstance(origin["attach_point"], str):
                    raise InputError("Dependency manifest entry {} origin {} has invalid version-3 attach_point".format(index, origin_index))
    return manifest


def _skip_reason(dependency: dict[str, Any]) -> str | None:
    if dependency["asset_types"] == ["model"] and dependency["path"].casefold().endswith(".rigid_model_v2"):
        return None
    if dependency["asset_types"] == ["texture"] and any(isinstance(origin, dict) and str(origin.get("attribute", "")).startswith("decal_") for origin in dependency["origins"]):
        return None
    return "unsupported asset types or invalid model/decal dependency shape"


def extract(manifest_path: Path, packs: list[Path], helper: Path, output_root: Path) -> dict[str, Any]:
    source = _validate_manifest(manifest_path)
    assets: list[dict[str, Any]] = []; missing: list[dict[str, Any]] = []; failed: list[dict[str, Any]] = []; skipped: list[dict[str, Any]] = []
    for dependency in sorted(source["dependencies"], key=lambda entry: entry["normalized_path"]):
        reason = _skip_reason(dependency)
        common = {key: dependency[key] for key in ("path", "normalized_path", "asset_types", "origins")}
        if reason:
            skipped.append({**common, "reason": reason}); continue
        matches = []
        try:
            for pack in packs:
                result = _call_helper(helper, ["contains", "--pack", str(pack), "--path", dependency["path"]])
                if not isinstance(result.get("exists"), bool): raise RuntimeError("helper contract violation: contains.exists is not boolean")
                if result["exists"]:
                    if not isinstance(result.get("matched_path"), str): raise RuntimeError("helper contract violation: contains.matched_path is not string")
                    matches.append((pack, result["matched_path"]))
        except RuntimeError as error:
            failed.append({**common, "failure_kind": "lookup-failed", "error": str(error)}); continue
        if not matches:
            missing.append({**common, "failure_kind": "not-found", "packs_searched": [pack.name for pack in packs]}); continue
        pack, matched = matches[0]
        try:
            result = _call_helper(helper, ["extract", "--pack", str(pack), "--path", dependency["path"], "--output-root", str(output_root)])
            if result.get("matched_path") != matched or not isinstance(result.get("output_path"), str) or not isinstance(result.get("bytes_written"), int): raise RuntimeError("helper contract violation: extraction result disagrees with selected match")
        except RuntimeError as error:
            failed.append({**common, "failure_kind": "extraction-failed", "pack": pack.name, "matched_path": matched, "error": str(error)}); continue
        assets.append({**common, "pack": pack.name, "matched_path": matched, "output_path": result["output_path"], "bytes_written": result["bytes_written"], "shadowed_packs": [candidate.name for candidate, _ in matches[1:]]})
    status = "failed" if missing or failed else "success-with-skips" if skipped else "success"
    return {"format": "rome2aoe2.asset-extraction", "version": 1, "status": status, "source_dependency_manifest": manifest_path.name, "source_dependency_manifest_version": source["format_version"], "pack_precedence": [pack.name for pack in packs], "assets": assets, "missing": missing, "failed": failed, "skipped": skipped}


def main(arguments: list[str]) -> int:
    values: dict[str, Any] = {"--pack": []}; index = 0
    while index < len(arguments):
        option = arguments[index]; index += 1
        if index == len(arguments): raise InputError("Missing value for {}".format(option))
        value = arguments[index]; index += 1
        if option == "--pack": values[option].append(Path(value))
        elif option in {"--manifest", "--helper", "--output-root", "--extraction-manifest"}: values[option] = Path(value)
        else: raise InputError("Unknown option {}".format(option))
    required = ("--manifest", "--helper", "--output-root", "--extraction-manifest")
    if not values["--pack"] or any(key not in values for key in required): raise InputError("Usage: extract_dependency_manifest.py --manifest <json> --pack <pack> [--pack <pack> ...] --helper <exe> --output-root <dir> --extraction-manifest <json>")
    if len({str(pack.resolve()) for pack in values["--pack"]}) != len(values["--pack"]): raise InputError("Duplicate configured pack path")
    result = extract(values["--manifest"], values["--pack"], values["--helper"], values["--output-root"])
    output = values["--extraction-manifest"]; output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True)); return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    try: raise SystemExit(main(sys.argv[1:]))
    except (OSError, InputError, RuntimeError) as error: print(error, file=sys.stderr); raise SystemExit(2)
