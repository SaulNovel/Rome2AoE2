import json
import unittest
from collections import Counter

from rome2aoe2.catalog import Catalog, DEFAULT_CACHE, load_default_catalog
from rome2aoe2.errors import ConverterError, ErrorCode


class FullCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = json.loads(DEFAULT_CACHE.read_text(encoding="utf-8"))
        cls.catalog = load_default_catalog()
        cls.source_only = Catalog(cls.index, None, validated_evidence=False)
        cls.rome = cls.catalog.find_faction("rom_rome")

    def test_authoritative_source_index_discovers_full_roster(self):
        self.assertEqual("rome2aoe2.source-catalog", self.index["format"])
        self.assertEqual(1, self.index["schema_version"])
        self.assertEqual(640, len(self.index["factions"]))
        self.assertEqual(1563, len(self.index["units"]))
        self.assertEqual("data_rome2.pack", self.index["source"]["db_pack"])

    def test_faction_order_and_ids_are_deterministic(self):
        expected = sorted(
            self.catalog.factions,
            key=lambda faction: (faction.display_name.casefold(), faction.key),
        )
        self.assertEqual([f.key for f in expected], [f.key for f in self.catalog.factions])
        self.assertEqual(list(range(1, 641)), [f.catalog_id for f in self.catalog.factions])

    def test_units_are_grouped_and_ids_are_local_to_faction(self):
        self.assertEqual(113, len(self.rome.units))
        self.assertIn("Rom_Hastati", {unit.main_unit for unit in self.rome.units})
        self.assertIn("Rom_Principes", {unit.main_unit for unit in self.rome.units})
        self.assertEqual(list(range(1, 114)), [unit.catalog_id for unit in self.rome.units])

    def test_localization_and_authoritative_fallback_fields(self):
        rome_row = next(row for row in self.index["factions"] if row["key"] == "rom_rome")
        principes = next(row for row in self.index["units"] if row["main_unit"] == "Rom_Principes")
        self.assertEqual(("Rome", "localized"), (rome_row["display_name"], rome_row["display_source"]))
        self.assertEqual(("Principes", "localized"), (principes["display_name"], principes["display_source"]))
        self.assertTrue(principes["description"])
        self.assertIn(principes["display_source"], {"localized", "unit_variants.name", "main_units.unit"})

    def test_convertibility_classes_and_structured_reasons(self):
        self.assertEqual("READY", self.catalog.find_unit("Rom_Hastati", self.rome).status)
        principes = self.source_only.find_unit("Rom_Principes", "rom_rome")
        self.assertEqual("PARTIAL", principes.status)
        self.assertEqual(("MISSING_REQUIRED_ASSET",), principes.reason_codes)
        ballista = self.catalog.find_unit("Rom_Ballista", self.rome)
        self.assertEqual("UNSUPPORTED", ballista.status)
        self.assertIn("UNSUPPORTED_UNIT_CLASS", ballista.reason_codes)

    def test_invalid_faction_and_faction_local_unit_are_structured(self):
        with self.assertRaises(ConverterError) as caught:
            self.catalog.find_faction("not_a_faction")
        self.assertEqual(ErrorCode.FACTION_NOT_FOUND, caught.exception.code)
        with self.assertRaises(ConverterError) as caught:
            self.catalog.find_unit("not_a_unit", self.rome)
        self.assertEqual(ErrorCode.UNIT_NOT_FOUND, caught.exception.code)

    def test_catalog_existence_does_not_depend_on_effective_unit_evidence(self):
        self.assertEqual(1563, len(self.source_only.source_index["units"]))
        principes = self.source_only.find_unit("Rom_Principes", "rom_rome")
        self.assertEqual("PARTIAL", principes.status)
        self.assertEqual("Roman_Principes", principes.variants[0]["variant"])
        self.assertEqual("models_rome2.pack", principes.variants[0]["source_pack"])

    def test_hastati_resolution_remains_the_frozen_generic_result(self):
        hastati = self.catalog.resolve("Rom_Hastati")
        self.assertEqual("Rom_Hastati", hastati.land_unit)
        self.assertEqual("Roman_Hastati", hastati.variant)
        self.assertEqual(
            "variantmeshes/variantmeshdefinitions/roman_hastati.variantmeshdefinition",
            hastati.root_vmd,
        )
        self.assertEqual(("rome_man_sword_shield", "rome_man_game"),
                         (hastati.animation.family, hastati.animation.skeleton))

    def test_unique_status_counts_cover_every_discovered_unit(self):
        statuses = {row["main_unit"]: row["status"] for row in self.index["units"]}
        for faction in self.catalog.factions:
            for unit in faction.units:
                if unit.status == "READY":
                    statuses[unit.main_unit] = "READY"
        counts = Counter(statuses.values())
        self.assertEqual(1563, sum(counts.values()))
        self.assertEqual({"READY", "PARTIAL", "UNSUPPORTED"}, set(counts))


if __name__ == "__main__":
    unittest.main()
