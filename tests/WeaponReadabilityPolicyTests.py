import inspect,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rome2aoe2.production import production_identity,resolve_production_profile
from rome2aoe2.weapon_readability import MIXED_RESPONSE_CALIBRATION,reflection_tail_delta,resolve_weapon_readability

V3="aoe2-infantry-animation-production-v3-weapon-forward";V4="aoe2-infantry-animation-production-v4-shield-readability";V5="aoe2-infantry-animation-production-v5-equipment-readability"
GLADIUS={"specular_luminance":.4027,"smoothness":.1084,"reflectivity":.1428}
FAILURES=("direct_diffuse_collapse","reflective_specular_lobe_collapse")
class WeaponReadabilityPolicyTests(unittest.TestCase):
 def test_role_alone_does_not_force_treatment(self):self.assertFalse(resolve_weapon_readability("melee_weapon",GLADIUS)["enabled"])
 def test_validated_response_and_failures_resolve_mixed(self):
  r=resolve_weapon_readability("melee_weapon",GLADIUS,FAILURES);self.assertEqual("mixed_diffuse_and_reflection_dark_tail",r["treatment"]);self.assertEqual(1.8,r["diffuse_floor"]);self.assertEqual(.15,r["transition_width"]);self.assertEqual(.04,r["environment_reflection_floor"])
 def test_diffuse_only_omits_reflection_floor(self):
  r=resolve_weapon_readability("melee_weapon",GLADIUS,("direct_diffuse_collapse",));self.assertEqual("diffuse_dark_tail",r["treatment"]);self.assertNotIn("environment_reflection_floor",r)
 def test_dissimilar_and_non_weapon_default_none(self):
  unlike={"specular_luminance":.1,"smoothness":.4,"reflectivity":.02}
  self.assertFalse(resolve_weapon_readability("melee_weapon",unlike,FAILURES)["enabled"])
  for role in ("body","armour","shield"):self.assertFalse(resolve_weapon_readability(role,GLADIUS,FAILURES)["enabled"])
 def test_material_controls_are_not_blindly_assigned_gladius_treatment(self):
  controls=(
   {"specular_luminance":.5026,"smoothness":.1291,"reflectivity":.15}, # prepared pilum sample
   {"specular_luminance":.4971,"smoothness":.2871,"reflectivity":.15}, # prepared Hellenic spear sample
  )
  for response in controls:self.assertFalse(resolve_weapon_readability("melee_weapon",response)["enabled"])
 def test_reflection_floor_is_lower_tail_only(self):
  self.assertAlmostEqual(.025,reflection_tail_delta(.015));self.assertEqual(0,reflection_tail_delta(.04));self.assertEqual(0,reflection_tail_delta(.1542))
 def test_no_asset_or_unit_name_dispatch(self):
  source=inspect.getsource(sys.modules[resolve_weapon_readability.__module__]).casefold()
  for word in ('"gladius"','"principes"','"pilum"','"spear"','"iron"','"steel"','"bronze"','"roman_"'):self.assertNotIn(word,source)
 def test_v5_composes_immutable_v4_and_distinct_identity(self):
  v3=resolve_production_profile(V3);v4=resolve_production_profile(V4);v5=resolve_production_profile(V5)
  self.assertEqual(3,v3["version"]);self.assertEqual(4,v4["version"]);self.assertEqual(2.7,v4["render_capabilities"]["shield_readability"]["response_dispatch"]["diffuse_dominant"]["floor"]);self.assertEqual(v4["render_capabilities"]["shield_readability"],v5["render_capabilities"]["shield_readability"])
  record={"resolved_asset":"a","asset_sha256":"f"*64};ids=[production_identity("e"*64,"idle",record,p) for p in (V3,V4,V5)];self.assertEqual(3,len(set(ids)))
 def test_runtime_preserves_fsr_and_native_lighting_variation(self):
  source=(ROOT/"src/blender/render_hastati_runtime_parity.py").read_text();self.assertNotIn("F[weapon_pixels]=",source);self.assertNotIn("S[weapon_pixels]=",source);self.assertNotIn("R[weapon_pixels]=",source);self.assertIn("reflection_gap=np.maximum(0",source);self.assertIn("direct_refl",source)
if __name__=="__main__":unittest.main()
