# Rome II effective runtime unit resolution

## Result

The installed `data_rome2.pack` DB chain is:

DB decoding used RPFM's MIT-licensed Rome II schema at commit `d12f59cb6de106d205f51b81739951adbc840c49`. Decal parameter behavior was cross-checked against The Asset Editor at commit `df28da06e4704c6025f2902873811ae391a64fb7`.

`main_units.unit -> main_units.land_unit -> land_units.key -> unit_variants.unit -> unit_variants.variant -> variants.variant_name -> variantmeshes/variantmeshdefinitions/<variant>.variantmeshdefinition`.

This resolves the benchmark identities as follows:

| Requested unit | Main/land key | Variant key | Effective root VMD |
|---|---|---|---|
| Hastati | `Rom_Hastati` | `Roman_Hastati` | `roman_hastati.variantmeshdefinition` |
| Eastern Spearman | `Eas_Spear` | `Eas_Spear` | `eas_spear.variantmeshdefinition` |
| standard Praetorian Guard | `Rom_Praetorian_Guard` | `Roman_Praetorian_Guard` | `roman_praetorian_guard.variantmeshdefinition` |

The earlier Praetorian benchmark was a different unit record: `3c_Rom_Praetorian_Guard -> 3c_Rom_Roman_Praetorian_Guard -> 3c_rom_roman_praetorian_guard.variantmeshdefinition`.

## Praetorian anatomy explanation

The standard Praetorian VMD has an empty root `legs` slot. Its `roman_game_skin` supplies exposed body geometry; `roman_segmentata` supplies `e3_tunic_cutoffA` plus `lorica_segmentata_c`. It contains no `3c_aurelian_pants` reference. This matches the observed exposed lower legs and forearms.

Every tunic branch in the separate third-century Praetorian VMD contains a trousers slot and every trousers entry uses `3c_aurelian_pants`. Consequently no mask value hides those pants. The mismatch was unit identity/campaign-family selection, not conditional visibility.

| Standard component | VMD entry | mask attributes | Runtime decision | Visible |
|---|---|---|---|---|
| skin | `roman_game_skin` -> one of five Roman skins | none | per-soldier slot choice unresolved | yes, one choice |
| tunic | `e3_tunic_cutoffA` | identity on two entries; third remaps `mask0->C2`, `mask2->C0` | per-soldier slot choice unresolved | yes |
| armour | `lorica_segmentata_c` | none | only child of selected tunic | yes |
| cloak | `roman_cloak_tint` | `mask0->C1`, `mask1->C0` | only child | yes |
| helmet | `roman_italic` | none | only child | yes |
| crest | `tall_ridge_crest_1_red` | none | only child | yes |
| shield | `roman_scutum`, three entries | identity on two; third remaps `mask0->C2`, `mask2->C0` | per-soldier slot choice unresolved | yes, one choice |
| legs | empty root slot | none | no component | no separate leg garment |

## `mask0` / `mask1` / `mask2`

These VMD attributes are not visibility booleans and are not supplied by a higher-level DB record. They remap the material's three faction-mask inputs for an individual VMD alternative. The attribute name identifies the source mask channel and its integer value identifies which faction colour input is used. Omitted attributes retain the normal channel mapping.

Examples:

- `mask0="1" mask1="0"`: source R uses C1 and source G uses C0.
- `mask0="2" mask2="0"`: source R uses C2 and source B uses C0.

The DB supplies the colour inputs, while the VMD alternative supplies any remapping. Slot alternatives and `probability` are runtime/per-soldier variation; the installed DB does not contain a fixed selected child index.

## Faction colours

Resolution precedence supported by the installed data is:

1. exact `unit_variants_colours` row for unit variant and faction;
2. faction-empty default `unit_variants_colours` row for the unit variant;
3. `faction_uniform_colours` row for the runtime faction.

For the explicit diagnostic factions:

| Unit/faction | C0 | C1 | C2 | Source |
|---|---|---|---|---|
| Hastati / `rom_rome` | `A62416` | `FFB504` | `993D24` | `faction_uniform_colours` |
| Eastern Spearman / `rom_parthia` | `855C6A` | `E4D9C7` | `382A07` | `faction_uniform_colours` |
| Praetorian / `rom_rome` | `8D0D04` | `4B103F` | `640D04` | unit-variant default |

The shader applies the already-established sequential equation. Eastern Spearmen has no single faction-independent appearance; changing the owning runtime faction legitimately changes C0/C1/C2.

## Decal arrays

The VMD selects a diffuse/normal texture-array resource and the material supplies the decal mask and transform. Neither the six traced DB tables nor RMV2 `IntParams_Decal_index` supplies a proven array slice. Asset Editor treats that integer as decal enablement. The slice is therefore recorded as `unresolved-runtime-array-index`; first-entry selection is not used as a production decision.

The same limitation remains for Roman early scutum, Praetorian scutum, Celtic shields and Hoplite shields. Evidence is consistent with per-entity variation, but the seed-to-slice mechanism has not been recovered.

## Manifest contract

`rome2aoe2.effective-unit` version 1 records the requested unit/faction, every DB row in the identity chain, resolved faction-colour source, VMD slots and alternatives, mask remaps, attachment points, decal arrays and provenance. Decisions are `deterministic`, `unresolved-runtime-random`, or `unresolved-runtime-array-index`; unknowns never silently become index zero.

The current diagnostic renders use a separately labelled representative slot seed so they can be inspected, but they are not proof of the unresolved random/decal selection.
