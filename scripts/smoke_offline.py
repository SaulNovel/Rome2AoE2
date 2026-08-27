"""Cheap offline structural smoke test; no game install or full render."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def main() -> int:
    result = subprocess.run([sys.executable, str(ROOT / "scripts/verify_offline_fixtures.py")])
    if result.returncode: return result.returncode
    manifest = json.loads((ROOT / "config/manifests/rom_principes-explicit-animations-v2.json").read_text(encoding="utf-8"))
    expected = {"idle": (43, 15), "walk": (23, 20), "attack": (27, 20), "death": (33, 15)}
    for key, (frames, fps) in expected.items():
        row = manifest["animations"][key]
        if row["frame_count"] != frames or row["fps"] != fps: print(f"FAIL {key} timing"); return 1
    print("PASS offline Principes dependency closure and frozen native animation identities")
    print("Run scripts/run_blender_fast_smoke.py for the pinned one-frame 400x400 Blender proof.")
    return 0
if __name__ == "__main__": raise SystemExit(main())
