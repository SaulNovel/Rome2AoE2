"""Safe, deterministic private-fixture archive helpers (stdlib only)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "data/local-fixtures"
METADATA = ROOT / "data/fixtures/rome2-offline-fixtures.json"
ARCHIVE = ROOT / "build/private-transfer/rome2aoe2-offline-fixtures.zip"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def safe_relative(value: str) -> Path:
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise ValueError(f"unsafe fixture path: {value!r}")
    return Path(*pure.parts)


def load_metadata(path: Path = METADATA) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify(root: Path, metadata: dict, reject_unexpected: bool = True) -> list[str]:
    errors: list[str] = []
    expected = {row["path"] for row in metadata.get("files", [])}
    for row in metadata.get("files", []):
        target = root / safe_relative(row["path"])
        if not target.is_file():
            errors.append(f"missing: {row['path']}")
        elif target.stat().st_size != row["size"]:
            errors.append(f"size: {row['path']}")
        elif digest(target) != row["sha256"]:
            errors.append(f"sha256: {row['path']}")
    if reject_unexpected and root.exists():
        actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
        errors.extend(f"unexpected: {path}" for path in sorted(actual - expected))
    return errors
