"""Encode paired x1/x2 final Hastati idle SMPX files with DESpriteTool."""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "build/python-deps/pillow"))
from PIL import Image
from smx_staging import make_pillow_palette, read_jasc_palette, write_slp


def header(path):
    raw = path.read_bytes()
    signature, version, frames, size, original = struct.unpack_from("<4sHHII", raw)
    if signature != b"SMPX" or frames != 1072:
        raise RuntimeError(f"invalid SMPX header: {signature!r}, {frames}")
    return {"signature": signature.decode(), "version": version, "frames": frames,
            "compressed_size": size, "original_size": original, "file_size": len(raw)}


def encode(zoom, report, output_dir, tool, palette_path, palette):
    work = output_dir / f"encoder-{zoom}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    records = {(r["direction"], r["output_frame"]): r for r in report["records"]}
    frames = [Image.open(records[(direction, frame)][zoom]).convert("RGBA")
              for direction in range(16) for frame in range(67)]
    hotspot = tuple(report["hotspots"]["0"][zoom])
    slp = work / f"rome2aoe2_hastati_idle_{zoom}.slp"
    write_slp(slp, frames, palette, hotspot)
    settings = {"DiffusePalette": str(palette_path.resolve()), "IgnoreSLP": False,
                "GenerateX1Assets": False, "FacetCount": 16, "Compress": True,
                "Interleave": True, "DeleteSMP": False, "DisablePlayerColor": True,
                "IgnoreSubDirectories": False}
    (work / "settings.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    first = subprocess.run([str(tool), str(work.resolve())], cwd=work, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    smp = next(work.glob("*.smp"), None)
    if smp is None:
        raise RuntimeError(first.stdout)
    second = subprocess.run([str(tool), "-compress", str(smp.resolve())], cwd=work, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    generated = next(work.glob("*.smx"), None)
    if generated is None:
        raise RuntimeError(second.stdout)
    destination = output_dir / f"rome2aoe2_hastati_idle_{zoom}.smx"
    shutil.copy2(generated, destination)
    return {"zoom": zoom, "canvas": report[f"{zoom}_canvas"], "hotspot": list(hotspot),
            "source_frames": len(frames), "slp": str(slp), "smx": str(destination),
            "header": header(destination), "layers": ["main"],
            "unsupported_layers": ["player_color", "shadow", "outline"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sprite-tool", type=Path, required=True)
    parser.add_argument("--palette", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.render_report.read_text(encoding="utf-8"))
    if report["directions"] != list(range(16)) or report["frames_per_direction"] != 67:
        raise RuntimeError("final idle requires 16 directions and 67 frames")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    palette = make_pillow_palette(read_jasc_palette(args.palette))
    outputs = [encode(zoom, report, args.output_dir, args.sprite_tool, args.palette, palette)
               for zoom in ("x1", "x2")]
    result = {"format": "rome2aoe2.final-idle-smx-pair", "version": 1,
              "frame_order": "facet-major", "frames_per_facet": 67, "facet_count": 16,
              "frame_duration_seconds": 1 / 24, "outputs": outputs,
              "layer_limitation": "Current validated SLP-to-SMPX staging carries main colour only; repository player-colour/shadow support is SLD-only."}
    (args.output_dir / "smx-pair-report.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
