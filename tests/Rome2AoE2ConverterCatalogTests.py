import io
import json
import unittest
from pathlib import Path

from rome2aoe2.catalog import load_default_catalog
from rome2aoe2.cli import choose_component, choose_unit
from rome2aoe2.errors import ConverterError, ErrorCode
from rome2aoe2.manifest import AutoSelection, build_manifest, select_components


ROOT = Path(__file__).resolve().parents[1]
HASTATI_MODELS = {
    "body": "variantmeshes/_variantmodels/man/skin/roman_skin1_shape1.rigid_model_v2",
    "tunic": "variantmeshes/_variantmodels/man/tunics/e3_tunic.rigid_model_v2",
    "armour": "variantmeshes/_variantmodels/man/armour/italian_square_muscled_cuirass_a.rigid_model_v2",
    "helmet": "variantmeshes/_variantmodels/man/helmets/roman_montefortino.rigid_model_v2",
    "crest": "variantmeshes/_variantmodels/man/crests/black_feather_03.rigid_model_v2",
    "shield": "variantmeshes/_variantmodels/man/shield/roman_early_scutum.rigid_model_v2",
    "melee_weapon": "variantmeshes/_variantmodels/man/weapons/roman_gladius.rigid_model_v2",
    "missile_weapon": "variantmeshes/_variantmodels/man/weapons/roman_pilum_light.rigid_model_v2",
}


class ConverterCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_default_catalog()
        cls.hastati = cls.catalog.resolve("Rom_Hastati")

    def test_catalog_ids_are_deterministic_sorted_and_not_aoe_ids(self):
        for faction in self.catalog.factions:
            ids = [unit.catalog_id for unit in faction.units]
            self.assertEqual(list(range(1, len(ids) + 1)), ids)
            self.assertNotIn(2081, ids)
        expected = sorted(
            self.catalog.factions,
            key=lambda faction: (faction.display_name.casefold(), faction.key.casefold()),
        )
        self.assertEqual([f.key for f in expected], [f.key for f in self.catalog.factions])
        self.assertEqual(
            list(range(1, len(self.catalog.factions) + 1)),
            [f.catalog_id for f in self.catalog.factions],
        )

    def test_hastati_resolves_actual_db_chain_and_animation(self):
        unit = self.hastati
        self.assertEqual("rom_rome", unit.definition.faction_key)
        self.assertEqual("Rom_Hastati", unit.definition.main_unit)
        self.assertEqual("Rom_Hastati", unit.land_unit)
        self.assertEqual("Roman_Hastati", unit.variant)
        self.assertEqual("variantmeshes/variantmeshdefinitions/roman_hastati.variantmeshdefinition", unit.root_vmd)
        self.assertEqual("rome_man_game", unit.animation.skeleton)
        self.assertEqual("rome_man_sword_shield", unit.animation.family)

    def test_hastati_default_components_match_frozen_source_configuration(self):
        chosen = select_components(self.hastati)
        for key, expected in HASTATI_MODELS.items():
            self.assertIn(key, chosen)
            self.assertEqual(expected, chosen[key].key)
        self.assertEqual("weapon_02", chosen["melee_weapon"].socket)
        self.assertEqual("weapon_05", chosen["missile_weapon"].socket)
        self.assertEqual("crest_centre", chosen["crest"].socket)
        self.assertEqual("weapon_03", chosen["shield"].socket)

    def test_manifest_contains_stable_source_keys_not_ui_ids(self):
        manifest = build_manifest(self.hastati)
        self.assertEqual(1, manifest["schema_version"])
        self.assertEqual("Rom_Hastati", manifest["source"]["main_unit"])
        self.assertEqual("rome_man_game", manifest["animation"]["skeleton"])
        self.assertEqual(
            {"capability": "infantry_visual_scale_v1", "mode": "deterministic_default",
             "reference": "aoe2_infantry_production_baseline", "value": 1.0},
            manifest["appearance"]["visual_scale"])
        self.assertNotIn("catalog_id", json.dumps(manifest))

    def test_structured_invalid_unit_and_component_errors(self):
        with self.assertRaises(ConverterError) as caught:
            self.catalog.resolve("999999")
        self.assertEqual(ErrorCode.UNIT_NOT_FOUND, caught.exception.code)
        with self.assertRaises(ConverterError) as caught:
            build_manifest(self.hastati, {"helmet": "not/a/real/model"})
        self.assertEqual(ErrorCode.COMPONENT_NOT_FOUND, caught.exception.code)
        required = next(slot for slot in self.hastati.component_slots if slot.required)
        with self.assertRaises(ConverterError) as caught:
            build_manifest(self.hastati, {required.key: None})
        self.assertEqual(ErrorCode.REQUIRED_COMPONENT_MISSING, caught.exception.code)

    def test_interactive_invalid_ids_reprompt_cleanly(self):
        unit_input = io.StringIO("999999\nRom_Hastati\n")
        output = io.StringIO()
        unit = choose_unit(self.catalog, unit_input, output, self.catalog.find_faction("rom_rome"))
        self.assertEqual("Rom_Hastati", unit.definition.main_unit)
        self.assertIn("UNIT_NOT_FOUND", output.getvalue())
        required = next(slot for slot in unit.component_slots if slot.required)
        output = io.StringIO()
        selected = choose_component(required, io.StringIO("0\nA\n"), output)
        self.assertEqual(required.default_key, selected)
        self.assertIsInstance(selected, AutoSelection)
        self.assertIn("REQUIRED_COMPONENT_MISSING", output.getvalue())


if __name__ == "__main__":
    unittest.main()
