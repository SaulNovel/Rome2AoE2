from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HASTATI_SCRIPTS = (
    "build_and_install_hastati_full_idle_test.ps1",
    "build_and_install_hastati_integration_test.ps1",
    "build_and_install_hastati_native_attack_test.ps1",
    "build_and_install_hastati_native_death_test.ps1",
    "build_and_install_hastati_native_walk_test.ps1",
    "build_and_install_hastati_test.ps1",
    "install_fast_corpse_test.ps1",
    "install_hastati_test.ps1",
)


class MigrationPathResolutionTests(unittest.TestCase):
    def test_hastati_powershell_defaults_use_explicit_profile_environment(self):
        for name in HASTATI_SCRIPTS:
            source = (ROOT / "scripts" / name).read_text(encoding="utf-8-sig")
            self.assertIn("$env:ROME2AOE2_AOE2_PROFILE", source, name)
            self.assertNotIn(r"C:\Users\sauln", source, name)

    def test_verifier_derives_frozen_children_from_supplied_profile(self):
        path = ROOT / "src/aoe2/verify_hastati_integration_install.py"
        spec = importlib.util.spec_from_file_location("verify_hastati_paths", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        profile = Path(r"D:\Games\AoE2DE\123456")
        mod = profile / "mods/local/Rome2AoE2 Hastati Dev Test"
        expected_mod, expected_scenario = module.expected_install_paths(mod)
        self.assertEqual(expected_mod, mod)
        self.assertEqual(
            expected_scenario,
            profile / "resources/_common/scenario/Rome2AoE2HastatiDevTest.aoe2scenario",
        )


if __name__ == "__main__":
    unittest.main()
