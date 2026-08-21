import json
import unittest
from dataclasses import replace
from pathlib import Path

from rome2aoe2.catalog import load_default_catalog
from rome2aoe2.dependencies import DependencyResolver, canonical_path, plan_json
from rome2aoe2.errors import ConverterError, ErrorCode
from rome2aoe2.manifest import build_manifest


ROOT = Path(__file__).resolve().parents[1]


class DependencyResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_default_catalog()
        cls.resolver = DependencyResolver()
        cls.principes_definition = cls.catalog.find_unit("Rom_Principes", "rom_rome")
        cls.principes_plan = cls.resolver.extract(cls.resolver.plan(cls.principes_definition))
        cls.principes = cls.resolver.resolved_unit(cls.principes_plan)

    def test_principes_chain_comes_from_authoritative_catalog(self):
        unit = self.principes
        self.assertEqual("Rom_Principes", unit.land_unit)
        self.assertEqual("Roman_Principes", unit.variant)
        self.assertEqual("variantmeshes/variantmeshdefinitions/roman_principes.variantmeshdefinition",
                         unit.root_vmd)
        self.assertEqual(("rome_man_sword_shield", "rome_man_game"),
                         (unit.animation.family, unit.animation.skeleton))

    def test_dependency_plan_is_deterministic(self):
        first = plan_json(self.resolver.plan(self.principes_definition))
        second = plan_json(self.resolver.plan(self.principes_definition))
        self.assertEqual(first, second)

    def test_recursive_vmds_and_pack_provenance_are_retained(self):
        vmds = [item for item in self.principes_plan.dependencies if item.kind == "VMD"]
        self.assertGreater(len(vmds), 1)
        self.assertTrue(all(item.source_pack for item in vmds))
        self.assertIn("models_rome2.pack", {item.source_pack for item in vmds})
        self.assertIn("models3_rome2.pack", {item.source_pack for item in vmds})

    def test_dependency_closure_has_no_duplicate_canonical_assets(self):
        identities = [(item.kind, canonical_path(item.path)) for item in self.principes_plan.dependencies]
        self.assertEqual(len(identities), len(set(identities)))

    def test_required_optional_and_shader_default_handling(self):
        crest = next(slot for slot in self.principes.component_slots if slot.key == "crest")
        self.assertFalse(crest.required)
        sentinels = [item for item in self.principes_plan.dependencies
                     if item.metadata.get("shader_default")]
        self.assertTrue(sentinels)
        self.assertTrue(all(not item.required and item.validation_state == "valid" for item in sentinels))

    def test_missing_required_asset_produces_structured_reassessment(self):
        required = next(item for item in self.principes_plan.dependencies if item.required)
        broken = replace(self.principes_plan, dependencies=(
            replace(required, validation_state="missing"),
            *(item for item in self.principes_plan.dependencies if item is not required),
        ))
        self.assertEqual(("PARTIAL", (ErrorCode.MISSING_REQUIRED_ASSET.value,)),
                         self.resolver.validate(broken))

    def test_missing_root_vmd_is_structured(self):
        broken = replace(self.principes_definition, variants=())
        with self.assertRaises(ConverterError) as caught:
            self.resolver.plan(broken)
        self.assertEqual(ErrorCode.UNRESOLVED_VMD, caught.exception.code)

    def test_post_extraction_principes_is_ready_and_manifest_uses_defaults(self):
        self.assertEqual(("READY", ()), self.resolver.validate(self.principes_plan))
        self.assertEqual("READY", self.principes.definition.status)
        manifest = build_manifest(self.principes)
        self.assertEqual("Rom_Principes", manifest["source"]["main_unit"])
        self.assertEqual("rome_man_game", manifest["animation"]["skeleton"])
        self.assertEqual(next(slot.default_key for slot in self.principes.component_slots if slot.key == "armour"),
                         manifest["components"]["armour"]["key"])

    def test_shared_hastati_assets_are_cache_hits_and_frozen_result_is_unchanged(self):
        hastati_definition = self.catalog.find_unit("Rom_Hastati", "rom_rome")
        hastati_plan = self.resolver.plan(hastati_definition)
        self.assertGreater(hastati_plan.cache_hits, 0)
        shared = {item.path for item in self.principes_plan.dependencies} & {
            item.path for item in hastati_plan.dependencies
        }
        self.assertIn("variantmeshes/_variantmodels/man/weapons/roman_gladius.rigid_model_v2", shared)
        frozen = self.catalog.resolve("Rom_Hastati")
        self.assertEqual("Roman_Hastati", frozen.variant)
        self.assertEqual("rome_man_sword_shield", frozen.animation.family)
        self.assertEqual("rome_man_game", frozen.animation.skeleton)

    def test_generic_production_resolver_contains_no_unit_name_special_case(self):
        source = (ROOT / "rome2aoe2/dependencies.py").read_text(encoding="utf-8")
        self.assertNotIn("Rom_Principes", source)
        self.assertNotIn("Rom_Hastati", source)


if __name__ == "__main__":
    unittest.main()
