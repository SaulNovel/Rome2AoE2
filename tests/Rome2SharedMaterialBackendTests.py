import inspect
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/rome2"))
sys.path.insert(0, str(ROOT / "src/blender"))

import runtime_material_preparation as core


class SharedMaterialBackendTests(unittest.TestCase):
    def test_all_validated_replays_import_shared_preparation(self):
        for name, function in (
            ("replay_weighted_capture.py", "prepare_weighted"),
            ("replay_weighted_skin_capture.py", "prepare_weighted_skin_dirtmap"),
            ("replay_decal_dirtmap_capture.py", "prepare_decal_dirtmap"),
        ):
            text = (ROOT / "src/rome2" / name).read_text()
            self.assertIn("runtime_material_preparation import", text)
            self.assertIn(function, text)

    def test_production_imports_same_core_and_has_no_node_formula_copy(self):
        text = (ROOT / "src/blender/render_hastati_runtime_parity.py").read_text()
        self.assertIn("from runtime_material_preparation import", text)
        self.assertNotIn("def exact_tangent_normal", text)
        self.assertNotIn("def faction_tint", text)
        self.assertIn('"UVMap.001" if material_type=="WeightedSkinDirtmap"', text)

    def test_skin_reconstructs_z_before_dirt_and_preserves_mask(self):
        normal_sample=np.array((0.0,.65,0.0,.7),np.float32)
        dirt=np.array((.9,.1,0,.8),np.float32);mask=np.array((0,0,0,.75),np.float32)
        basis=np.eye(3,dtype=np.float32)
        skin=np.array((.2,.7,.4,1),np.float32)
        p=core.prepare_weighted_skin_dirtmap(
            np.array((.6,.3,.2,1),np.float32),normal_sample,np.array((.5,.2,0,1),np.float32),
            mask,dirt,skin,basis[2],basis[0],basis[1])
        tx,ty=core.ag_xy(normal_sample);tz=np.sqrt(max(0,1-tx*tx-ty*ty))
        expected=core.normalize(np.array((tx+(2*dirt[0]-1)*mask[3],ty+(2*dirt[1]-1)*mask[3],tz)))
        np.testing.assert_allclose(p.normal,expected,rtol=0,atol=1e-6)
        np.testing.assert_array_equal(p.specular,skin[:3])

    def test_gbuffer_layouts_remain_family_specific(self):
        basis=np.eye(3,dtype=np.float32);d=np.array((.36,.16,.04,1),np.float32)
        weighted=core.prepare_weighted(d,np.array((.1,.2,.3,1),np.float32),np.array((0,.5,0,.5),np.float32),np.array((.4,.2,0,1),np.float32),basis[2],basis[0],basis[1])
        skin=core.prepare_weighted_skin_dirtmap(d,np.array((0,.5,0,.5),np.float32),np.array((.4,.2,0,1),np.float32),np.zeros(4,np.float32),np.zeros(4,np.float32),np.array((.2,.3,.4,1),np.float32),basis[2],basis[0],basis[1])
        _,wr1,wr2=core.pack_gbuffer(weighted);_,sr1,sr2=core.pack_gbuffer(skin)
        np.testing.assert_allclose(wr1[:3],np.sqrt(d[:3]))
        np.testing.assert_allclose(sr1[:3],d[:3])
        np.testing.assert_allclose(wr2,np.array((.1,.2,.3,0)))
        np.testing.assert_allclose(sr2,np.array((.2,.3,.4,.4)))

    def test_early_scutum_uses_shield_specific_faction_slot_order(self):
        colours=np.array(((.39,.01,.005),(1,.47,0),(.325,.043,.013)),np.float32)
        mapped=core.shield_faction_colours(colours)
        np.testing.assert_array_equal(mapped,colours[[0,2,1]])
        diffuse=np.array((.8,.7,.6,1),np.float32)
        yellow_mask=np.array((1,1,0,1),np.float32)
        result=core.faction_diffuse(diffuse,yellow_mask,mapped)
        self.assertGreater(result[0],result[1]*5)
        self.assertGreater(result[0],result[2]*5)


if __name__ == "__main__":
    unittest.main(argv=[__file__])
