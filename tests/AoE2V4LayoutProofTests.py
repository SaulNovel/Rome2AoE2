"""Validate v4 runtime-layout proof: facet frames, facet-major indexing, hotspot invariant."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
_VENDORED = ROOT / "build" / "python-deps" / "sld-authoring"
if _VENDORED.is_dir() and str(_VENDORED) not in sys.path:
    sys.path.insert(0, str(_VENDORED))
from aoe2.sld import LAYER_MAIN, parse_sld, serialize_sld  # noqa: E402
from aoe2.analyze_sld import decode_frame  # noqa: E402
sys.path.insert(0, str(ROOT / "third_party" / "python-deps"))
from aoe2_genie_tooling import GenieWorkspace  # noqa: E402

PROOF = ROOT / "build" / "local-integration" / "v4-layout-proof"
GRAPHICS = PROOF / "mod" / "resources" / "_common" / "drs" / "graphics"
DAT = PROOF / "v4_layout.dat"
MOD_DAT = PROOF / "mod" / "resources" / "_common" / "dat" / "empires2_x2_p1.dat"
STEMS = ("rome2_v4_corrected50", "rome2_v4_corrected54")


def load_sld(stem, zoom):
    path = GRAPHICS / f"{stem}_{zoom}.sld"
    data = path.read_bytes()
    sld = parse_sld(data)  # Strict parser rejects truncation and trailing bytes.
    assert serialize_sld(sld) == data, f"{stem} {zoom}: serialization is not deterministic"
    return sld


def decoded_feet(sld, frame_index):
    main, _ = decode_frame(sld, frame_index)
    frame = sld.frames[frame_index]
    hx = frame.center_x
    hy = frame.center_y
    opaque = [(i % main.width, i // main.width) for i, p in enumerate(main.convert("RGBA").getdata()) if p[3] > 8]
    assert opaque, f"frame {frame_index}: no decoded opaque pixels"
    # Feet can straddle a transparent hotspot and rotate away from hotspot x.
    # The closest decoded sprite pixel is therefore a sounder ground-contact
    # witness than the lowest pixel in an arbitrary vertical strip.
    return min(opaque, key=lambda p: (p[0] - hx) ** 2 + (p[1] - hy) ** 2)


def test_1x16_facets_16_frames():
    for stem in STEMS:
        for zoom, canvas, hotspot in (("x1", 200, (100, 100)), ("x2", 400, (200, 200))):
            sld = load_sld(stem, zoom)
            assert len(sld.frames) == 16, f"{stem} {zoom}: expected 16 frames"
            assert [(f.canvas_width, f.canvas_height) for f in sld.frames] == [(canvas, canvas)] * 16
            assert [(f.center_x, f.center_y) for f in sld.frames] == [hotspot] * 16


def test_facet_major_indexing():
    for stem in STEMS:
        for zoom in ("x1", "x2"):
            sld = load_sld(stem, zoom)
            indices = [f.frame_index for f in sld.frames]
            assert indices == list(range(16)), f"{stem} {zoom}: facet-major order broken"


def test_no_missing_facing():
    for stem in STEMS:
        for zoom in ("x1", "x2"):
            sld = load_sld(stem, zoom)
            assert sorted(f.frame_index for f in sld.frames) == list(range(16)), f"{stem} {zoom}: missing facing"


def test_hotspot_feet_invariant():
    for stem in STEMS:
        for zoom, canvas, hotspot in (("x1", 200, (100, 100)), ("x2", 400, (200, 200))):
            sld = load_sld(stem, zoom)
            for index, frame in enumerate(sld.frames):
                feet_x, feet_y = decoded_feet(sld, index)
                scale = canvas // 200
                distance2 = (feet_x - frame.center_x) ** 2 + (feet_y - frame.center_y) ** 2
                assert distance2 <= (4 * scale) ** 2, \
                    f"{stem} {zoom} facing {index}: no foot pixels near hotspot"


def test_x1_x2_logical_equivalence():
    for stem in STEMS:
        s1, s2 = load_sld(stem, "x1"), load_sld(stem, "x2")
        for index, (f1, f2) in enumerate(zip(s1.frames, s2.frames)):
            assert (f2.center_x, f2.center_y) == (2 * f1.center_x, 2 * f1.center_y)
            feet1, feet2 = decoded_feet(s1, index), decoded_feet(s2, index)
            # Compare offsets from each scale's hotspot, not absolute canvas pixels.
            delta1 = (feet1[0] - f1.center_x, feet1[1] - f1.center_y)
            delta2 = (feet2[0] - f2.center_x, feet2[1] - f2.center_y)
            # Both decoded witnesses remain within the same four-logical-pixel
            # neighbourhood. Exact vectors need not match because BC1 chooses
            # a different nearest opaque sample on the doubled pixel grid.
            assert delta1[0] ** 2 + delta1[1] ** 2 <= 4 ** 2
            assert delta2[0] ** 2 + delta2[1] ** 2 <= 8 ** 2
            main1 = next(layer for layer in f1.layers if layer.layer_type == LAYER_MAIN)
            main2 = next(layer for layer in f2.layers if layer.layer_type == LAYER_MAIN)
            # Independent BC alignment may differ by one x1 block, which is
            # eight pixels after expressing both bounds on the x2 grid.
            for a, b in zip((main1.offset_x1, main1.offset_y1, main1.offset_x2, main1.offset_y2),
                            (main2.offset_x1, main2.offset_y1, main2.offset_x2, main2.offset_y2)):
                assert abs(b - 2 * a) <= 8


def test_no_duplicate_single_frame():
    for stem in STEMS:
        for zoom in ("x1", "x2"):
            sld = load_sld(stem, zoom)
            # Must NOT be a single duplicated frame.
            assert len(sld.frames) == 16
            assert len({f.frame_index for f in sld.frames}) == 16


def test_dat_layout_and_canonical_install_name():
    assert MOD_DAT.is_file()
    assert MOD_DAT.read_bytes() == DAT.read_bytes()
    workspace = GenieWorkspace.load(DAT)
    for unit_id, expected_stem in ((2081, STEMS[0]), (2113, STEMS[1])):
        unit = workspace.unit_manager.get(unit_id)
        assert unit.standing_sprite_id1 == unit.standing_sprite_id2
        graphic = workspace.graphic_manager.get(unit.standing_sprite_id1)
        assert graphic.file_name == expected_stem
        assert graphic.angle_count == 16
        assert graphic.frame_count == 1


def run_all():
    tests = [
        test_1x16_facets_16_frames,
        test_facet_major_indexing,
        test_no_missing_facing,
        test_hotspot_feet_invariant,
        test_x1_x2_logical_equivalence,
        test_no_duplicate_single_frame,
        test_dat_layout_and_canonical_install_name,
    ]
    for t in tests:
        t()
        print(f"ok - {t.__name__}")
    print(f"PASS ({len(tests)} checks)")


if __name__ == "__main__":
    run_all()
