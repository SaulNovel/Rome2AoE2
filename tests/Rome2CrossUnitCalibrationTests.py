"""Structural checks for the cross-unit discovery/extraction calibration gate."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "local-integration" / "rome2" / "cross-unit-calibration"


def main():
    discovery = json.loads((OUT / "unit-discovery.json").read_text(encoding="utf-8"))
    expected = {"Hastati", "Principes", "Triarii", "Velites", "Hoplites",
                "Celtic Warriors", "Eastern Spearmen", "Praetorian"}
    units = discovery["units"]
    assert {row["name"] for row in units} == expected
    assert len({row["selected_vmd"].lower() for row in units}) == 8
    for row in units:
        assert row["selected_vmd"] in {c["path"] for c in discovery["all_candidates"][row["name"]]}
        assert row["selection_strategy"] == "first-variant-per-slot"
        assert row["selected_dependencies"]
    assert discovery["all_candidates"]["Celtic Warriors"]
    assert any(c["path"].endswith("/eas_spear.variantmeshdefinition")
               for c in discovery["all_candidates"]["Eastern Spearmen"])

    assets = json.loads((OUT / "asset-summary.json").read_text(encoding="utf-8"))
    assert {row["unit"] for row in assets} == expected
    failures = {row["unit"]: row["failed"] for row in assets}
    assert all(failures[unit] == 0 for unit in expected)
    validation = json.loads((OUT / "material-type-70-validation.json").read_text(encoding="utf-8"))
    assert {row["unit"] for row in validation["assets"]} == {"Hoplite", "Eastern Spearman"}
    for row in validation["assets"]:
        assert row["skinned"] and row["all_primitives_have_uv0"]
        assert row["all_primitives_have_joints_weights"]
        assert any(m["type"] == "WeightedSkin" for m in row["material_types"])
    print("CROSS-UNIT CALIBRATION GATE PASS (WeightedSkin real assets supported)")


if __name__ == "__main__":
    main()
