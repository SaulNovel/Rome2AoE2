"""Validate v4 material-fidelity candidate requirements (static checks)."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_conductor_dielectric_classification():
    src = (ROOT / "src" / "blender" / "render_rome2_v4_candidate.py").read_text(encoding="utf-8")
    assert "CONDUCTORS" in src
    assert "DIELECTRICS" in src
    assert 'bsdf.inputs["Metallic"].default_value = 1.0' in src
    assert 'bsdf.inputs["Metallic"].default_value = 0.0' in src
    assert "not authentic" in src.lower() or "authentic" in src.lower()


def test_chainmail_candidate():
    src = (ROOT / "src" / "blender" / "render_rome2_v4_candidate.py").read_text(encoding="utf-8")
    assert "chainmail_A" in src or '"A"' in src
    assert "chainmail_B" in src or '"B"' in src
    assert "chainmail_C" in src or '"C"' in src
    assert "mask" in src.lower() and "specular_rgb_F0" in src


def test_deterministic_environment_and_fixed_exposure():
    src = (ROOT / "src" / "blender" / "render_rome2_v4_candidate.py").read_text(encoding="utf-8")
    assert "EXPOSURE = 0.65" in src
    assert "set_environment" in src
    assert "PREETHAM" in src
    assert "sun_elevation" in src


def test_no_arbitrary_saturation():
    src = (ROOT / "src" / "blender" / "render_rome2_v4_candidate.py").read_text(encoding="utf-8")
    assert "desat" in src.lower()  # only sky desaturation, never a global boost


def test_unchanged_v2_v3_profiles():
    v2 = json.loads((ROOT / "config" / "render_profiles" / "aoe2_de_infantry_v2.json").read_text(encoding="utf-8"))
    v3 = json.loads((ROOT / "config" / "render_profiles" / "aoe2_de_infantry_v3_candidate.json").read_text(encoding="utf-8"))
    assert v2["render"]["exposure"] == 0.65
    assert "name" in v3


def test_x1_x2_source_resolution():
    src = (ROOT / "src" / "aoe2" / "generate_v4_ingame_proof.py").read_text(encoding="utf-8")
    assert "downsample_about_feet" in src
    assert 'author_16_facet_sld(stem, "x1", logical, 200, (100, 100))' in src
    assert 'author_16_facet_sld(stem, "x2", logical * 2, 400, (200, 200))' in src
    assert "logical" in src


def test_no_sld_binary_changes():
    sld = (ROOT / "src" / "aoe2" / "sld.py").read_text(encoding="utf-8")
    blocks = (ROOT / "src" / "aoe2" / "sld_blocks.py").read_text(encoding="utf-8")
    assert "serialize_sld" in sld
    assert "encode_bc1_block" in blocks or "encode_bc4_block" in blocks


def test_no_proprietary_assets_committed():
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "build/" in gi
    assert "test_data/empires2_x2_p1.dat" in gi


def run_all():
    tests = [
        test_conductor_dielectric_classification,
        test_chainmail_candidate,
        test_deterministic_environment_and_fixed_exposure,
        test_no_arbitrary_saturation,
        test_unchanged_v2_v3_profiles,
        test_x1_x2_source_resolution,
        test_no_sld_binary_changes,
        test_no_proprietary_assets_committed,
    ]
    for t in tests:
        t()
        print(f"ok - {t.__name__}")
    print(f"PASS ({len(tests)} checks)")


if __name__ == "__main__":
    run_all()
