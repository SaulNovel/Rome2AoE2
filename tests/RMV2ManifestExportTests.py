import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("export_rmv2_manifest", ROOT / "src/rome2/export_rmv2_manifest.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RMV2ManifestExportTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / "build" / "rmv2-manifest-test"
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / "asset-extraction.json"

    def invoke(self, _helper, _arguments):
        return {"format": "rome2aoe2.rmv2-gltf-export", "selected_lod": 0, "mesh_count": 1, "vertex_count": 3, "triangle_count": 1, "materials": []}

    def export(self, origins):
        asset = {"normalized_path": "models/a.rigid_model_v2", "output_path": "a.rigid_model_v2", "asset_types": ["model"], "origins": origins}
        self.manifest_path.write_text(json.dumps({"format": "rome2aoe2.asset-extraction", "version": 1, "assets": [asset]}), encoding="utf-8")
        return MODULE.export_manifest(self.manifest_path, Path("helper.exe"), self.root / "out", invoke=self.invoke)

    def test_version_3_attach_point_provenance_reaches_export_manifest(self):
        origins = [{"attribute": "model", "attach_point": "weapon_02", "definition": "root", "reference_chain": ["root"], "slot_path": "weapon_2"}]
        self.assertEqual(self.export(origins)["exports"][0]["origins"], origins)

    def test_version_2_missing_attach_point_remains_unavailable(self):
        origins = [{"attribute": "model", "definition": "root", "reference_chain": ["root"], "slot_path": "weapon_2"}]
        exported = self.export(origins)["exports"][0]["origins"][0]
        self.assertNotIn("attach_point", exported)

    def test_output_is_deterministic(self):
        origins = [{"attribute": "model", "attach_point": "weapon_03", "definition": "root", "reference_chain": ["root"], "slot_path": "shield"}]
        self.assertEqual(self.export(origins), self.export(origins))


if __name__ == "__main__":
    unittest.main()
