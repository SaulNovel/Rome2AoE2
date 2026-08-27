"""Verify the ignored local fixture set without a Rome II installation."""
from __future__ import annotations

import argparse
from pathlib import Path

from fixture_common import LOCAL, load_metadata, verify


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=LOCAL)
    args = parser.parse_args()
    metadata = load_metadata()
    errors = verify(args.root, metadata)
    if errors:
        for error in errors: print(f"FAIL {error}")
        return 1
    print(f"PASS {len(metadata['files'])} fixture files; units={','.join(metadata['units'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
