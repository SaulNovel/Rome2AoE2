"""Freeze and describe the corrected Hastati source used by the sprite pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frozen = args.output_dir / "corrected-hastati-sws-stand-frozen.blend"
    shutil.copy2(args.source, frozen)
    document = {
        "format": "rome2aoe2.hastati-sprite-source-freeze",
        "version": 1,
        "status": "frozen_for_sprite_production_pilot",
        "source": str(args.source),
        "frozen_scene": str(frozen),
        "sha256": sha256(frozen),
        "accepted": {
            "unit": "Hastati",
            "animation": "animations/rome2/human/battle/sword_and_shield/stand/sws_stand.anim",
            "materials": "native-textured corrected pipeline",
            "attachments": ["correct gladius", "runtime-corrected crest", "shield", "pilum"],
        },
        "policy": "render-only downstream; do not alter meshes, rig, attachments, materials, or animation",
    }
    (args.output_dir / "source-freeze.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(document, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
