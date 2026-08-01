import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rome2.resolve_variant_mesh_definition import (
    MissingVariantMeshDefinitionError,
    VariantMeshDefinitionCycleError,
    manifest_json,
    resolve,
)


FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "variant_mesh_definitions"
RECURSIVE = FIXTURE_ROOT / "recursive"


class VariantMeshDefinitionResolverTests(unittest.TestCase):
    def test_resolves_only_the_first_variant_in_each_slot(self):
        manifest = resolve(FIXTURE_ROOT / "first_variant.variantmeshdefinition", FIXTURE_ROOT)

        self.assertEqual(manifest["selection_strategy"], "first-variant-per-slot")
        self.assertEqual(
            [dependency["normalized_path"] for dependency in manifest["dependencies"]],
            [
                "variantmeshes/textures/shield_diffuse.dds",
                "variantmeshes/textures/shield_normal.dds",
                "variantmeshes/units/body.rigid_model_v2",
                "variantmeshes/units/crest.rigid_model_v2",
                "variantmeshes/units/helmet.rigid_model_v2",
                "variantmeshes/units/shield.rigid_model_v2",
            ],
        )
        self.assertEqual(manifest["dependencies"][2]["path"], "VariantMeshes\\\\Units\\\\Body.RIGID_MODEL_V2")
        self.assertEqual(
            manifest["dependencies"][3]["origins"],
            [{
                "attribute": "model",
                "definition": "first_variant.variantmeshdefinition",
                "reference_chain": ["first_variant.variantmeshdefinition"],
                "slot_path": "type/helmet/crest",
            }],
        )

    def test_resolves_direct_reference_relative_to_configurable_root(self):
        manifest = resolve(RECURSIVE / "direct_root.variantmeshdefinition", FIXTURE_ROOT)

        self.assertEqual(
            manifest["definitions"],
            [
                {"path": "recursive/direct_child.variantmeshdefinition", "normalized_path": "recursive/direct_child.variantmeshdefinition"},
                {"path": "recursive/direct_root.variantmeshdefinition", "normalized_path": "recursive/direct_root.variantmeshdefinition"},
            ],
        )
        dependency = manifest["dependencies"][0]
        self.assertEqual(dependency["path"], "VariantMeshes/Characters/DirectChild.RIGID_MODEL_V2")
        self.assertEqual(dependency["normalized_path"], "variantmeshes/characters/directchild.rigid_model_v2")
        self.assertEqual(dependency["origins"][0]["reference_chain"], [
            "recursive/direct_root.variantmeshdefinition",
            "recursive/direct_child.variantmeshdefinition",
        ])

    def test_resolves_multiple_reference_levels_and_collects_decals(self):
        manifest = resolve(RECURSIVE / "multi_root.variantmeshdefinition", FIXTURE_ROOT)

        self.assertEqual(len(manifest["definitions"]), 3)
        self.assertEqual(len(manifest["dependencies"]), 2)
        self.assertEqual(
            manifest["dependencies"][0]["origins"][0]["reference_chain"],
            [
                "recursive/multi_root.variantmeshdefinition",
                "recursive/level_one.variantmeshdefinition",
                "recursive/level_two.variantmeshdefinition",
            ],
        )

    def test_detects_direct_reference_cycle(self):
        with self.assertRaisesRegex(
            VariantMeshDefinitionCycleError,
            r"Recursive VariantMeshDefinition reference detected: recursive/self_cycle\.variantmeshdefinition -> recursive/self_cycle\.variantmeshdefinition",
        ):
            resolve(RECURSIVE / "self_cycle.variantmeshdefinition", FIXTURE_ROOT)

    def test_detects_indirect_reference_cycle(self):
        with self.assertRaisesRegex(
            VariantMeshDefinitionCycleError,
            r"cycle_a\.variantmeshdefinition -> recursive/cycle_b\.variantmeshdefinition -> recursive/cycle_c\.variantmeshdefinition -> recursive/cycle_a\.variantmeshdefinition",
        ):
            resolve(RECURSIVE / "cycle_a.variantmeshdefinition", FIXTURE_ROOT)

    def test_deduplicates_a_definition_reached_by_two_slots_without_losing_origins(self):
        manifest = resolve(RECURSIVE / "shared_root.variantmeshdefinition", FIXTURE_ROOT)

        self.assertEqual(len(manifest["definitions"]), 2)
        self.assertEqual(len(manifest["dependencies"]), 1)
        self.assertEqual(
            [origin["slot_path"] for origin in manifest["dependencies"][0]["origins"]],
            ["left", "right"],
        )

    def test_reports_missing_referenced_definition_with_context(self):
        with self.assertRaisesRegex(MissingVariantMeshDefinitionError, r"referring_definition='recursive/missing_root\.variantmeshdefinition'.*referenced_definition='recursive/not_present\.variantmeshdefinition'.*slot_path='missing-slot'.*reference_chain='recursive/missing_root\.variantmeshdefinition -> recursive/not_present\.variantmeshdefinition'") as captured:
            resolve(RECURSIVE / "missing_root.variantmeshdefinition", FIXTURE_ROOT)
        error = captured.exception
        self.assertEqual(error.referring_definition, "recursive/missing_root.variantmeshdefinition")
        self.assertEqual(error.referenced_definition, "recursive/not_present.variantmeshdefinition")
        self.assertEqual(error.slot_path, "missing-slot")
        self.assertEqual(error.reference_chain, ["recursive/missing_root.variantmeshdefinition", "recursive/not_present.variantmeshdefinition"])

    def test_deduplicates_models_using_normalized_key_but_preserves_first_original_path(self):
        manifest = resolve(RECURSIVE / "duplicate_root.variantmeshdefinition", FIXTURE_ROOT)

        self.assertEqual(len(manifest["dependencies"]), 1)
        dependency = manifest["dependencies"][0]
        self.assertEqual(dependency["path"], "VariantMeshes/Characters/Duplicate.RIGID_MODEL_V2")
        self.assertEqual(dependency["normalized_path"], "variantmeshes/characters/duplicate.rigid_model_v2")
        self.assertEqual(len(dependency["origins"]), 2)

    def test_manifest_is_deterministic_and_machine_readable(self):
        first = manifest_json(resolve(RECURSIVE / "multi_root.variantmeshdefinition", FIXTURE_ROOT))
        second = manifest_json(resolve(RECURSIVE / "multi_root.variantmeshdefinition", FIXTURE_ROOT))

        self.assertEqual(first, second)
        self.assertEqual(json.loads(first), resolve(RECURSIVE / "multi_root.variantmeshdefinition", FIXTURE_ROOT))


if __name__ == "__main__":
    unittest.main()
