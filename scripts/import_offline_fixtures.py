"""Safely import and verify a private Rome II fixture archive."""
from __future__ import annotations

import argparse
import shutil
import uuid
import zipfile
from pathlib import Path

from fixture_common import ARCHIVE, LOCAL, ROOT, load_metadata, safe_relative, verify


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", nargs="?", type=Path, default=ARCHIVE)
    parser.add_argument("--destination", type=Path, default=LOCAL)
    parser.add_argument("--replace", action="store_true", help="replace an existing ignored fixture directory")
    args = parser.parse_args()
    metadata = load_metadata()
    if args.destination.exists() and not args.replace:
        parser.error(f"destination exists; verify it or pass --replace: {args.destination}")
    temporary_root = ROOT / "build/private-transfer"
    temporary_root.mkdir(parents=True, exist_ok=True)
    staging = temporary_root / f"import-staging-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        with zipfile.ZipFile(args.archive) as archive:
            names = [i.filename for i in archive.infolist() if not i.is_dir()]
            for name in names:
                safe_relative(name)
            if len(names) != len(set(names)):
                parser.error("archive contains duplicate paths")
            archive.extractall(staging)
        errors = verify(staging, metadata)
        if errors:
            for error in errors: print(f"FAIL {error}")
            return 1
        if args.destination.exists():
            shutil.rmtree(args.destination)
        args.destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staging, args.destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    print(f"PASS imported {len(metadata['files'])} files into {args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
