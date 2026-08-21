import base64
import json
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IDENTITY = "bc5d577aadbce8e452d4419c6282e1e0d916900a9038516b321684ead85135c6"
GLTF = ROOT / "build/conversions/rom_principes" / IDENTITY / "gltf"


def accessor(document, index):
    row = document["accessors"][index]
    view = document["bufferViews"][row["bufferView"]]
    uri = document["buffers"][view["buffer"]]["uri"]
    data = base64.b64decode(uri.split(",", 1)[1])
    offset = view.get("byteOffset", 0) + row.get("byteOffset", 0)
    stride = view.get("byteStride", 8)
    width = {"VEC2": 2, "VEC3": 3, "VEC4": 4}[row["type"]]
    return [struct.unpack_from("<" + "f" * width, data, offset + i * stride)
            for i in range(row["count"])]


class GltfVertexRoutingTests(unittest.TestCase):
    def test_exporter_uses_explicit_packed_vertex_encoding(self):
        source = (ROOT / "third_party/rpfm/rpfm_extensions/src/gltf/mod.rs").read_text(encoding="utf-8")
        self.assertIn("const GLTF_VERTEX_STRIDE: usize = 120", source)
        self.assertIn("let vertex_bin = encode_vertices(vertices)", source)
        self.assertNotIn("let vertex_bin = to_padded_byte_vector(vertices.clone())", source)

    def test_selected_primary_uv_accessors_are_texture_coordinates(self):
        paths = list(GLTF.glob("*/*.gltf"))
        self.assertEqual(7, len(paths))
        for path in paths:
            document = json.loads(path.read_text(encoding="utf-8"))
            for mesh in document["meshes"]:
                values = accessor(document, mesh["primitives"][0]["attributes"]["TEXCOORD_0"])
                flattened = [value for pair in values for value in pair]
                self.assertGreaterEqual(min(flattened), -0.001, path)
                self.assertLessEqual(max(flattened), 1.001, path)

    def test_skin_empty_secondary_uv_is_preserved_as_degenerate_source_data(self):
        document = json.loads((GLTF / "body/roman_skin1_shape1.gltf").read_text(encoding="utf-8"))
        for mesh in document["meshes"]:
            values = accessor(document, mesh["primitives"][0]["attributes"]["TEXCOORD_1"])
            self.assertEqual({(0.0, 0.0)}, set(values))

    def test_runtime_falls_back_from_degenerate_secondary_uv(self):
        source = (ROOT / "src/blender/render_hastati_runtime_parity.py").read_text(encoding="utf-8")
        self.assertIn("def _normal_uv_name", source)
        self.assertIn('return "UVMap.001"', source)
        self.assertIn('return "UVMap"', source)


if __name__ == "__main__":
    unittest.main()
