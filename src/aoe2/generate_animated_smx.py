"""Stage the full Hastati idle action and invoke the official DE SMX encoder."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "build" / "python-deps" / "pillow"))
from PIL import Image

from smx_staging import make_pillow_palette, read_jasc_palette, write_slp


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-report", type=Path, required=True)
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sprite-tool", type=Path, required=True)
    parser.add_argument("--palette", type=Path, required=True)
    return parser.parse_args()


def parse_smx_header(path):
    data = path.read_bytes()
    if len(data) < 32:
        raise ValueError("SMX is shorter than its header")
    import struct
    signature, version, frames, size, original, checksum, odd_size, odd_original, odd_checksum = struct.unpack_from(
        "<4sHHIIIIII", data, 0)
    if signature != b"SMPX":
        raise ValueError(f"unexpected SMX signature {signature!r}")
    if frames <= 0 or size <= 0 or original <= 0:
        raise ValueError("invalid SMX header counts")
    return {"signature": signature.decode("ascii"), "version": version, "frame_count": frames,
            "compressed_size": size, "original_size": original, "checksum": checksum,
            "odd_compressed_size": odd_size, "odd_original_size": odd_original,
            "odd_checksum": odd_checksum, "file_size": len(data)}


def main():
    args = arguments()
    report = json.loads(args.render_report.read_text(encoding="utf-8"))
    frame_count = report["output_frames_per_direction"]
    directions = report["directions"]
    if directions != list(range(16)):
        raise RuntimeError("first animated SMX requires all 16 ordered directions")
    records = {(item["direction"], item["output_frame"]): item for item in report["records"]}
    ordered = []
    for direction in directions:
        for frame in range(frame_count):
            item = records[(direction, frame)]
            ordered.append(Image.open(args.frames_dir / item["path"]).convert("RGBA"))
    colours = read_jasc_palette(args.palette)
    palette = make_pillow_palette(colours)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    work = args.output_dir / "encoder-work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    slp = work / "rome2aoe2_hastati_idle.slp"
    write_slp(slp, ordered, palette, tuple(report["hotspot"]))
    settings = {
        "DiffusePalette": str(args.palette.resolve()), "IgnoreSLP": False,
        "GenerateX1Assets": False, "FacetCount": 16, "Compress": True,
        "Interleave": True, "DeleteSMP": False, "DisablePlayerColor": True,
        "IgnoreSubDirectories": False,
    }
    (work / "settings.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    first = subprocess.run([str(args.sprite_tool), str(work.resolve())], cwd=work, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    smps = list(work.glob("*.smp"))
    if not smps:
        raise RuntimeError("DESpriteTool produced no SMP staging file\n" + first.stdout)
    second = subprocess.run([str(args.sprite_tool), "-compress", str(smps[0].resolve())], cwd=work, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    smxs = list(work.glob("*.smx"))
    if not smxs:
        raise RuntimeError("DESpriteTool produced no SMX\n" + second.stdout)
    output = args.output_dir / "rome2aoe2_hastati_idle_x1.smx"
    shutil.copy2(smxs[0], output)
    header = parse_smx_header(output)
    if header["frame_count"] != frame_count * len(directions):
        raise RuntimeError(f"SMX frame count mismatch: {header['frame_count']}")
    document = {
        "format": "rome2aoe2.animated-smx", "version": 1,
        "source_frames": len(ordered), "frames_per_facet": frame_count,
        "facet_count": len(directions), "frame_order": "facet-major",
        "hotspot": report["hotspot"], "palette": str(args.palette),
        "layers": ["main"], "deferred_layers": ["player_color", "shadow", "outline"],
        "staging_slp": str(slp), "output_smx": str(output), "header": header,
        "encoder_first_pass": first.stdout, "encoder_compression_pass": second.stdout,
    }
    (args.output_dir / "smx-report.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                                                     encoding="utf-8")
    print(json.dumps(document, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
