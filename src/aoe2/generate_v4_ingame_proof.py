"""Generate v4 runtime-layout proof: 16-facet SLDs + compact DAT + scenario.

Structural fixes vs prior proof:
- 16 direction renders, one SLD frame per facet (facet-major: linear_frame = facet_index)
- feet point anchored at the SLD hotspot (feet invariant through downsample)
- only stock + 2 clones (50px, 54px), placed far apart
- decoded overlays showing canvas center / hotspot / feet / trimmed bounds / layer origin
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "third_party" / "python-deps"))
sys.path.insert(0, str(PROJECT_ROOT / "third_party" / "AoE2ScenarioParser"))

_VENDORED = PROJECT_ROOT / "build" / "python-deps" / "sld-authoring"
if _VENDORED.is_dir() and str(_VENDORED) not in sys.path:
    sys.path.insert(0, str(_VENDORED))

from PIL import Image, ImageDraw  # noqa: E402
from aoe2_genie_tooling import GenieWorkspace  # noqa: E402

sys.path.insert(0, str(PROJECT_ROOT / "src"))
from aoe2.sld_authoring import DirectXTexBC1Encoder, author_one_frame  # noqa: E402
from aoe2.sld import SLDFile, serialize_sld  # noqa: E402
from aoe2.analyze_sld import decode_frame  # noqa: E402

DIRS = PROJECT_ROOT / "build" / "local-integration" / "rome2" / "visual-fidelity" / "v4" / "directions"
TEXCONV = PROJECT_ROOT / "build" / "tools" / "directxtex-may2026" / "texconv.exe"
SOURCE_DAT = PROJECT_ROOT / "test_data" / "empires2_x2_p1.dat"
OUT_ROOT = PROJECT_ROOT / "build" / "local-integration" / "v4-layout-proof"
OUT_DAT = OUT_ROOT / "v4_layout.dat"
OUT_SCENARIO = OUT_ROOT / "v4_layout.aoe2scenario"
TEMPLATE_SCENARIO = PROJECT_ROOT / "test_data" / "EmptyMap.aoe2scenario"
MOD_ROOT = OUT_ROOT / "mod"
GRAPHICS = MOD_ROOT / "resources" / "_common" / "drs" / "graphics"
MOD_DAT = MOD_ROOT / "resources" / "_common" / "dat" / "empires2_x2_p1.dat"
OVERLAYS = OUT_ROOT / "overlays"

STOCK_ID = 74
CLONE_IDS = [2081, 2113]  # 50px, 54px
STEMS = ["rome2_v4_corrected50", "rome2_v4_corrected54"]
LABELS = ["V4 Corrected 50px", "V4 Corrected 54px"]
LOGICAL = {"rome2_v4_corrected50": 50, "rome2_v4_corrected54": 54}
FACETS = 16
# Source render feet point (800x800 canvas center).
SRC_FEET = (400, 400)


def downsample_about_feet(img, canvas, logical, hotspot):
    """Scale sprite about the feet point so feet lands on the hotspot."""
    rgba = img.convert("RGBA")
    data = list(rgba.getdata())
    w, h = rgba.size
    pts = [(i % w, i // w) for i, p in enumerate(data) if p[3] > 8]
    if not pts:
        return Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    xs = [x for x, _ in pts]
    ys = [y for _, y in pts]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs) + 1, max(ys) + 1
    sprite = rgba.crop((x0, y0, x1, y1))
    # Feet position relative to sprite bbox.
    feet_rel = (SRC_FEET[0] - x0, SRC_FEET[1] - y0)
    scale = logical / sprite.height
    new_w = max(1, int(round(sprite.width * scale)))
    new_h = logical
    sprite = sprite.resize((new_w, new_h), Image.LANCZOS)
    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    # Place so scaled feet lands on hotspot.
    ox = hotspot[0] - int(round(feet_rel[0] * scale))
    oy = hotspot[1] - int(round(feet_rel[1] * scale))
    out.paste(sprite, (ox, oy), sprite)
    return out


def make_shadow(main_img):
    rgba = main_img.convert("RGBA")
    alpha = rgba.split()[3]
    shadow = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 255), (0, 2), alpha)
    shadow.putalpha(alpha.point(lambda a: int(a * 0.58)))
    return shadow


def author_16_facet_sld(stem, zoom, logical, canvas, hotspot):
    """Author a 16-frame facet-major SLD from the 16 direction renders.

    Builds each frame explicitly with author_one_frame so the hotspot is
    guaranteed to be honored (author_direction_frames did not apply it).
    """
    out_frames = []
    for i in range(FACETS):
        src = DIRS / f"direction-{i:02d}.png"
        main = downsample_about_feet(Image.open(src).convert("RGBA"), canvas, logical, hotspot)
        shadow = make_shadow(main)
        encoder = DirectXTexBC1Encoder(TEXCONV)
        frame = author_one_frame(main, shadow, hotspot, encoder=encoder).frames[0]
        frame.frame_index = i
        out_frames.append(frame)
    sld = SLDFile(frames=out_frames, facet_count=FACETS)
    path = OUT_ROOT / "sld-work" / f"{stem}_{zoom}.sld"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(serialize_sld(sld))
    return path, out_frames


def build_dat():
    workspace = GenieWorkspace.load(SOURCE_DAT)
    source = workspace.unit_manager.get(STOCK_ID)
    source_state = (source.name, source.standing_sprite_id1, source.standing_sprite_id2)
    results = []
    for unit_id, stem, label in zip(CLONE_IDS, STEMS, LABELS):
        if workspace.unit_manager.exists(unit_id):
            raise ValueError(f"unit {unit_id} already occupied")
        graphic = workspace.graphic_manager.add_graphic(
            stem, name=label, frame_count=1, angle_count=FACETS, frame_duration=1.0
        )
        clone = workspace.unit_manager.clone_into(unit_id, STOCK_ID, on_conflict="error", fill_gaps="placeholder")
        clone.name = label
        clone.standing_sprite_id1 = graphic.id
        clone.standing_sprite_id2 = graphic.id
        results.append({"unit_id": unit_id, "graphic_id": graphic.id, "stem": stem})
    OUT_DAT.parent.mkdir(parents=True, exist_ok=True)
    workspace.save(OUT_DAT)
    written = GenieWorkspace.load(OUT_DAT)
    militia = written.unit_manager.get(STOCK_ID)
    if (militia.name, militia.standing_sprite_id1, militia.standing_sprite_id2) != source_state:
        raise RuntimeError("written DAT changed original Legionary")
    return {"stock_unit_id": STOCK_ID, "clones": results}


def install_slds(sld_map):
    GRAPHICS.mkdir(parents=True, exist_ok=True)
    MOD_DAT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT_DAT, MOD_DAT)
    installed = []
    for stem, (sld_x1, sld_x2) in sld_map.items():
        dest_x1 = GRAPHICS / f"{stem}_x1.sld"
        dest_x2 = GRAPHICS / f"{stem}_x2.sld"
        shutil.copy2(sld_x1, dest_x1)
        shutil.copy2(sld_x2, dest_x2)
        installed.append(f"resources/_common/drs/graphics/{dest_x1.name}")
        installed.append(f"resources/_common/drs/graphics/{dest_x2.name}")
    (MOD_ROOT / "info.json").write_text(
        json.dumps({"Author": "Rome2AoE2", "CacheStatus": 0,
                    "Description": "V4 runtime-layout proof.",
                    "Title": "Rome2AoE2 V4 Layout Proof"}, indent=2) + "\n", encoding="utf-8"
    )
    return installed


def build_scenario():
    from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
    scenario = AoE2DEScenario.from_file(str(TEMPLATE_SCENARIO))
    placements = [
        (STOCK_ID, 1, 8.0, 10.0),
        (CLONE_IDS[0], 1, 20.0, 10.0),
        (CLONE_IDS[1], 1, 32.0, 10.0),
    ]
    for unit_id, player, x, y in placements:
        scenario.unit_manager.add_unit(player=player, unit_const=unit_id, x=x, y=y)
    OUT_SCENARIO.parent.mkdir(parents=True, exist_ok=True)
    scenario.write_to_file(str(OUT_SCENARIO))


def build_overlays(sld_map, frames_map):
    """Decoded overlays: canvas center, hotspot, detected feet, trimmed bounds, layer origin."""
    OVERLAYS.mkdir(parents=True, exist_ok=True)
    from aoe2.sld import parse_sld
    for stem, (sld_x1, _sld_x2) in sld_map.items():
        sld = parse_sld(sld_x1.read_bytes())
        frame = sld.frames[0]
        main, _shadow = decode_frame(sld, 0)
        overlay = main.convert("RGBA")
        draw = ImageDraw.Draw(overlay)
        w, h = overlay.size
        cx, cy = w // 2, h // 2
        hx, hy = frame.center_x, frame.center_y
        # Canvas center (blue), hotspot (red), feet = hotspot (green).
        draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=(0, 0, 255, 255))
        draw.ellipse((hx - 3, hy - 3, hx + 3, hy + 3), fill=(255, 0, 0, 255))
        draw.ellipse((hx - 1, hy - 1, hx + 1, hy + 1), fill=(0, 255, 0, 255))
        # Trimmed bounds from first main layer.
        for layer in frame.layers:
            if layer.layer_type == 1:
                draw.rectangle((layer.offset_x1, layer.offset_y1, layer.offset_x2, layer.offset_y2),
                               outline=(255, 255, 0, 255))
                draw.text((layer.offset_x1 + 2, layer.offset_y1 + 2), "origin", fill=(255, 255, 0, 255))
                break
        overlay.save(OVERLAYS / f"{stem}_x1_overlay.png")
        # x2 overlay.
        sld2 = parse_sld(sld_map[stem][1].read_bytes())
        frame2 = sld2.frames[0]
        main2, _s2 = decode_frame(sld2, 0)
        ov2 = main2.convert("RGBA")
        d2 = ImageDraw.Draw(ov2)
        w2, h2 = ov2.size
        d2.ellipse((w2 // 2 - 3, h2 // 2 - 3, w2 // 2 + 3, h2 // 2 + 3), fill=(0, 0, 255, 255))
        d2.ellipse((frame2.center_x - 3, frame2.center_y - 3, frame2.center_x + 3, frame2.center_y + 3), fill=(255, 0, 0, 255))
        for layer in frame2.layers:
            if layer.layer_type == 1:
                d2.rectangle((layer.offset_x1, layer.offset_y1, layer.offset_x2, layer.offset_y2),
                             outline=(255, 255, 0, 255))
                break
        ov2.save(OVERLAYS / f"{stem}_x2_overlay.png")


def main():
    for label, p in (("directions", DIRS), ("texconv", TEXCONV), ("DAT", SOURCE_DAT)):
        if not p.is_dir() if p == DIRS else not p.is_file():
            print(f"missing {label}: {p}", file=sys.stderr)
            return 2
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    sld_map = {}
    frames_map = {}
    for stem in STEMS:
        logical = LOGICAL[stem]
        sld_x1, frames_x1 = author_16_facet_sld(stem, "x1", logical, 200, (100, 100))
        sld_x2, frames_x2 = author_16_facet_sld(stem, "x2", logical * 2, 400, (200, 200))
        sld_map[stem] = (sld_x1, sld_x2)
        frames_map[stem] = (frames_x1, frames_x2)

    dat_report = build_dat()
    installed = install_slds(sld_map)
    build_scenario()
    build_overlays(sld_map, frames_map)

    report = {
        "format": "rome2aoe2.visual-fidelity.v4-layout-proof",
        "version": 1,
        "dat": str(OUT_DAT),
        "scenario": str(OUT_SCENARIO),
        "mod_root": str(MOD_ROOT),
        "stock_unit_id": STOCK_ID,
        "units": dat_report,
        "installed_slds": installed,
        "installed_dat": str(MOD_DAT),
        "facets": FACETS,
        "frame_order": "facet-major: linear_frame = facet_index (1 frame per facet)",
        "x1_hotspot": [100, 100],
        "x2_hotspot": [200, 200],
        "feet_invariant": "source feet (400,400) -> hotspot after downsample",
        "overlays": str(OVERLAYS),
    }
    (OUT_ROOT / "v4-layout-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
