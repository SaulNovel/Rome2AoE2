# Rome II full catalog checkpoint

This milestone replaces experiment-driven roster discovery with an authoritative,
derived source index. It does not implement conversion or rendering.

## Data flow

`data_rome2.pack` DB tables and `local_en.pack` localization are indexed first.
The index joins `main_units`, `land_units`, `unit_variants`, faction military
group permissions, and exclusive faction permissions. Model pack directories are
scanned only to identify the owning pack for each root VMD. Existing extracted
effective-unit evidence is an optional dependency-validation overlay; it can
promote an indexed unit to `READY`, but it cannot add units to the roster.

The versioned derived cache is
`build/cache/rome2aoe2/catalog-v1.json`. It records source pack sizes, schema
identity, DB/localization provenance, VMD paths, and model-pack ownership. Rebuild
it deterministically with:

```powershell
python -B -m rome2aoe2 catalog rebuild
```

Metadata indexing extracts only DB/LOC records. RMV2, texture, and animation
dependency extraction remains a selected-unit operation for a later milestone.

## Selection and inspection

Factions and their units use deterministic display-name/key ordering. Unit
numeric IDs restart within each faction and never enter manifests. Stable faction
and unit keys are also accepted.

```powershell
python -B -m rome2aoe2 list-units --faction rom_rome
python -B -m rome2aoe2 inspect Rom_Hastati --faction rom_rome --verbose
python -B -m rome2aoe2 configure
```

Display text falls back from localized name to authoritative source name to the
stable DB key. Descriptions are emitted only when an authoritative localization
record exists.

## Convertibility

- `READY`: indexed and validated by available selected-unit dependency evidence.
- `PARTIAL`: indexed, but selected dependencies or a supported capability remain
  unvalidated or missing.
- `UNSUPPORTED`: outside the currently supported infantry architecture.

Reason codes remain structured (`MISSING_REQUIRED_ASSET`, `UNRESOLVED_VMD`,
`UNRESOLVED_ANIMATION_FAMILY`, `UNSUPPORTED_SKELETON`, and
`UNSUPPORTED_UNIT_CLASS`). Merely having a DB record never makes a unit `READY`.

The frozen Hastati effective evidence remains an overlay and preserves its exact
DB/VMD, component/socket, skeleton, and animation-family resolution.
