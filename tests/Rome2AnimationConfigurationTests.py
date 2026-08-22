import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rome2aoe2.animation import (CATEGORIES, choose_candidate, discover, enrich_metadata,
                                 freeze_animations, preview_cache_identity)
from rome2aoe2.catalog import load_default_catalog
from rome2aoe2.conversion import load_and_validate_manifest, manifest_digest
from rome2aoe2.errors import ConverterError, ErrorCode
from rome2aoe2.manifest import build_manifest
from rome2aoe2.native_assembly import classify_components, export_identity, static_visual_manifest, ASSEMBLY_VERSION


class AnimationConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.unit = load_default_catalog().resolve("Rom_Principes", "rom_rome")
        cls.base = build_manifest(cls.unit)
        cls.groups = enrich_metadata(discover(cls.unit))

    def test_authoritative_principes_resolution_and_counts(self):
        self.assertEqual("rome_man_sword_shield", self.unit.animation.family)
        self.assertEqual("rome_man_game", self.unit.animation.skeleton)
        self.assertEqual({"idle": 2, "walk": 5, "attack": 5, "death": 13},
                         {key: len(value.candidates) for key, value in self.groups.items()})
        self.assertTrue(all("fragment" in item.provenance for group in self.groups.values() for item in group.candidates))

    def test_shortlist_show_more_and_order_are_deterministic(self):
        again = discover(self.unit)
        self.assertEqual([item.resolved_asset for item in again["death"].shortlist],
                         [item.resolved_asset for item in discover(self.unit)["death"].shortlist])
        self.assertEqual(5, len(again["death"].shortlist))
        self.assertEqual(8, len(again["death"].additional))

    def test_auto_explicit_and_invalid_selection(self):
        group = self.groups["walk"]
        self.assertEqual((group.recommendation, "deterministic_auto"), choose_candidate(group, "A"))
        self.assertEqual((group.candidates[2], "explicit"), choose_candidate(group, "3"))
        with self.assertRaises(ConverterError) as caught:
            choose_candidate(group, "99")
        self.assertEqual(ErrorCode.INVALID_ANIMATION_SELECTION, caught.exception.code)

    def test_manifest_freezes_paths_without_ui_ids(self):
        selections = {key: choose_candidate(group, "A") for key, group in self.groups.items()}
        frozen = freeze_animations(self.base, selections)
        encoded = json.dumps(frozen)
        self.assertEqual(2, frozen["schema_version"])
        self.assertNotIn("ui_id", encoded.casefold())
        for key in CATEGORIES:
            self.assertEqual(key, frozen["animations"][key]["category"])
            self.assertTrue(frozen["animations"][key]["resolved_asset"].endswith(".anim"))
            self.assertEqual("deterministic_auto", frozen["animations"][key]["mode"])

    def test_preview_identity_reuses_and_invalidates_visual_change(self):
        candidate = self.groups["idle"].recommendation
        first = preview_cache_identity(self.base, candidate)
        self.assertEqual(first, preview_cache_identity(self.base, candidate))
        changed = json.loads(json.dumps(self.base))
        changed["palette"] = {"faction": "different"}
        self.assertNotEqual(first, preview_cache_identity(changed, candidate))
        self.assertNotEqual(first, preview_cache_identity(self.base, self.groups["walk"].candidates[0]))

    def test_motion_policy_has_no_unit_special_case(self):
        source = (ROOT / "rome2aoe2/native_assembly.py").read_text(encoding="utf-8") + (ROOT / "src/blender/assemble_native_basis_animation.py").read_text(encoding="utf-8")
        self.assertNotIn("Rom_Principes", source)
        self.assertNotIn("Rom_Hastati", source)
        self.assertIn('doc["category"]=="walk"', source)

    def test_source_driven_weighted_rigid_classification(self):
        rows = {row.component: row for row in classify_components(self.base)}
        self.assertEqual({"armour", "body", "helmet"}, {key for key, row in rows.items() if row.deformation == "weighted"})
        self.assertEqual({"crest", "melee_weapon", "missile_weapon", "shield"},
                         {key for key, row in rows.items() if row.deformation == "rigid"})
        self.assertTrue(all(row.skeleton == "rome_man_game" for row in rows.values() if row.deformation == "weighted"))
        self.assertTrue(all(row.socket for row in rows.values() if row.deformation == "rigid"))

    def test_native_export_cache_depends_on_component_and_clip(self):
        weighted = next(row for row in classify_components(self.base) if row.deformation == "weighted")
        self.assertNotEqual(export_identity(weighted, self.groups["idle"].candidates[0]),
                            export_identity(weighted, self.groups["walk"].candidates[0]))
        self.assertIn("native-basis", ASSEMBLY_VERSION)

    def test_action_and_basis_provenance_are_unambiguous(self):
        native = (ROOT / "rome2aoe2/native_assembly.py").read_text(encoding="utf-8")
        assembler = (ROOT / "src/blender/assemble_native_basis_animation.py").read_text(encoding="utf-8")
        for field in ("requested_animation_clip", "basis_export_clip", "canonical_action_clip"):
            self.assertIn(field, native)
            self.assertIn(field, assembler)
        self.assertIn("runner_reported_action_name", assembler)
        self.assertNotIn('"imported_action_name":', assembler)

    def test_frozen_animations_do_not_change_static_visual_identity(self):
        selections = {key: choose_candidate(group, "1") for key, group in self.groups.items()}
        frozen = freeze_animations(self.base, selections)
        self.assertEqual(self.base, static_visual_manifest(frozen))

    def test_native_assembler_never_imports_static_weighted_gltf(self):
        source = (ROOT / "src/blender/assemble_native_basis_animation.py").read_text(encoding="utf-8")
        self.assertIn('record["gltf"]', source)
        self.assertIn('old_meshes', source)
        self.assertIn('bpy.data.objects.remove(obj,do_unlink=True)', source)
        self.assertNotIn('static-assembly-input.json', source)
        self.assertNotIn("Rom_Principes", source)
        self.assertNotIn("Rom_Hastati", source)

    def test_native_assembler_contract_covers_materials_carriers_and_category_policies(self):
        source = (ROOT / "src/blender/assemble_native_basis_animation.py").read_text(encoding="utf-8")
        for carrier in ("crest_centre", "weapon_02", "weapon_03", "weapon_05"):
            self.assertIn(carrier, json.dumps(self.base))
        self.assertIn("material_map", source)
        self.assertIn("rest_matrix_max_delta", source)
        self.assertIn("action_fingerprint_preserved", source)
        self.assertIn('doc["category"] in {"walk","death"}', source)
        self.assertIn("Rome2AoE2_DeathPreviewHorizontalCenter", source)
        self.assertNotIn("bn_hips.location", source)

    def test_approved_principes_manifest_contract_and_noninteractive_reload(self):
        path = ROOT / "config/manifests/rom_principes-explicit-animations-v2.json"
        request = load_and_validate_manifest(path)
        expected = {
            "idle": ("STAND", "sws_stand.anim"),
            "walk": ("WALK_2", "sws_walk_162_cm.anim"),
            "attack": ("ATTACK_5", "sws_sync_atk_005.anim"),
            "death": ("DEATH_STAND_4", "sws_death_stand_004.anim"),
        }
        self.assertEqual("611db84c371e707bbf8c14626402077a8974f7d8c14af1941b0f38905f39625b",
                         request.manifest_hash)
        for category, (state, filename) in expected.items():
            row = request.manifest["animations"][category]
            self.assertEqual(("explicit", "exact_manifest_asset"),
                             (row["mode"], row["resolution_policy"]))
            self.assertEqual(state, row["resolved_state"])
            self.assertTrue(row["resolved_asset"].endswith(filename))
        self.assertEqual(["DEATH_STAND_4", "DEATH_STAND_10"],
                         request.manifest["animations"]["death"]["source_states"])

    def test_stale_runner_label_is_reported_but_never_used_as_candidate_identity(self):
        source = (ROOT / "rome2aoe2/native_assembly.py").read_text(encoding="utf-8")
        self.assertIn("runner_reported_clip", source)
        for field in ("requested_animation_clip", "basis_export_clip", "canonical_action_clip",
                      "requested_animation_sha256"):
            self.assertIn(field, source)
        self.assertIn('"animation": file_sha256(Path(candidate.local_asset))', source)


if __name__ == "__main__":
    unittest.main()
