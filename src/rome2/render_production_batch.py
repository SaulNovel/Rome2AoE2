"""Run a resumable direction batch for one frozen production category."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from rome2aoe2.conversion import DEFAULT_BLENDER, load_and_validate_manifest
from rome2aoe2.native_assembly import assemble_native, static_assembly_identity
from rome2aoe2.production import (PROFILE, category_output, frozen_candidate,
                                  resolve_production_profile)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("category")
    parser.add_argument("directions")
    parser.add_argument("--production-profile", default=PROFILE)
    args = parser.parse_args()
    profile = resolve_production_profile(args.production_profile)
    blade_capability = profile["attachment_capabilities"]["one_handed_blade/weapon_02"]
    request = load_and_validate_manifest(args.manifest)
    record = request.manifest["animations"][args.category]
    candidate = frozen_candidate(args.category, record)
    blend, assembly = assemble_native(request.manifest, candidate, DEFAULT_BLENDER,
                                      blade_capability)
    output = category_output(request.unit.definition.main_unit, request.manifest_hash,
                             args.category, record, profile["name"])
    static = (ROOT / "build/conversions" / request.unit.definition.main_unit.casefold() /
              static_assembly_identity(request.manifest, blade_capability) /
              "static-assembly-input.json")
    if not static.is_file():
        raise RuntimeError(f"profile-specific static assembly is unavailable: {static}")
    report = output / f"render-report-directions-{args.directions.replace(',', '-')}.json"
    command = [
        str(DEFAULT_BLENDER), "--background", "--python",
        str(ROOT / "src/blender/render_manifest_native_production.py"), "--",
        "--input-blend", str(blend), "--static-input", str(static),
        "--output-root", str(output), "--report", str(report),
        "--category", args.category, "--manifest-hash", request.manifest_hash,
        "--profile-name", profile["name"],
        "--animation-asset", record["resolved_asset"],
        "--source-samples", str(record["frame_count"]), "--source-fps", str(record["fps"]),
        "--action-fingerprint", assembly["action_fingerprint_before"],
        "--directions", args.directions,
    ]
    raise SystemExit(subprocess.run(command).returncode)


if __name__ == "__main__":
    main()
