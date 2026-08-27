"""Read-only new-machine environment audit. Uses only the Python stdlib."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MANIFEST_BYTES = "4ead2bf1a918fe33a4ef3ae2fd472233877717b8ab54679fd500b97449e5a496"
EXPECTED_MANIFEST_CANONICAL = "611db84c371e707bbf8c14626402077a8974f7d8c14af1941b0f38905f39625b"
SUBMODULES = {"third_party/googletest": "b78aa5ee64be299ae50932e7b4d7e5d7b89a72f6",
              "third_party/rpfm": "fdde51aa9e6826afda1832d1b563b5f11125dc75",
              "third_party/AoE2ScenarioParser": "b763e2e37006bedab50c7d349b3ce24b9c2497f6"}
RPFM_PATCHES = {
    "patches/rpfm/0001-support-rome2-default-layout-materials.patch": "0dd66768c8656119ea6e1460f9ac4a927661e5c3898f0153984527bae28ee2be",
    "patches/rpfm/0002-preserve-rmv-pivots-and-serialize-gltf-vertices.patch": "0e38820ecf99809b36ce9729d9ce36a1bfb8870fa42c17b4742484afec7f8a08",
}
RPFM_NORMALIZED_TEXT = {
    "rpfm_extensions/src/gltf/mod.rs": "a6ce533d0a301984c25f902cbb8e70ff7b79cf3cef747cf8463f718a8b8d365f",
    "rpfm_lib/src/files/rigidmodel/materials/mod.rs": "f57f7e16353702ec1e2f49b5f2f7b5bffcc97844d33868088f78a07b7935fab3",
    "rpfm_lib/src/files/rigidmodel/test_rigidmodel.rs": "16ebf67f4d6f3084eba9476cf084b0e2d5c70f6eb1f382487c9abd3bb5299eb9",
    "rpfm_lib/src/files/rigidmodel/vertices/mod.rs": "fe9ff8467e5ad7c4551f3a35f5639a0b6c127007ddfe19dd3240d9cbf14697c9",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_text_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def command(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=20)
        return result.returncode == 0, (result.stdout or result.stderr).splitlines()[0]
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="return nonzero for required failures")
    parser.add_argument("--fixtures", action="store_true", help="require and hash the private fixtures")
    args = parser.parse_args()
    failures = 0
    def report(ok: bool, name: str, detail: str = "") -> None:
        nonlocal failures
        print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
        failures += not ok
    report(sys.version_info[:2] == (3, 14), "Python", sys.version.split()[0] + " (supported: 3.14.x)")
    for package, version in (("Pillow", "12.1.0"), ("numpy", "2.5.1"),
                             ("aoe2-genie-tooling", "1.2.4"), ("deprecation", "2.1.0"),
                             ("ordered-set", "4.1.0"), ("typing_extensions", "4.12.2")):
        try: actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: actual = "missing"
        report(actual == version, f"package {package}", actual)
    try: opencv = importlib.metadata.version("opencv-python")
    except importlib.metadata.PackageNotFoundError: opencv = "not installed (supported fallback active)"
    print(f"INFO optional package opencv-python: {opencv}")
    blender = os.environ.get("ROME2AOE2_BLENDER") or shutil.which("blender") or r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
    ok, output = command([blender, "--version"])
    report(ok and output.startswith("Blender 5.2.0"), "Blender", f"{blender} ({output})")
    for executable in ("git", "cargo", "cmake"):
        ok, output = command([executable, "--version"])
        report(ok, executable, output)
    for path, expected in SUBMODULES.items():
        ok, actual = command(["git", "-C", str(ROOT / path), "rev-parse", "HEAD"])
        report(ok and actual == expected, f"submodule {path}", actual)
    manifest = ROOT / "config/manifests/rom_principes-explicit-animations-v2.json"
    raw = manifest.read_bytes() if manifest.is_file() else b""
    byte_hash = hashlib.sha256(raw).hexdigest() if raw else "missing"
    report(byte_hash == EXPECTED_MANIFEST_BYTES, "Principes manifest byte identity", byte_hash)
    try:
        document = json.loads(raw)
        canonical = hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    except (ValueError, TypeError):
        document, canonical = {}, "invalid"
    report(canonical == EXPECTED_MANIFEST_CANONICAL, "Principes manifest canonical identity", canonical)
    frozen = {"idle": ("sws_stand.anim", 43, 15.0), "walk": ("sws_walk_162_cm.anim", 23, 20.0),
              "attack": ("sws_sync_atk_005.anim", 27, 20.0), "death": ("sws_death_stand_004.anim", 33, 15.0)}
    semantic_ok = True
    for key, (name, frames, fps) in frozen.items():
        row = document.get("animations", {}).get(key, {})
        semantic_ok &= Path(row.get("resolved_asset", "")).name == name and row.get("frame_count") == frames and row.get("fps") == fps
    report(bool(semantic_ok), "Principes frozen clip semantics", "idle/walk/attack/death names, frames, and FPS")
    for relative, expected in RPFM_PATCHES.items():
        actual = sha(ROOT / relative) if (ROOT / relative).is_file() else "missing"
        report(actual == expected, relative, actual)
    for relative, expected in RPFM_NORMALIZED_TEXT.items():
        path = ROOT / "third_party/rpfm" / relative
        actual = normalized_text_sha(path) if path.is_file() else "missing"
        report(actual == expected, f"RPFM semantic overlay {relative}", actual)
    try:
        overlay_status = subprocess.run(
            ["git", "-C", str(ROOT / "third_party/rpfm"), "status", "--short"],
            capture_output=True, text=True, timeout=20, check=True,
        ).stdout.splitlines()
        modified_paths = {line[3:].replace("\\", "/") for line in overlay_status if len(line) >= 4}
    except (OSError, subprocess.SubprocessError):
        modified_paths = set()
    report(modified_paths == set(RPFM_NORMALIZED_TEXT), "RPFM modified path set", ", ".join(sorted(modified_paths)))
    gltf = ROOT / "third_party/rpfm/rpfm_extensions/src/gltf/mod.rs"
    if gltf.is_file():
        raw_gltf = gltf.read_bytes()
        crlf = raw_gltf.count(b"\r\n")
        lf_only = raw_gltf.count(b"\n") - crlf
        if crlf and lf_only:
            print(f"WARN live RPFM gltf source has mixed line endings ({crlf} CRLF, {lf_only} LF-only); portable state is normalized semantic text")
    for directory in (ROOT / "build", ROOT / "out"):
        report(directory.exists() and os.access(directory, os.W_OK), "writable output", str(directory))
    old = ("C:/Users/" + "sauln").casefold(); hits = []
    for path in list((ROOT / "rome2aoe2").rglob("*.py")) + list((ROOT / "scripts").rglob("*.py")):
        if old in path.read_text(encoding="utf-8-sig", errors="ignore").replace("\\", "/").casefold(): hits.append(path.relative_to(ROOT).as_posix())
    report(not hits, "portable active Python paths", ", ".join(hits) if hits else "no old-user paths")
    if args.fixtures:
        result = subprocess.run([sys.executable, str(ROOT / "scripts/verify_offline_fixtures.py")])
        report(result.returncode == 0, "offline fixtures", "see verifier output")
    print("Environment variables checked: ROME2AOE2_BLENDER (value omitted).")
    return 1 if args.strict and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
