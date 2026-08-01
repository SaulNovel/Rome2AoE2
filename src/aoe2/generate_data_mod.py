"""Build the Crusader Knight AoE2 DE data mod from documented DAT handles."""

from __future__ import annotations

import sys
import json
import shutil
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "third_party" / "python-deps"))

from aoe2_genie_tooling import GenieWorkspace


CRUSADER_KNIGHT_NAME = "CRUSADER KNIGHT"
CRUSADER_KNIGHT_ICON_ID = 49

# The supplied SMX files are Cavalier-format animations.  These source graphic
# records provide the verified frame and facet metadata; only their filenames
# are replaced.  The Cataphract's unit record supplies the gameplay data.
GRAPHICS = (
    (1044, "u_cav_cavalier_attackA_x1.smx", "u_cav_crusader_knight_attackA_x1", "Attack"),
    (1047, "u_cav_cavalier_deathA_x1.smx", "u_cav_crusader_knight_deathA_x1", "Death"),
    (1049, "u_cav_cavalier_idleB_x1.smx", "u_cav_crusader_knight_idleB_x1", "Idle B"),
    (1050, "u_cav_cavalier_idleA_x1.smx", "u_cav_crusader_knight_idleA_x1", "Idle"),
    (1051, "u_cav_cavalier_decayA_x1.smx", "u_cav_crusader_knight_decayA_x1", "Decay"),
    (1054, "u_cav_cavalier_walkA_x1.smx", "u_cav_crusader_knight_walkA_x1", "Walk"),
)

REQUIRED_ASSETS = tuple(
    source_name.replace("_x1.smx", suffix)
    for _, source_name, _, _ in GRAPHICS
    for suffix in ("_x1.smx", "_x2.smx")
) + ("u_cav_cavalier_idleC_x1.smx", "u_cav_cavalier_idleC_x2.smx", "049_50730.dds")


def require_assets(graphics_directory: Path) -> None:
    if not graphics_directory.is_dir():
        raise NotADirectoryError(
            f"Crusader Knight graphics directory does not exist: {graphics_directory}"
        )

    missing = [name for name in REQUIRED_ASSETS
               if not (graphics_directory / name).is_file()]
    if missing:
        raise FileNotFoundError(
            "Crusader Knight graphics directory is missing: " + ", ".join(missing)
        )


def copy_assets(graphics_directory: Path, mod_directory: Path) -> None:
    graphics_output = mod_directory / "resources" / "_common" / "drs" / "graphics"
    graphics_output.mkdir(parents=True, exist_ok=True)

    for _, source_name, output_stem, _ in GRAPHICS:
        for suffix in ("_x1.smx", "_x2.smx"):
            source = graphics_directory / source_name.replace("_x1.smx", suffix)
            destination = graphics_output / (
                output_stem.replace("_x1", suffix[:-4]) + ".smx"
            )
            shutil.copy2(source, destination)

    # Idle C is included in the supplied animation set but the Cataphract
    # template uses only idle A and idle B.  Package it for a later animation
    # expansion without adding an unreferenced DAT graphic record.
    for suffix in ("_x1.smx", "_x2.smx"):
        shutil.copy2(
            graphics_directory / f"u_cav_cavalier_idleC{suffix}",
            graphics_output / f"u_cav_crusader_knight_idleC{suffix}",
        )

    icon_output = mod_directory / "widgetui" / "textures" / "ingame" / "units"
    icon_output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(graphics_directory / "049_50730.dds", icon_output / "049_50730.dds")


def generate(source_path: Path, output_path: Path, source_unit_id: int,
             target_unit_id: int, corpse_unit_id: int,
             graphics_directory: Path) -> None:
    if not source_path.is_file():
        raise FileNotFoundError(f"Source DAT file does not exist: {source_path}")

    if source_path.resolve() == output_path.resolve():
        raise ValueError("The generated DAT must not overwrite the source DAT.")

    require_assets(graphics_directory)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    workspace = GenieWorkspace.load(source_path)
    if not workspace.unit_manager.exists(source_unit_id):
        raise ValueError(f"Source unit ID does not exist: {source_unit_id}")
    if workspace.unit_manager.exists(target_unit_id):
        raise ValueError(f"Reserved unit ID is already in use: {target_unit_id}")
    if workspace.unit_manager.exists(corpse_unit_id):
        raise ValueError(f"Reserved corpse unit ID is already in use: {corpse_unit_id}")

    crusader = workspace.unit_manager.clone_into(
        dest_unit_id=target_unit_id,
        base_unit_id=source_unit_id,
        on_conflict="error",
        fill_gaps="placeholder",
    )
    corpse = workspace.unit_manager.clone_into(
        dest_unit_id=corpse_unit_id,
        base_unit_id=workspace.unit_manager.get(source_unit_id).dead_unit_id,
        on_conflict="error",
        fill_gaps="placeholder",
    )

    graphic_ids: dict[str, int] = {}
    for source_graphic_id, _, output_stem, animation_name in GRAPHICS:
        graphic = workspace.graphic_manager.copy(source_graphic_id)
        graphic.file_name = output_stem
        graphic.name = f"Crusader Knight ({animation_name})"
        graphic_ids[animation_name] = graphic.id

    crusader.name = CRUSADER_KNIGHT_NAME
    crusader.icon_id = CRUSADER_KNIGHT_ICON_ID
    crusader.attack_graphic_id = graphic_ids["Attack"]
    crusader.walking_graphic_id = graphic_ids["Walk"]
    crusader.standing_sprite_id1 = graphic_ids["Idle"]
    crusader.standing_sprite_id2 = graphic_ids["Idle B"]
    crusader.dying_sprite_id = graphic_ids["Death"]
    crusader.dead_unit_id = corpse_unit_id

    corpse.name = f"{CRUSADER_KNIGHT_NAME} CORPSE"
    corpse.standing_sprite_id1 = graphic_ids["Decay"]

    workspace.save(output_path)

    written_workspace = GenieWorkspace.load(output_path)
    if not written_workspace.unit_manager.exists(target_unit_id):
        raise RuntimeError("Generated DAT does not contain the Rome2AoE2 unit.")

    written_crusader = written_workspace.unit_manager.get(target_unit_id)
    if written_crusader.name != CRUSADER_KNIGHT_NAME:
        raise RuntimeError("Generated DAT did not preserve the Crusader Knight name.")
    if written_crusader.dead_unit_id != corpse_unit_id:
        raise RuntimeError("Generated DAT did not preserve the Crusader Knight corpse link.")

    mod_directory = output_path.parents[3]
    copy_assets(graphics_directory, mod_directory)
    (mod_directory / "info.json").write_text(
        json.dumps(
            {
                "Author": "Rome2AoE2",
                "CacheStatus": 0,
                "Description": "Adds the Crusader Knight, with Cataphract gameplay and custom graphics.",
                "Title": "Rome2AoE2 Crusader Knight",
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if len(sys.argv) != 7:
        print(
            "Usage: generate_data_mod.py <source-dat> <output-dat> "
            "<graphics-directory> <source-unit-id> <target-unit-id> <corpse-unit-id>",
            file=sys.stderr,
        )
        return 2

    generate(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        int(sys.argv[4]),
        int(sys.argv[5]),
        int(sys.argv[6]),
        Path(sys.argv[3]),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
