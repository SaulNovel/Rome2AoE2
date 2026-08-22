from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from .animation import AnimationCandidate, preview_cache_identity
from .conversion import DEFAULT_BLENDER, DEFAULT_OUTPUT_ROOT, manifest_digest
from .errors import ConverterError, ErrorCode
from .native_assembly import ASSEMBLY_VERSION, assemble_native, static_visual_manifest


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "build/cache/rome2aoe2/animation-previews-v1"
RUNNER = ROOT / "build/community_tool_investigation/asset-editor-animation-runner/bin/Release/net10.0-windows/AssetEditorAnimationRunner.exe"
SKELETON = ROOT / "build/cache/rome2aoe2/assets-v1/animations/skeletons/rome_man_game.anim"
ASSET_CACHE = ROOT / "build/cache/rome2aoe2/assets-v1"


def _run(command: list[str], code: ErrorCode, message: str) -> str:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode or "Traceback (most recent call last)" in result.stdout:
        raise ConverterError(code, message, command=command, stderr=result.stderr[-2000:])
    return result.stdout


def _compose(samples: list[Path], output: Path) -> None:
    sys.path.insert(0, str(ROOT / "build/python-deps/pillow"))
    from PIL import Image, ImageDraw
    images = [Image.open(path).convert("RGBA") for path in samples]
    width, height = images[0].size
    sheet = Image.new("RGBA", (width * 3, height * 3), (24, 24, 24, 255))
    draw = ImageDraw.Draw(sheet)
    for index, item in enumerate(images):
        x, y = index % 3 * width, index // 3 * height
        sheet.alpha_composite(item, (x, y))
        draw.text((x + 8, y + 8), f"{index * 12.5:g}%", fill="white", stroke_width=2, stroke_fill="black")
    sheet.save(output)


def generate_preview(manifest: Mapping[str, Any], candidate: AnimationCandidate,
                     blender: Path = DEFAULT_BLENDER) -> tuple[AnimationCandidate, bool, dict[str, Any]]:
    identity = preview_cache_identity(manifest, candidate)
    directory = CACHE / identity
    contact = directory / "contact-sheet.png"
    report_path = directory / "preview-report.json"
    if contact.is_file() and report_path.is_file():
        report = json.loads(report_path.read_text())
        if report.get("provenance_version") != 4:
            _blend, native = assemble_native(manifest, candidate, blender)
            report["native_action"] = native
            report["provenance_version"] = 4
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return candidate.__class__(**{**candidate.__dict__, "preview_path": str(contact)}), True, report
    static = DEFAULT_OUTPUT_ROOT / manifest["source"]["main_unit"].casefold() / manifest_digest(static_visual_manifest(manifest)) / "static-unit.blend"
    if not static.is_file():
        raise ConverterError(ErrorCode.PREVIEW_GENERATION_FAILED, "Static configured unit must be converted before animation previews", path=str(static))
    directory.mkdir(parents=True, exist_ok=True)
    blend, native = assemble_native(manifest, candidate, blender)
    frames = directory / "frames"
    _run([str(blender), "--background", "--python", str(ROOT / "src/blender/render_animation_contact_sheet_frames.py"), "--",
          "--input-blend", str(blend), "--output", str(frames), "--exact-input", str(static.with_name("static-assembly-input.json"))],
         ErrorCode.PREVIEW_GENERATION_FAILED, "Preview sample rendering failed")
    samples = [frames / f"sample-{index}.png" for index in range(9)]
    _compose(samples, contact)
    report = {"format": "rome2aoe2.animation-preview", "version": 1, "cache_identity": identity,
              "cache_hit": False, "profile": "native-contact-sheet-v3-all-native-weighted-basis",
              "native_basis_assembly_version": ASSEMBLY_VERSION, "candidate": candidate.resolved_asset,
              "provenance_version": 4,
              "category": candidate.category, "contact_sheet": str(contact), "samples": [str(item) for item in samples],
              "native_action": native}
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return candidate.__class__(**{**candidate.__dict__, "preview_path": str(contact)}), False, report
