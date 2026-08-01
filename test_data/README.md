# Test data

- `EmptyMap.aoe2scenario` is a minimal project-created AoE2 scenario fixture.
  `ScenarioGeneratorTests.GeneratesAndValidatesArbitraryUnitId` uses it as the
  template for scenario-generation verification.
- `graphics/` contains synthetic placeholder files used only to test
  unit-animation filename discovery. They are not valid SMX or SLD graphics.

The repository does not distribute game-derived AoE2 DAT files or graphics.
Ignored DAT files in this directory and local assets in the root `graphics/`
directory must be supplied from a legally obtained installation when a manual
data-mod or graphics workflow requires them.
