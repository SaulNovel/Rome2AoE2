"""Export a private Rome II fixture archive without changing source assets."""
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

from fixture_common import ARCHIVE, LOCAL, METADATA, ROOT, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "build/cache/rome2aoe2/assets-v1")
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--metadata", type=Path, default=METADATA)
    parser.add_argument("--principes-blend", type=Path, default=ROOT / "build/conversions/rom_principes/5ca5c13009cc208e16accc28440de3645f8d2924e8d3fd51dda0d5ad0fc4ba9f/static-unit.blend")
    args = parser.parse_args()
    source = args.source.resolve()
    if not source.is_dir():
        parser.error(f"asset cache does not exist: {source}")
    files = sorted((p for p in source.rglob("*") if p.is_file()), key=lambda p: p.relative_to(source).as_posix().casefold())
    if not files:
        parser.error("asset cache is empty")
    rows = [{"path": p.relative_to(source).as_posix(), "size": p.stat().st_size,
             "sha256": digest(p), "units": ["principes", "hastati"]} for p in files]
    if not args.principes_blend.is_file():
        parser.error(f"approved Principes smoke blend is missing: {args.principes_blend}")
    prepared_path = "_prepared/principes/static-unit.blend"
    rows.append({"path": prepared_path, "size": args.principes_blend.stat().st_size,
                 "sha256": digest(args.principes_blend), "units": ["principes"],
                 "role": "approved static assembly for offline Blender smoke only"})
    document = {
        "format": "rome2aoe2.offline-fixtures", "version": 1,
        "notice": "Private user-supplied Total War: Rome II data; never publish or commit payload files.",
        "units": {
            "principes": {"manifest": "config/manifests/rom_principes-explicit-animations-v2.json", "complete": True},
            "hastati": {"role": "frozen known-good oracle", "complete": True,
                        "note": "Copied from the existing shared validated cache; Hastati was not regenerated."},
        },
        "source_scope": "Conservative validated shared cache for Principes and Hastati; includes closure supersets where unit ownership is shared.",
        "files": rows,
    }
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if LOCAL.exists():
        shutil.rmtree(LOCAL)
    shutil.copytree(source, LOCAL)
    prepared_target = LOCAL / Path(*prepared_path.split("/"))
    prepared_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.principes_blend, prepared_target)
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for row in rows:
            data = (LOCAL / Path(*Path(row["path"]).parts)).read_bytes()
            info = zipfile.ZipInfo(row["path"], date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compresslevel=9)
    print(f"metadata={args.metadata} files={len(rows)}")
    print(f"archive={args.archive} size={args.archive.stat().st_size} sha256={digest(args.archive)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
