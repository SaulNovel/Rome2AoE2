# Rome II converter catalog checkpoint

This checkpoint introduces the configuration front end for a data-driven
Rome II unit converter. It does not render, package, or convert another unit,
and it does not modify the approved Hastati production assets.

## Architecture

The `rome2aoe2` Python package defines typed faction, unit, component,
component-option, resolved-unit, and animation-profile models. Catalog input is
the existing effective-unit evidence produced from the Rome II DB and VMD
resolution workflow:

```text
main_units -> land_units -> unit_variants -> variantmeshdefinition
```

Factions and units are sorted before transient numeric UI IDs are assigned.
Those IDs never appear in output manifests. Component slots and alternatives
come from VMD slot paths, model references, source order, attachment sockets,
and extracted RMV2 metadata rather than unit-name conditionals.

## Commands

```powershell
python -m rome2aoe2 list-units
python -m rome2aoe2 inspect Rom_Hastati
python -m rome2aoe2 configure --output conversion-manifest.json
python -m rome2aoe2 convert conversion-manifest.json
```

Interactive component selection supports the Rome II default, `None` for
optional slots, and an explicit alternative. Required slots reject `None` and
re-prompt. The `convert` command is reserved for later orchestration and exits
with `CONVERSION_NOT_IMPLEMENTED` in this checkpoint.

## Manifest and validation boundary

Schema version 1 records exact faction, main-unit, land-unit, variant, root-VMD,
component definition/model/socket, skeleton, material-type, and animation-family
keys. It contains no UI IDs.

Configuration validation reports structured codes for missing units or
components, required omissions, incompatible sockets, skeleton mismatches,
missing source assets or textures, unsupported materials, unresolved animation
families, and the deferred conversion command. These checks are intended to
reject invalid configurations before Blender orchestration begins.

The frozen Hastati regression verifies `Rom_Hastati -> Rom_Hastati ->
Roman_Hastati`, `roman_hastati.variantmeshdefinition`, `rome_man_game`,
`rome_man_sword_shield`, and the approved body, tunic, armour, helmet, crest,
shield, gladius, and pilum source configuration.
