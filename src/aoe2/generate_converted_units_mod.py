"""Create a data mod for every complete converted-unit graphics folder."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "third_party" / "python-deps"))

from aoe2_genie_tooling import GenieWorkspace

ANIMATIONS = ("attack", "death", "decay", "idle", "walk")

# Matches _x1. or _x2. (but NOT _x22.) in a filename.
# AoE2 DE appends _x1 / _x2 to a DAT file_name when resolving graphics on disk.
_ZOOM_RE = re.compile(r"_(x[12])\.", re.IGNORECASE)


def _zoom_suffix(filename: str) -> str | None:
    """Return '_x1' or '_x2' if the filename carries an AoE2 zoom marker."""
    match = _ZOOM_RE.search(filename)
    return f"_{match.group(1).lower()}" if match else None


def animation_files(directory: Path) -> dict[str, Path]:
    """Return the first file that matches each animation keyword in *directory*.

    Validation only needs to know whether each animation *exists*; the actual
    paths are used later for copying.  Any file whose name contains one of the
    five animation keywords is accepted, regardless of zoom suffix.
    """
    result: dict[str, Path] = {}
    for path in sorted(directory.iterdir()):
        if path.is_file():
            for animation in ANIMATIONS:
                if animation in path.name.lower() and animation not in result:
                    result[animation] = path
                    break
    return result


def zoom_variants(directory: Path, animation: str) -> dict[str, Path]:
    """Collect every ``_x1`` / ``_x2`` zoom file for *animation* in *directory*.

    Returns a mapping ``{"_x1": Path(...), "_x2": Path(...)}`` with whichever
    variants are present.  Files without a recognised zoom suffix are ignored.
    The first alphabetical file for each zoom level is kept (e.g. attackA before
    attackB), which keeps the selection consistent with the DAT graphic record
    that was cloned from the same-indexed template animation.
    """
    variants: dict[str, Path] = {}
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        lower_name = path.name.lower()
        if animation not in lower_name:
            continue
        zoom = _zoom_suffix(lower_name)
        if zoom is not None and zoom not in variants:
            variants[zoom] = path
    return variants


def valid_units(graphics_directory: Path) -> list[tuple[Path, dict[str, Path]]]:
    """Return every unit subdirectory that has all five required animations."""
    if not graphics_directory.is_dir():
        raise NotADirectoryError(f"Graphics directory does not exist: {graphics_directory}")
    units = []
    for path in sorted(graphics_directory.iterdir()):
        if not path.is_dir():
            continue
        files = animation_files(path)
        if len(files) == len(ANIMATIONS):
            units.append((path, files))
    return units


def unused_unit_id(workspace: GenieWorkspace, candidate: int) -> int:
    while workspace.unit_manager.exists(candidate):
        candidate += 1
    return candidate


def safe_stem(unit_name: str, animation: str) -> str:
    name = "".join(c.lower() if c.isalnum() else "_" for c in unit_name)
    return f"rome2_{name}_{animation}"


def _copy_animation_assets(
    unit_directory: Path,
    animation: str,
    stem: str,
    output_graphics: Path,
) -> None:
    """Copy zoom variants for *animation* into *output_graphics*.

    AoE2 DE resolves a graphic by appending ``_x1`` / ``_x2`` to the DAT
    ``file_name``, so output filenames must carry that suffix::

        <stem>_x1.sld   ← required
        <stem>_x2.sld   ← packaged when the source provides it

    If no ``_x1`` / ``_x2`` variants exist in the source directory (e.g. plain
    ``attack.smx`` test stubs), the raw file is copied as ``<stem>_x1<ext>``
    so the game can still find at least the standard-resolution asset.
    """
    variants = zoom_variants(unit_directory, animation)

    if variants:
        # Source has proper _x1 / _x2 files — copy each with its zoom suffix.
        for zoom_suffix, source_path in variants.items():
            dest_name = f"{stem}{zoom_suffix}{source_path.suffix.lower()}"
            shutil.copy2(source_path, output_graphics / dest_name)
    else:
        # Fallback: no zoom-tagged files found — use the first matching file
        # and package it as the _x1 asset so AoE2 DE can locate it.
        for path in sorted(unit_directory.iterdir()):
            if path.is_file() and animation in path.name.lower():
                dest_name = f"{stem}_x1{path.suffix.lower()}"
                shutil.copy2(path, output_graphics / dest_name)
                break


def generate(
    source_path: Path,
    output_path: Path,
    graphics_directory: Path,
    first_unit_id: int,
    template_unit_id: int,
) -> None:
    if not source_path.is_file():
        raise FileNotFoundError(f"Source DAT file does not exist: {source_path}")

    units = valid_units(graphics_directory)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workspace = GenieWorkspace.load(source_path)

    if not workspace.unit_manager.exists(template_unit_id):
        raise ValueError(f"Template unit ID does not exist: {template_unit_id}")

    template = workspace.unit_manager.get(template_unit_id)
    template_corpse = workspace.unit_manager.get(template.dead_unit_id)
    template_graphics = {
        "attack": template.attack_graphic_id,
        "walk": template.walking_graphic_id,
        "idle": template.standing_sprite_id1,
        "death": template.dying_sprite_id,
        "decay": template_corpse.standing_sprite_id1,
    }

    mod_directory = output_path.parents[3]
    output_graphics = mod_directory / "resources" / "_common" / "drs" / "graphics"
    output_graphics.mkdir(parents=True, exist_ok=True)

    corpse_candidate = first_unit_id + len(units)

    for index, (directory, _files) in enumerate(units):
        unit_id = first_unit_id + index
        if workspace.unit_manager.exists(unit_id):
            raise ValueError(f"Custom unit ID is already in use: {unit_id}")

        corpse_id = unused_unit_id(workspace, corpse_candidate)
        corpse_candidate = corpse_id + 1

        unit = workspace.unit_manager.clone_into(
            unit_id, template_unit_id, on_conflict="error", fill_gaps="placeholder"
        )
        corpse = workspace.unit_manager.clone_into(
            corpse_id, template.dead_unit_id, on_conflict="error", fill_gaps="placeholder"
        )

        graphic_ids: dict[str, int] = {}
        for animation, source_graphic_id in template_graphics.items():
            graphic = workspace.graphic_manager.copy(source_graphic_id)
            stem = safe_stem(directory.name, animation)
            # Store only the base stem in the DAT; AoE2 DE appends _x1 / _x2
            # at runtime to resolve the actual file on disk.
            graphic.file_name = stem
            graphic.name = f"{directory.name} ({animation.title()})"
            graphic_ids[animation] = graphic.id
            _copy_animation_assets(directory, animation, stem, output_graphics)

        unit.name = directory.name.upper()
        unit.attack_graphic_id = graphic_ids["attack"]
        unit.walking_graphic_id = graphic_ids["walk"]
        unit.standing_sprite_id1 = graphic_ids["idle"]
        unit.dying_sprite_id = graphic_ids["death"]
        unit.dead_unit_id = corpse_id

        corpse.name = f"{unit.name} CORPSE"
        corpse.standing_sprite_id1 = graphic_ids["decay"]

    workspace.save(output_path)
    (mod_directory / "info.json").write_text(
        json.dumps(
            {
                "Author": "Rome2AoE2",
                "CacheStatus": 0,
                "Description": "Generated data mod for converted Rome2AoE2 units.",
                "Title": "ROME2AOE2 GENERATED DATA MOD",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if len(sys.argv) != 6:
        print(
            "Usage: generate_converted_units_mod.py "
            "<source-dat> <output-dat> <graphics-directory> "
            "<first-unit-id> <template-unit-id>",
            file=sys.stderr,
        )
        return 2
    generate(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        Path(sys.argv[3]),
        int(sys.argv[4]),
        int(sys.argv[5]),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
