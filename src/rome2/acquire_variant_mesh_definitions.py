"""Acquire selected VariantMeshDefinition files through rome2aoe2-pack."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rome2.resolve_variant_mesh_definition import MissingVariantMeshDefinitionError, manifest_json, normalized_pack_path, resolve


def helper_result(helper, arguments):
    completed = subprocess.run([str(helper), *arguments], capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError("rome2aoe2-pack failed ({}): {}".format(completed.returncode, completed.stderr.strip()))
    return json.loads(completed.stdout)


def acquire(helper, packs, root_path, output_root):
    if not packs:
        raise ValueError("At least one --pack is required")
    output_root = Path(output_root)
    root_path = str(root_path)
    acquired = {}

    def extract(requested):
        key = normalized_pack_path(requested)
        if key in acquired:
            return
        matches = []
        for pack in packs:
            result = helper_result(helper, ["contains", "--pack", str(pack), "--path", requested])
            if result["exists"]:
                matches.append((pack, result["matched_path"]))
        if not matches:
            raise RuntimeError("VariantMeshDefinition '{}' was not found in configured packs".format(requested))
        pack, matched_path = matches[0]
        result = helper_result(helper, ["extract", "--pack", str(pack), "--path", requested, "--output-root", str(output_root)])
        acquired[key] = {
            "path": result["matched_path"], "normalized_path": normalized_pack_path(result["matched_path"]),
            "pack": Path(pack).name, "output_path": result["output_path"],
            "shadowed_packs": [Path(candidate).name for candidate, _ in matches[1:]],
        }

    extract(root_path)
    root_file = output_root.joinpath(*acquired[normalized_pack_path(root_path)]["path"].replace("\\", "/").split("/"))
    while True:
        try:
            dependency_manifest = resolve(root_file, output_root)
            break
        except MissingVariantMeshDefinitionError as error:
            extract(error.referenced_definition)

    acquisition = {
        "format": "rome2aoe2.vmd-acquisition", "version": 1,
        "root_definition": acquired[normalized_pack_path(root_path)]["path"],
        "pack_precedence": [Path(pack).name for pack in packs],
        "definitions": [acquired[key] for key in sorted(acquired)],
    }
    return acquisition, dependency_manifest


def main(arguments):
    packs = []
    helper = None
    root_path = None
    output_root = None
    index = 0
    while index < len(arguments):
        option = arguments[index]; index += 1
        if index == len(arguments):
            raise ValueError("Missing value for {}".format(option))
        value = arguments[index]; index += 1
        if option == "--pack": packs.append(Path(value))
        elif option == "--helper": helper = Path(value)
        elif option == "--root-path": root_path = value
        elif option == "--output-root": output_root = Path(value)
        else: raise ValueError("Unknown option {}".format(option))
    if not helper or not root_path or not output_root: raise ValueError("Usage: acquire_variant_mesh_definitions.py --helper <rome2aoe2-pack> --pack <pack> [--pack <pack> ...] --root-path <vmd> --output-root <directory>")
    acquisition, dependency = acquire(helper, packs, root_path, output_root)
    (output_root / "vmd-acquisition.json").write_text(manifest_json(acquisition), encoding="utf-8", newline="\n")
    (output_root / "dependencies.json").write_text(manifest_json(dependency), encoding="utf-8", newline="\n")
    print(manifest_json(acquisition), end="")
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main(sys.argv[1:]))
    except (OSError, ValueError, RuntimeError) as error:
        print(error, file=sys.stderr); raise SystemExit(1)
