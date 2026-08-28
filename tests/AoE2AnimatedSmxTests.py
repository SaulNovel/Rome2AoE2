import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "third_party" / "python-deps"))
from aoe2_genie_tooling import GenieWorkspace

BASE = ROOT / "build" / "local-integration" / "first-animated-smx"


def test_render_layout():
    report = json.loads((BASE / "all-directions-report.json").read_text(encoding="utf-8"))
    assert report["output_frames_per_direction"] == 67
    assert report["directions"] == list(range(16))
    assert report["direction_angles"] == [45.0, 22.5, 0.0, 337.5, 315.0, 292.5, 270.0, 247.5,
                                            225.0, 202.5, 180.0, 157.5, 135.0, 112.5, 90.0, 67.5]
    assert report["canvas"] == [200, 200]
    assert report["hotspot"] == [100, 100]
    assert [(item["direction"], item["output_frame"]) for item in report["records"]] == [
        (direction, frame) for direction in range(16) for frame in range(67)]


def test_smx_and_dat_metadata_agree():
    package = json.loads((BASE / "package" / "package-report.json").read_text(encoding="utf-8"))
    smx = Path(package["smx"])
    signature, version, total_frames = struct.unpack_from("<4sHH", smx.read_bytes(), 0)
    assert (signature, version, total_frames) == (b"SMPX", 1, 16 * 67)
    workspace = GenieWorkspace.load(Path(package["dat"]))
    unit = workspace.unit_manager.get(2081)
    graphic = workspace.graphic_manager.get(unit.standing_sprite_id1)
    assert unit.standing_sprite_id1 == unit.standing_sprite_id2 == package["graphic_id"]
    assert (graphic.frame_count, graphic.angle_count) == (67, 16)
    assert abs(graphic.frame_duration - 1 / 24) < 1e-7


if __name__ == "__main__":
    test_render_layout()
    test_smx_and_dat_metadata_agree()
    print("AoE2 animated SMX regressions: 2 passed")
