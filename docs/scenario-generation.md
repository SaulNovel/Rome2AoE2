# Scenario generation backend

Rome2AoE2 generates Stage 1 AoE2 DE scenarios through the locally vendored
`AoE2ScenarioParser` Python library. The C++ code calls only the project-owned
`ScenarioGenerator`; the third-party Python API is isolated in
`src/aoe2/generate_scenario.py`.

The bridge loads `test_data/EmptyMap.aoe2scenario`, places the caller-provided
AoE2 unit IDs at the requested coordinates for player one, writes the output,
then reloads it and verifies every requested unit.

## Source dependencies and local inputs

Clone with submodules, or initialize them after cloning:

```powershell
git submodule update --init --recursive
```

This obtains the pinned source dependencies at `third_party/googletest`,
`third_party/AoE2ScenarioParser`, and `third_party/rpfm`. The latter is not yet
invoked by the build, but is the planned Rome II pack-extraction dependency.

The repository does not distribute AoE2 game DAT files or game-derived graphics.
Supply your own legally obtained baseline DAT at
`test_data/empires2_x2_p1.dat`, or configure `ROME2AOE2_AOE2_DAT_PATH` to point
to a local copy. The other local DAT names ignored by Git are diagnostic inputs,
not fixtures. Supply game-derived SMX/SLD assets through a local graphics
directory, such as `graphics/`, or pass an explicit graphics directory to the
commands below. Do not add game-derived assets to the repository without a
separate provenance and redistribution review.

## Generate the demonstration scenario

After configuring CMake, build the `generate_scenario` target:

```powershell
cmake --build build --config Debug --target generate_scenario
```

The output is `build/Rome2AoE2Generated.aoe2scenario`. The demonstration unit
ID and coordinates are CMake cache values (`ROME2AOE2_DEMO_UNIT_ID`,
`ROME2AOE2_DEMO_UNIT_X`, and `ROME2AOE2_DEMO_UNIT_Y`). Copy this file to the
AoE2 DE scenario directory and open it in the in-game scenario editor to perform
the required manual validation.

The executable is also available for direct use:

```powershell
build/Debug/Rome2AoE2.exe scenario <unit-id> <x> <y> <output-scenario>
```

## Generate every converted unit

`generate-all` scans immediate subdirectories of `graphics/`. Each directory
names one custom unit and must contain filenames with all five keywords:
`attack`, `death`, `decay`, `idle`, and `walk`. Extensions do not matter. A
unit with a missing animation is reported as a warning and skipped; other units
continue processing. An empty graphics directory produces an empty scenario.

By default, `graphics/` is resolved next to the executable. Supply an explicit
directory as the final argument to override it:

```powershell
build/Debug/Rome2AoE2.exe generate-all build/ConvertedUnits.aoe2scenario 30 graphics
```

The middle value is `unitsPerPlayer` and defaults to `30`. Valid unit folders
are assigned consecutive custom IDs beginning at `10000`, in alphabetical folder
order. The scenario generator places that many instances of every valid unit
for both Player 1 and Player 2. The scenario therefore requires the matching
data mod to define those custom unit IDs before it can be opened in AoE2 DE.

This command is the production scenario-generation entry point. `UnitTests.exe`
only verifies scanning, validation, placement creation, and bridge behavior.

## Generate the matching data mod and scenario

To create both artifacts in one command, use the baseline AoE2 DE DAT as the
first argument. The generated mod folder defaults to the uppercase
`ROME2AOE2_GENERATED_DATA_MOD` beside the output scenario:

```powershell
build/Debug/Rome2AoE2.exe generate-mod-scenario test_data/empires2_x2_p1.dat build/ConvertedUnits.aoe2scenario 30 graphics
```

The data mod clones the Huskarl gameplay template for each valid unit folder,
assigns the same IDs as `generate-all`, and packages its five source animation
files. Copy `build/ROME2AOE2_GENERATED_DATA_MOD` into AoE2 DE's `mods/local`
directory and select it before opening the scenario.

## Generate the Crusader Knight mod and scenario

Copy the `empires2_x2_p1.dat` from the installed AoE2 DE version being tested
to `test_data/empires2_x2_p1.dat`. This proprietary input is intentionally
ignored by Git. Configure `ROME2AOE2_AOE2_DAT_PATH` if the local copy lives
elsewhere in the project.

Then build the pipeline target:

```powershell
cmake --build build --config Debug --target generate_pipeline
```

It writes both artifacts without changing the game installation:

- `build/Rome2AoE2DataMod/resources/_common/dat/empires2_x2_p1.dat`
- `build/Rome2AoE2Generated.aoe2scenario`

The generated mod directory also contains `info.json`, so AoE2 DE can show it
as a local mod. Copy the entire `Rome2AoE2DataMod` directory to the game's
`mods/local` directory (under your profile directory), restart or refresh the
Mod Centre, and select **Rome2AoE2 Generated Data Mod** as the data mod before
opening the scenario. Opening the scenario with the vanilla data set causes
AoE2 DE to discard the unknown unit ID.

The data-mod bridge clones the Byzantine Cataphract (unit ID `40`) into the
project-reserved unit ID `2081`, renames it **Crusader Knight**, and retains
the Cataphract's gameplay data. It creates dedicated graphics records using
the supplied Cavalier-format SMX metadata, packages the supplied `_x1` and
`_x2` SMX files in `resources/_common/drs/graphics`, and packages icon ID `49`
at `widgetui/textures/ingame/units/049_50730.dds`. A private corpse record at
unit ID `2113` uses the supplied decay animation.

`generate_pipeline` uses the configured
`ROME2AOE2_CRUSADER_KNIGHT_GRAPHICS_PATH` (by default, `graphics/`). The
direct executable form is:

```powershell
build/Debug/Rome2AoE2.exe pipeline <source-dat> <graphics-directory> <mod-directory> <x> <y> <output-scenario>
```

Select the generated data mod in AoE2 DE before opening the generated scenario
for the required in-game validation.

When the configured baseline DAT and the complete Crusader Knight SMX asset set
exist during CMake configuration, the test suite also includes a DAT round-trip
integration test. Re-run CMake after adding or changing either input.

The project-local Python dependencies are generated into
`third_party/python-deps`; this directory is intentionally ignored by Git. To
recreate it from scratch, remove that directory and run:

```powershell
python -m pip install --target third_party/python-deps -r third_party/AoE2ScenarioParser/requirements.txt
python -m pip install --target third_party/python-deps git+https://github.com/GoKuModder/aoe2-genie-tooling.git@ed299b1ac66ed79d0e597eb0b110b582ba08bfd7
```

The first command uses AoE2ScenarioParser's pinned requirements file. The
second pins the `aoe2-genie-tooling` source revision used by the data-mod
bridge. Normal dependency setup must not modify Windows ACLs; if a local
dependency tree is unreadable, regenerate it through these commands rather
than applying a repository-wide permission change.

## Licensing

The vendored backend's checked-in `LICENSE` is GPL-3.0. Its README and package
metadata still describe MIT licensing, so this dependency should be reviewed
before distributing Rome2AoE2.
