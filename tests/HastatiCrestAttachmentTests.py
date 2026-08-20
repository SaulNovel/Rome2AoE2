import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "blender" / "crest_attachment.py"
SOLVER = ROOT / "src" / "blender" / "solve_crest_attachment.py"


class HastatiCrestAttachmentTests(unittest.TestCase):
    def test_geometry_contact_tolerances_are_frozen(self):
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        constants = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in tree.body if isinstance(node, ast.Assign)
            and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {
                "CONTACT_EPSILON", "SUPPORT_TOLERANCE",
            }
        }
        self.assertEqual(constants["CONTACT_EPSILON"], 1.0e-4)
        self.assertEqual(constants["SUPPORT_TOLERANCE"], 5.0e-4)

    def test_production_solver_uses_geometry_contact_without_visual_offsets(self):
        text = SOLVER.read_text(encoding="utf-8")
        self.assertIn("seat_crest(", text)
        self.assertNotIn("crest.location", text)

    def test_solver_preserves_orientation_and_uses_bn_head_space(self):
        text = MODULE.read_text(encoding="utf-8")
        self.assertIn('pose.bones["bn_head"].matrix', text)
        self.assertIn("orientation_matrix_max_error", text)
        self.assertIn("connected-component support contact", text)

    def test_pair_cache_uses_assets_and_socket_not_unit_name(self):
        text = MODULE.read_text(encoding="utf-8")
        self.assertIn("pair_key = (str(helmet_asset).lower(), str(crest_asset).lower(), socket_name.lower())", text)
        self.assertIn("PAIR_SOLUTION_CACHE[pair_key]", text)
        self.assertIn("PAIR_SOLUTION_CACHE.get(pair_key)", text)
        self.assertNotIn("hastati", text.lower())
        solver = (ROOT / "src" / "blender" / "solve_crest_attachment.py").read_text(encoding="utf-8")
        self.assertNotIn("montefortino", solver.lower())
        self.assertNotIn('"feather"', solver.lower())
        self.assertIn("mesh_for_asset(args.helmet_asset", solver)

    def test_geometry_selection_is_not_topology_hardcoded(self):
        text = MODULE.read_text(encoding="utf-8")
        self.assertNotIn("HELMET_MOUNT_VERTEX_COUNT", text)
        self.assertNotIn("CREST_ROOT_VERTEX_COUNTS", text)
        self.assertIn("lower_supports", text)
        self.assertIn("wrapper.matrix_world.to_3x3().col[2]", text)


if __name__ == "__main__":
    unittest.main()
