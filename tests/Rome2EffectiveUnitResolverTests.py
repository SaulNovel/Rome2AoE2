"""Local-integration validation for the effective Rome II unit resolver."""
import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/"build"/"local-integration"/"rome2"/"runtime-resolution"
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.doc=json.loads((BASE/"effective-units.json").read_text());cls.units={u["unit"]:u for u in cls.doc["units"]}
 def test_identity_chain_uses_land_variants(self):
  self.assertEqual(self.units["hastati"]["identity"]["variant_filename"],"variantmeshes/variantmeshdefinitions/roman_hastati.variantmeshdefinition")
  self.assertEqual(self.units["eastern-spearman"]["identity"]["variant_filename"],"variantmeshes/variantmeshdefinitions/eas_spear.variantmeshdefinition")
  self.assertEqual(self.units["praetorian"]["identity"]["variant_filename"],"variantmeshes/variantmeshdefinitions/roman_praetorian_guard.variantmeshdefinition")
 def test_standard_praetorian_is_not_third_century_vmd(self):
  p=self.units["praetorian"];self.assertNotIn("3c_",p["identity"]["variant_filename"]);models=[e.get("model") or "" for s in p["vmd"]["slots"] for e in s["entries"]];self.assertFalse(any("aurelian_pants" in x for x in models))
 def test_real_faction_colour_provenance(self):
  self.assertEqual((self.units["hastati"]["faction_colours"]["C0"],self.units["hastati"]["faction_colours"]["C1"],self.units["hastati"]["faction_colours"]["C2"]),("A62416","FFB504","993D24"))
  self.assertEqual(self.units["praetorian"]["faction_colours"]["source"],"unit_variants_colours:default")
 def test_unknown_runtime_choices_are_not_silently_selected(self):
  for u in self.units.values():
   for s in u["vmd"]["slots"]:
    if s["entry_count"]>1:self.assertEqual(s["selection"],{"status":"unresolved-runtime-random","selected_index":None})
   for a in u["decal_arrays"]:self.assertEqual(a["selection"]["selected_index"],None)
 def test_masks_are_recorded_as_colour_remaps(self):
  self.assertIn("not a visibility boolean",self.units["praetorian"]["vmd"]["mask_attribute_semantics"])
 def test_diagnostic_renders_exist(self):
  for key in self.units:self.assertGreater((BASE/"renders"/f"{key}-runtime-resolved-representative.png").stat().st_size,10000)
if __name__=="__main__":unittest.main()
