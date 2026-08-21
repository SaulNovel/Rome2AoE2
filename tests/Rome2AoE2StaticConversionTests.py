import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rome2aoe2.catalog import load_default_catalog
from rome2aoe2.conversion import load_and_validate_manifest, manifest_digest
from rome2aoe2.errors import ConverterError, ErrorCode
from rome2aoe2.manifest import AutoSelection, build_manifest


class _CatalogResult:
    def __init__(self, unit):
        self.unit = unit

    def resolve(self, *_args, **_kwargs):
        return self.unit


class StaticConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_default_catalog()
        cls.principes = cls.catalog.resolve("Rom_Principes", "rom_rome")
        cls.manifest = build_manifest(cls.principes)

    def validate(self, document, catalog=None):
        directory = ROOT / "build/cache/rome2aoe2/static-conversion-tests"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "manifest.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return load_and_validate_manifest(path, catalog or self.catalog, directory / "output")

    def test_default_resolution_is_concrete_and_deterministic(self):
        first = build_manifest(self.principes)
        second = build_manifest(self.principes)
        self.assertEqual(first, second)
        for component in first["components"].values():
            if component is not None:
                selection = component["selection"]
                self.assertEqual("deterministic_source_first", selection["mode"])
                self.assertEqual(component["key"], selection["resolved_asset"])
                self.assertEqual("first_distinct_source", selection["resolution_policy"])
                self.assertIn("no_authoritative_default_marker", selection["source_semantics"])

    def test_explicit_selection_and_optional_none_are_preserved(self):
        helmet = next(slot for slot in self.principes.component_slots if slot.key == "helmet")
        explicit = helmet.options[-1].key
        crest = next(slot for slot in self.principes.component_slots if slot.key == "crest")
        self.assertFalse(crest.required)
        manifest = build_manifest(self.principes, {"helmet": explicit, "crest": None})
        self.assertEqual(explicit, manifest["components"]["helmet"]["key"])
        self.assertEqual("explicit", manifest["components"]["helmet"]["selection"]["mode"])
        self.assertEqual("exact_manifest_asset", manifest["components"]["helmet"]["selection"]["resolution_policy"])
        self.assertIsNone(manifest["components"]["crest"])

    def test_auto_and_explicit_first_option_keep_distinct_intent(self):
        helmet = next(slot for slot in self.principes.component_slots if slot.key == "helmet")
        auto = build_manifest(self.principes, {"helmet": AutoSelection(helmet.default_key)})
        explicit = build_manifest(self.principes, {"helmet": helmet.default_key})
        self.assertEqual(auto["components"]["helmet"]["key"], explicit["components"]["helmet"]["key"])
        self.assertEqual("deterministic_source_first", auto["components"]["helmet"]["selection"]["mode"])
        self.assertEqual("explicit", explicit["components"]["helmet"]["selection"]["mode"])

    def test_schema_and_unit_identity_fail_before_assembly(self):
        broken = json.loads(json.dumps(self.manifest))
        broken["schema_version"] = 99
        with self.assertRaises(ConverterError) as caught:
            self.validate(broken)
        self.assertEqual(ErrorCode.MANIFEST_SCHEMA_UNSUPPORTED, caught.exception.code)
        broken = json.loads(json.dumps(self.manifest))
        broken["source"]["variant"] = "wrong_variant"
        with self.assertRaises(ConverterError) as caught:
            self.validate(broken)
        self.assertEqual(ErrorCode.MANIFEST_UNIT_MISMATCH, caught.exception.code)

    def test_wrong_component_and_required_none_are_rejected(self):
        broken = json.loads(json.dumps(self.manifest))
        broken["components"]["helmet"]["key"] = "not/a/unit/asset.rigid_model_v2"
        broken["components"]["helmet"]["source_path"] = broken["components"]["helmet"]["key"]
        with self.assertRaises(ConverterError) as caught:
            self.validate(broken)
        self.assertEqual(ErrorCode.MANIFEST_COMPONENT_INVALID, caught.exception.code)
        required = next(slot.key for slot in self.principes.component_slots if slot.required)
        broken = json.loads(json.dumps(self.manifest))
        broken["components"][required] = None
        with self.assertRaises(ConverterError) as caught:
            self.validate(broken)
        self.assertEqual(ErrorCode.REQUIRED_COMPONENT_MISSING, caught.exception.code)

    def test_tampered_attachment_metadata_is_rejected(self):
        broken = json.loads(json.dumps(self.manifest))
        broken["components"]["shield"]["socket"] = "weapon_02"
        with self.assertRaises(ConverterError) as caught:
            self.validate(broken)
        self.assertEqual(ErrorCode.MANIFEST_COMPONENT_INVALID, caught.exception.code)

    def test_configurator_uses_auto_not_default_terminology(self):
        source = (ROOT / "rome2aoe2/cli.py").read_text(encoding="utf-8")
        self.assertIn("[A] Auto (deterministic source-first)", source)
        self.assertNotIn("[D] Rome II default", source)

    def test_dependency_closure_must_be_ready(self):
        definition = replace(self.principes.definition, status="PARTIAL",
                             reason_codes=(ErrorCode.MISSING_REQUIRED_ASSET.value,))
        partial = replace(self.principes, definition=definition)
        with self.assertRaises(ConverterError) as caught:
            self.validate(self.manifest, _CatalogResult(partial))
        self.assertEqual(ErrorCode.MISSING_REQUIRED_ASSET, caught.exception.code)

    def test_output_identity_uses_stable_unit_and_manifest_hash(self):
        request = self.validate(self.manifest)
        self.assertEqual("rom_principes", request.output_directory.parent.name)
        self.assertEqual(manifest_digest(self.manifest), request.output_directory.name)
        self.assertNotIn(str(self.principes.definition.catalog_id), request.output_directory.parts[-2:])

    def test_static_report_has_generic_attachment_and_crest_validation(self):
        reports = sorted((ROOT / "build/conversions/rom_principes").glob("*/static-assembly-report.json"))
        self.assertTrue(reports, "run the Principes static acceptance conversion first")
        report_path = reports[-1]
        receipt_path = report_path.with_name("conversion-receipt.json")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        attachments = report["attachments"]
        self.assertEqual("bn_weapon_02", attachments["melee_weapon"]["carrier"])
        self.assertEqual("bn_weapon_03", attachments["shield"]["carrier"])
        self.assertEqual("bn_weapon_05", attachments["missile_weapon"]["carrier"])
        crest = attachments["crest"]
        self.assertFalse(crest["contact_solver"]["penetration"])
        self.assertTrue(receipt_path.is_file())
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(report["manifest_hash"], receipt["manifest_hash"])
        self.assertEqual("Rom_Principes", receipt["unit"])

    def test_frozen_hastati_static_resolution_is_unchanged(self):
        hastati = self.catalog.resolve("Rom_Hastati", "rom_rome")
        manifest = build_manifest(hastati)
        self.assertEqual("rome_man_game", manifest["animation"]["skeleton"])
        self.assertEqual("rome_man_sword_shield", manifest["animation"]["family"])
        self.assertEqual("weapon_02", manifest["components"]["melee_weapon"]["socket"])
        self.assertEqual("weapon_03", manifest["components"]["shield"]["socket"])
        self.assertEqual("crest_centre", manifest["components"]["crest"]["socket"])

    def test_generic_conversion_sources_have_no_unit_name_special_cases(self):
        for relative in ("rome2aoe2/conversion.py", "src/blender/assemble_manifest_static.py"):
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("Rom_Principes", source)
            self.assertNotIn("Rom_Hastati", source)

    def test_static_backend_uses_captured_material_parity_semantics(self):
        assembly = (ROOT / "src/blender/assemble_manifest_static.py").read_text(encoding="utf-8")
        self.assertIn('import rome2_exact_material_backend as exact_materials', assembly)
        self.assertIn('"backend": "rome2_exact_material_backend"', assembly)
        self.assertIn('"approximations": []', assembly)
        self.assertNotIn('apply_rome2_materials_recovered+captured-parity-fixes', assembly)

    def test_exact_static_backend_can_claim_capture_validated_readiness(self):
        source = (ROOT / "rome2aoe2/conversion.py").read_text(encoding="utf-8")
        exact = (ROOT / "src/blender/rome2_exact_material_backend.py").read_text(encoding="utf-8")
        self.assertNotIn("apply_rome2_materials_recovered", source)
        self.assertIn("render_hastati_runtime_parity import render_aov, shade", exact)
        self.assertNotIn("bounded generic", exact)
        self.assertNotIn("approximate dark", exact)


if __name__ == "__main__":
    unittest.main()
