import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rome2.rmv2_named_attachment import compose_runtime, named_attachment_local


class NamedAttachmentTransformTests(unittest.TestCase):
    def test_runtime_capture_reconstruction(self):
        root = ((0.947655261, 0, 0, 247.446914673), (0, 0.947655261, 0, 366.161712646), (0, 0, 0.947655261, -425.561157227), (0, 0, 0, 1))
        delta = ((0.995918989, -0.085893668, 0.027858261, 0.162444428), (0.085765496, 0.996301115, 0.005751329, -0.943452418), (-0.028253458, -0.003339224, 0.999593437, 0.073481321), (0, 0, 0, 1))
        bind = ((-0.000014206, 1.000014469, 0.000002747, 0.000009393), (-0.999846838, -0.000014469, -0.018401090, 1.581373549), (-0.018403837, 0, 0.999832632, -0.012678036), (0, 0, 0, 1))
        attachment = ((-0.0000003111, 0.9841441512, -0.1773701608, 0.2417578250), (0.9999999404, -0.0000070464, -0.0000411794, -0.0002055045), (-0.0000417754, -0.1773701608, -0.9841441512, -0.0150617408))
        pivot = ((1, 0, 0, 0.008174144), (0, 1, 0, 0.1027770), (0, 0, 1, 0.01105482), (0, 0, 0, 1))
        captured = ((-0.943787515, -0.084564865, -0.013102650, 247.435455322), (-0.081278794, 0.931241035, -0.155685633, 367.082366943), (0.026772477, -0.153925747, -0.934685349, -425.545288086), (0, 0, 0, 1))
        reconstructed = compose_runtime(root, delta, bind, attachment, pivot)
        self.assertLess(max(abs(reconstructed[r][c] - captured[r][c]) for r in range(4) for c in range(4)), 4.2e-5)

    def test_named_local_is_generic_and_direct(self):
        rows = ((1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12))
        self.assertEqual(named_attachment_local(rows), ((-1, -2, -3, -4), (-5, -6, -7, -8), (9, 10, 11, 12), (0, 0, 0, 1)))


if __name__ == "__main__":
    unittest.main()
