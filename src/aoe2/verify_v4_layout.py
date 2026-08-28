"""Verify the v4 layout proof: SLD frame count, facet-major order, feet/hotspot invariant, overlays."""
from __future__ import annotations
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
_VENDORED = PROJECT_ROOT / "build" / "python-deps" / "sld-authoring"
if _VENDORED.is_dir() and str(_VENDORED) not in sys.path:
    sys.path.insert(0, str(_VENDORED))
from PIL import Image, ImageDraw  # noqa: E402
from aoe2.sld import parse_sld  # noqa: E402
from aoe2.analyze_sld import decode_frame  # noqa: E402

ROOT = PROJECT_ROOT / "build" / "local-integration" / "v4-layout-proof"
GRAPHICS = ROOT / "mod" / "resources" / "_common" / "drs" / "graphics"
OVERLAYS = ROOT / "overlays"


def verify():
    stems = ["rome2_v4_corrected50", "rome2_v4_corrected54"]
    report = {}
    for stem in stems:
        entry = {}
        for zoom, canvas, hotspot in (("x1", 200, (100, 100)), ("x2", 400, (200, 200))):
            path = GRAPHICS / f"{stem}_{zoom}.sld"
            sld = parse_sld(path.read_bytes())
            frame_count = len(sld.frames)
            facets = sld.facet_count
            # Facet-major: linear_frame = facet_index, so sld frames == 16 and frame indices 0..15.
            indices = [f.frame_index for f in sld.frames]
            entry[zoom] = {
                "frame_count": frame_count,
                "facet_count": facets,
                "frame_indices": indices,
                "all_facets_present": sorted(indices) == list(range(16)),
            }
            # Feet/hotspot invariant from decoded frame 0.
            main, _shadow = decode_frame(sld, 0)
            hx, hy = sld.frames[0].center_x, sld.frames[0].center_y
            entry[zoom]["hotspot"] = [hx, hy]
            # Detect lowest opaque pixel column band near hotspot x as feet.
            data = list(main.convert("RGBA").getdata())
            w, h = main.size
            feet_y = max((i // w) for i, p in enumerate(data) if p[3] > 8 and (i % w) >= hx - 6 and (i % w) <= hx + 6)
            entry[zoom]["decoded_feet"] = [hx, feet_y]
            entry[zoom]["source_feet_minus_hotspot"] = [0, feet_y - hy]
        report[stem] = entry
    overlay_files = sorted(p.name for p in OVERLAYS.glob("*.png"))
    report["overlays"] = overlay_files
    out = ROOT / "v4-layout-verify.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    # Hard checks.
    for stem in stems:
        for zoom in ("x1", "x2"):
            e = report[stem][zoom]
            assert e["frame_count"] == 16, f"{stem} {zoom}: expected 16 frames"
            assert e["all_facets_present"], f"{stem} {zoom}: missing facings"
            assert e["source_feet_minus_hotspot"][1] <= 4, f"{stem} {zoom}: feet not at hotspot"
    print("LAYOUT VERIFY PASS")


if __name__ == "__main__":
    verify()