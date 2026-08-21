import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "build/validation/rome2aoe2/principes-weighted-dirtmap-parity/report.json"


class WeightedDirtmapRecoveryTests(unittest.TestCase):
    def test_selected_principes_materials_pass_capture_equivalence(self):
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertTrue(report["capture_validated_for_selected_assets"])
        self.assertTrue(report["passed"])
        self.assertEqual(
            {"lorica_hamata_A", "roman_belt_01", "hellenic_konos"},
            {name for row in report["records"] for name in row["materials"]},
        )
        for row in report["records"]:
            self.assertEqual(0.0, row["exact_mean_difference"])
            self.assertEqual(0.0, row["exact_max_difference"])

    def test_source_material_records_preserve_optional_input_differences(self):
        materials = json.loads(REPORT.read_text(encoding="utf-8"))["source_materials"]
        lorica = {row["semantic"]: row for row in materials["lorica_hamata_A"]["textures"]}
        belt = {row["semantic"]: row for row in materials["roman_belt_01"]["textures"]}
        helmet = {row["semantic"]: row for row in materials["hellenic_konos"]["textures"]}
        self.assertEqual("shader_default", lorica["DecalDirtmask"]["status"])
        self.assertEqual("shader_default", belt["DecalDirtmask"]["status"])
        self.assertTrue(lorica["DecalDirtmask"]["source_path"].endswith("test_black.dds"))
        self.assertEqual("resolved", helmet["DecalDirtmask"]["status"])
        self.assertTrue(helmet["Mask"]["source_path"].endswith("test_mask.dds"))

    def test_stage_proof_contains_every_recovered_stage(self):
        root = REPORT.parent
        for group in ("lorica", "belt", "helmet"):
            for stage in ("A-diffuse", "B-faction", "C-dirt", "D-spec-gloss", "E-normal", "F-final"):
                output = root / f"{group}-{stage}.png"
                self.assertTrue(output.is_file(), output)
                self.assertGreater(output.stat().st_size, 0, output)

    def test_exact_static_report_declares_no_approximation(self):
        report_path = ROOT / (
            "build/conversions/rom_principes/"
            "bc5d577aadbce8e452d4419c6282e1e0d916900a9038516b321684ead85135c6/"
            "static-assembly-report.json"
        )
        material = json.loads(report_path.read_text(encoding="utf-8"))["materials"]
        self.assertEqual("rome2_exact_material_backend", material["backend"])
        self.assertEqual([], material["approximations"])


if __name__ == "__main__":
    unittest.main()
