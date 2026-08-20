"""Author one complete 16-facet Hastati animation with separated shadows."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for dependency in (ROOT / "build/python-deps/sld-authoring", ROOT / "build/python-deps/pillow"):
    if dependency.is_dir():
        sys.path.insert(0, str(dependency))

from PIL import Image

sys.path.insert(0, str(ROOT / "src"))
from aoe2.sld import LAYER_MAIN, LAYER_SHADOW, SLDFile, parse_sld, serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder, author_one_frame


def frame_path(root, animation, direction, frame):
    return root / f"{animation}-direction-{direction:02d}-frame-{frame:03d}.png"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--animation", required=True)
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--main-root", type=Path, required=True)
    parser.add_argument("--shadow-root", type=Path, required=True)
    parser.add_argument("--texconv", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--frame-duration", type=float, required=True)
    parser.add_argument("--hotspot-x1", nargs=2, type=int, default=(100, 122))
    parser.add_argument("--hotspot-x2", nargs=2, type=int, default=(200, 244))
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    encoded = {}
    for zoom, canvas, hotspot in (("x1", 200, tuple(args.hotspot_x1)),
                                   ("x2", 400, tuple(args.hotspot_x2))):
        frames = []
        bounds = []
        for direction in range(16):
            for ordinal in range(args.frames):
                main_path = frame_path(args.main_root / zoom, args.animation, direction, ordinal)
                shadow_path = frame_path(args.shadow_root / zoom, args.animation, direction, ordinal)
                if not main_path.is_file() or not shadow_path.is_file():
                    raise FileNotFoundError(f"missing main/shadow pair: {main_path}, {shadow_path}")
                main = Image.open(main_path).convert("RGBA")
                shadow = Image.open(shadow_path).convert("RGBA")
                box = main.getchannel("A").getbbox()
                shadow_box = shadow.getchannel("A").getbbox()
                if box is None or shadow_box is None:
                    raise RuntimeError(f"empty main/shadow: {direction}/{ordinal}")
                if box[0] == 0 or box[1] == 0 or box[2] == canvas or box[3] == canvas:
                    raise RuntimeError(f"clipped main frame: {direction}/{ordinal}: {box}")
                frame = author_one_frame(
                    main, shadow, hotspot=hotspot,
                    encoder=DirectXTexBC1Encoder(args.texconv),
                ).frames[0]
                frame.frame_index = len(frames)
                frames.append(frame)
                bounds.append({"direction": direction, "frame": ordinal,
                               "main": list(box), "shadow": list(shadow_box)})
        document = SLDFile(frames=frames, facet_count=16)
        output = args.output_root / f"hastati-{args.animation}_{zoom}.sld"
        output.write_bytes(serialize_sld(document))
        parsed = parse_sld(output.read_bytes())
        if len(parsed.frames) != 16 * args.frames:
            raise RuntimeError("strict SLD frame-count round trip failed")
        if any(frame.frame_type != (LAYER_MAIN | LAYER_SHADOW) for frame in parsed.frames):
            raise RuntimeError("SLD does not contain exactly main + shadow semantics")
        encoded[zoom] = {
            "path": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "canvas": [canvas, canvas], "hotspot": list(hotspot),
            "frames": len(parsed.frames), "facets": parsed.facet_count,
            "layer_types": [LAYER_MAIN, LAYER_SHADOW], "bounds": bounds,
        }
    report = {
        "format": "rome2aoe2.hastati-gameplay-animation-sld", "version": 1,
        "animation": args.animation, "frames_per_facet": args.frames,
        "facet_count": 16, "frame_order": "facet-major",
        "frame_duration_seconds": args.frame_duration,
        "player_colour": False, "layers": ["main", "shadow"], "encoded": encoded,
    }
    (args.output_root / f"{args.animation}-sld-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"animation": args.animation, "encoded": encoded}, sort_keys=True))


if __name__ == "__main__":
    main()
