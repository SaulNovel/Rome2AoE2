# Rome2AoE2

> A fully automated pipeline that converts units from **Total War: Rome II** into playable **Age of Empires II: Definitive Edition** units.

---

## Vision

Rome2AoE2 aims to automate the complete process of taking an existing Rome II unit, together with its equipment, materials, textures, skeleton, and animations, and producing a playable AoE2:DE unit that can immediately be loaded into a scenario or included in a mod.

The long-term objective is for a conversion to require little more than:

```bash
rome2aoe2 convert \
    --unit "Praetorian Guard" \
    --output MyAoE2Mod
```

The tool should perform every intermediate step automatically.

Rome2AoE2 is not intended to become another Rome II asset editor or another AoE2 sprite editor.

It is an orchestration and conversion pipeline that integrates existing community tools with custom automation where no suitable tool currently exists.

---

## Project Goals

The project should:

* require minimal manual intervention
* be deterministic and reproducible
* preserve the visual identity of the original Rome II unit
* convert Rome II equipment and animations into AoE2-compatible assets
* generate production-quality AoE2 graphics
* support units with different animation lengths and frame counts
* support batch conversion of multiple units
* produce a complete AoE2 mod
* automatically generate a scenario for rapid in-game testing
* keep every pipeline stage modular and independently testable
* reuse mature community tools whenever practical
* remain extensible to other Total War titles where possible

The final workflow should allow a user to select a Rome II unit and obtain an AoE2:DE mod containing a playable equivalent with minimal additional work.

---

## High-Level Pipeline

```text
Rome II installation
        │
        ▼
Locate unit and variant definitions
        │
        ▼
Resolve VariantMeshDefinitions
        │
        ▼
Resolve meshes, textures, materials, skeletons, and animations
        │
        ▼
Extract assets from Rome II .pack archives
        │
        ▼
Import assets into Blender
        │
        ▼
Assemble the complete character
        │
        ▼
Apply Rome II animations
        │
        ▼
Render every animation and direction
        │
        ▼
Process rendered frames
        │
        ▼
Generate AoE2 SMX graphics
        │
        ▼
Generate AoE2 data-mod definitions
        │
        ▼
Generate an AoE2 scenario
        │
        ▼
Load and validate the unit in AoE2:DE
```

The intended final result is a playable unit, not merely an extracted model or a collection of rendered images.

---

## Expected Output

A successful conversion should produce:

* extracted Rome II source assets
* a resolved asset manifest
* Blender-ready model and animation data
* rendered animation frames
* AoE2-compatible SMX graphics
* an AoE2:DE data mod
* unit graphics and metadata
* an automatically generated test scenario
* validation reports and logs

The generated scenario should contain the converted unit so it can be opened quickly in the AoE2:DE Scenario Editor or launched in-game for visual verification.

---

## Core Project Principles

### Automation First

Every repeated manual operation should be considered a candidate for automation.

Examples include:

* locating Rome II unit definitions
* resolving equipment variants
* following asset references
* extracting archive files
* importing assets into Blender
* configuring cameras and lighting
* applying animations
* rendering frames
* calculating sprite anchors
* generating SMX files
* creating AoE2 mod definitions
* inserting units into scenarios
* validating generated output

Manual editing may be useful during investigation, but it should not become a permanent requirement of the final pipeline.

---

### Reuse Existing Tools

The project should build on existing community tools instead of reimplementing complex formats without a compelling reason.

Expected external tools include:

* **RPFM** for reading and extracting Rome II `.pack` archives
* **Blender** for model assembly, animation, and rendering
* **QtRME** or equivalent tools where they provide useful Rome II model-format support
* **SLX Studio** or other AoE2 tooling as a reference for sprite formats and anchor behaviour
* existing SMX or sprite libraries where suitable

Rome2AoE2 should orchestrate these tools through stable command-line or scripting interfaces whenever possible.

---

### Modular Pipeline

Each pipeline stage should have:

* clearly defined inputs
* clearly defined outputs
* explicit failure conditions
* deterministic behaviour
* independent tests
* useful diagnostics

A stage should not require the entire pipeline to be running in order to be tested.

For example, VariantMeshDefinition resolution should be testable without:

* Rome II being installed
* RPFM
* Blender
* AoE2:DE

Similarly, SMX generation should be testable using synthetic or fixture-based frame data.

---

### Deterministic Builds

Running the converter twice with identical inputs and configuration should produce identical logical output.

The implementation should not depend on:

* unspecified filesystem ordering
* unstable container iteration order
* random identifiers
* implicit locale behaviour
* environment-specific path casing
* undefined behaviour
* timestamps embedded unnecessarily in generated assets

Deterministic manifests and output ordering are preferred even when the consuming format does not require them.

---

### Preserve Source Information

The pipeline should preserve enough metadata to explain how every generated asset was produced.

Useful provenance includes:

* source unit
* source VariantMeshDefinition
* selected slot and variant
* reference chain
* source pack archive
* original pack-relative path
* selected model
* selected material
* selected animation
* render configuration
* generated frame range
* generated AoE2 graphic identifier

This information is important for debugging complex units and reproducing conversions.

---

### Thin C++ Orchestrator

The main C++ application coordinates the pipeline.

Specialized operations may be implemented using the most appropriate tool or language.

The expected architecture is:

```text
C++20 application
        │
        ├── Python helpers
        │      ├── VariantMeshDefinition resolution
        │      ├── manifest processing
        │      └── Blender scripts
        │
        ├── RPFM / rpfm_cli
        │      └── Rome II pack extraction
        │
        ├── Blender
        │      ├── scene assembly
        │      ├── animation
        │      └── rendering
        │
        ├── Sprite and SMX generation
        │
        ├── AoE2 data-mod generation
        │
        └── AoE2 scenario generation
```

C++ should not absorb specialized logic merely to keep the entire project in one language.

At the same time, new languages should only be introduced when they provide a clear architectural benefit.

---

## Application Entry Point and Pipeline Orchestration

The application entry point should remain intentionally small.

`main()` is responsible only for top-level application concerns:

* parsing command-line arguments
* loading configuration
* constructing the pipeline
* invoking the pipeline
* translating unhandled failures into process exit codes
* printing top-level diagnostics

It should not contain conversion-stage logic.

A representative structure is:

```cpp
int main(int argc, char** argv)
{
    try
    {
        const auto options = parseCommandLine(argc, argv);

        Rome2AoE2::Pipeline pipeline(options);
        pipeline.run();

        return EXIT_SUCCESS;
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
```

The ordered conversion workflow belongs in a dedicated pipeline module.

For example:

```cpp
void Pipeline::run()
{
    discoverUnit();
    resolveDependencies();
    extractAssets();
    prepareBlenderScene();
    importAnimations();
    renderAnimations();
    processFrames();
    generateSmx();
    generateDataMod();
    generateScenario();
    validateOutput();
}
```

The pipeline module is responsible for:

* invoking stages in the correct order
* passing outputs from one stage to the next
* maintaining pipeline context
* stopping execution after a fatal failure
* recording stage status
* writing logs and manifests
* supporting partial pipeline execution
* coordinating cleanup and temporary output
* eventually supporting resume and caching behaviour

Each stage should remain implemented in its own component. The pipeline should orchestrate stages, not absorb their internal logic.

### Development of Incomplete Stages

During development, not every pipeline stage will be available.

The complete intended stage sequence should still remain visible in the pipeline module.

Prefer explicit stage enablement over permanently deleting calls or scattering temporary logic through `main()`.

For example:

```cpp
struct PipelineConfiguration
{
    bool discoverUnit = true;
    bool resolveDependencies = true;
    bool extractAssets = false;
    bool prepareBlenderScene = false;
    bool importAnimations = false;
    bool renderAnimations = false;
    bool processFrames = false;
    bool generateSmx = false;
    bool generateDataMod = false;
    bool generateScenario = false;
    bool validateOutput = false;
};
```

The pipeline may then execute only enabled stages:

```cpp
void Pipeline::run()
{
    if (configuration_.discoverUnit)
        discoverUnit();

    if (configuration_.resolveDependencies)
        resolveDependencies();

    if (configuration_.extractAssets)
        extractAssets();

    if (configuration_.prepareBlenderScene)
        prepareBlenderScene();
}
```

Temporary commented-out stage calls are acceptable during very early experimentation, but the target design is explicit stage configuration.

This will later allow command-line workflows such as:

```bash
rome2aoe2 convert \
    --unit "Praetorian Guard" \
    --through-stage extract-assets
```

```bash
rome2aoe2 convert \
    --manifest build/praetorian_guard/assets.json \
    --from-stage prepare-blender-scene
```

```bash
rome2aoe2 convert \
    --unit "Praetorian Guard" \
    --only-stage resolve-dependencies
```

### Pipeline Context

Stages should exchange data through an explicit pipeline context rather than global state.

A possible structure is:

```cpp
struct PipelineContext
{
    ConversionOptions options;

    std::filesystem::path workspaceDirectory;
    std::filesystem::path outputDirectory;

    std::optional<UnitDefinition> unit;
    std::optional<DependencyManifest> dependencies;
    std::optional<ExtractionManifest> extraction;
    std::optional<RenderManifest> renders;
    std::optional<AoE2ModManifest> mod;
    std::optional<ScenarioManifest> scenario;
};
```

The exact types will evolve, but the principles are:

* stage inputs and outputs must be explicit
* global mutable state should be avoided
* stages should not rediscover information produced by earlier stages
* manifests should be persisted where useful
* pipeline state should be inspectable for diagnostics
* stages should be independently testable outside the full pipeline

### Stage Interface

As the implementation grows, pipeline stages may share a common interface:

```cpp
class IPipelineStage
{
public:
    virtual ~IPipelineStage() = default;

    virtual std::string_view name() const noexcept = 0;
    virtual void execute(PipelineContext& context) = 0;
};
```

The pipeline can then operate over an ordered collection of stages:

```cpp
void Pipeline::run()
{
    for (auto& stage : stages_)
    {
        if (!isEnabled(stage->name()))
            continue;

        stage->execute(context_);
    }
}
```

This abstraction should only be introduced when it simplifies real stage orchestration. The project should not add an inheritance framework prematurely if simple direct function calls are still sufficient.

The architectural requirements are more important than the exact implementation:

* `main()` remains small
* the complete workflow lives in a pipeline module
* stages execute in a deliberate order
* each stage remains independently implemented and testable
* unfinished stages are disabled explicitly
* stage inputs and outputs are passed through well-defined data
* the pipeline does not become a monolithic implementation module

---

## Pipeline Stages

### Stage 1 — Rome II Unit Discovery

Identify the Rome II unit selected by the user and locate its corresponding definitions.

Possible inputs include:

* internal unit key
* display name
* faction
* VariantMeshDefinition path
* manually specified root asset

The discovery stage should eventually resolve a user-facing name such as `Praetorian Guard` into the correct game data and visual definitions.

---

### Stage 2 — Variant and Dependency Resolution

Parse the selected `.variantmeshdefinition` file and determine the assets required to construct the unit.

Responsibilities include:

* parsing VariantMeshDefinition XML
* selecting variants according to configured rules
* initially supporting deterministic first-variant selection
* resolving nested `VARIANT_MESH_REFERENCE` entries
* collecting `.rigid_model_v2` references
* collecting decal and texture references
* detecting recursive cycles
* deduplicating assets
* preserving reference provenance
* producing a deterministic dependency manifest

The initial implementation uses the first applicable variant in every slot.

Future versions may support:

* explicit variant selection
* random variants with reproducible seeds
* faction-specific variants
* weighted probability selection
* generating several visual variations of one unit

---

### Stage 3 — Rome II Asset Extraction

Extract all required files from Rome II `.pack` archives.

RPFM or `rpfm_cli` should handle archive access.

Responsibilities include:

* locating Rome II pack files
* determining pack precedence
* resolving duplicate paths across packs
* extracting referenced definitions
* extracting models
* extracting textures
* extracting materials
* extracting skeleton and animation resources
* preserving pack-relative output paths
* recording which pack supplied each asset
* reporting missing dependencies clearly

The project should not implement its own pack parser unless the architecture is explicitly reconsidered.

---

### Stage 4 — Model and Material Preparation

Prepare the extracted assets for use in Blender.

Responsibilities may include:

* importing `.rigid_model_v2` models
* combining body, armour, helmet, shield, weapons, and accessories
* restoring parent-child relationships
* resolving attachment points
* assigning materials
* loading diffuse, normal, specular, gloss, mask, and decal textures
* applying faction or unit colours
* resolving scale and coordinate-system differences
* verifying mesh integrity

The assembled Blender scene should reproduce the Rome II unit as closely as practical.

---

### Stage 5 — Skeleton and Animation Processing

Import or reconstruct Rome II animation data and apply it to the assembled model.

Responsibilities include:

* resolving the correct skeleton
* importing Rome II animation clips
* mapping animation names to AoE2 actions
* handling weapon and shield attachments
* handling animations with different frame counts
* preserving animation timing
* supporting looping and non-looping actions
* detecting missing bones or incompatible meshes
* defining fallback behaviour when a direct animation mapping does not exist

Animation frame counts must not be assumed to be identical across actions.

A walk animation, attack animation, death animation, and idle animation may all contain different numbers of frames.

---

### Stage 6 — Blender Automation and Rendering

Execute Blender non-interactively from the command line.

Responsibilities include:

* generating or loading a Blender scene
* importing all required assets
* configuring materials
* applying the selected animation
* configuring the orthographic camera
* configuring lighting
* rotating the unit for AoE2 directions
* rendering every animation frame
* using consistent resolution and scale
* applying transparency
* writing render metadata
* exiting with a meaningful status code

The Blender stage should be reproducible and require no manual interaction.

Before bulk sprite rendering, the pipeline uses the versioned AoE2 DE infantry
render-calibration profile documented in
[`docs/RESEARCH/AOE2_DE_RENDER_CALIBRATION.md`](docs/RESEARCH/AOE2_DE_RENDER_CALIBRATION.md).
It fixes an orthographic camera, stable feet anchor/canvas, direction policy,
lighting, transparent color output, and a separate shadow pass. Calibration is
kept distinct from future source-sample rendering and SMX encoding.

The textured-unit calibration is versioned separately as
`config/render_profiles/aoe2_de_infantry_v2.json`. It preserves the v1 camera
geometry, renders Cycles internally at 4x resolution, and performs deterministic
premultiplied-alpha bicubic reduction to the stable 200x200 canvas. Canonical
geometry, materials, equipment and source animation samples are not reduced or
mutated by this output-only stage.

---

### Stage 7 — Frame Processing

Convert raw Blender renders into frames suitable for AoE2 graphics.

Responsibilities include:

* cropping transparent space
* preserving a consistent anchor point
* calculating unit-foot position
* calculating per-frame offsets
* handling shadows
* handling player-colour masks
* handling outlines where required
* validating dimensions
* detecting empty or clipped frames
* preserving animation direction and frame order

Frame processing should support variable frame counts per animation.

---

### Stage 8 — AoE2 SMX Generation

Generate SMX graphics compatible with Age of Empires II: Definitive Edition.

Responsibilities include:

* encoding rendered frames
* creating direction groups
* assigning per-frame offsets
* handling transparency
* handling player colours
* handling shadows
* handling outlines if required
* preserving different frame counts per animation
* producing deterministic SMX output
* validating generated files against known working SMX examples

The implementation must not assume that every animation contains the same number of frames.

---

### Stage 9 — AoE2 Data-Mod Generation

Create or update the AoE2 data required for the converted unit.

Responsibilities include:

* creating a new unit definition
* assigning graphic IDs
* assigning unit IDs
* configuring standing, walking, attacking, dying, and decay graphics
* defining animation timing
* configuring movement and combat properties
* assigning sounds where available
* avoiding collisions with existing IDs
* producing a valid AoE2:DE data mod directory

The generated unit should be minimally playable even before advanced balancing or sound integration is complete.

---

### Stage 10 — AoE2 Scenario Generation

Create a scenario containing the generated unit.

Responsibilities include:

* loading or generating an AoE2 scenario
* placing the generated unit
* optionally placing a known vanilla comparison unit
* selecting suitable terrain
* setting players and diplomacy
* using the generated data mod
* saving the scenario to the correct output location

The scenario exists primarily to shorten the test cycle.

A typical diagnostic scenario may contain:

* one vanilla reference unit
* one generated Rome2AoE2 unit
* enough space to inspect standing, movement, attack, and death animations

---

### Stage 11 — Validation

Validate the output at multiple levels.

Validation should include:

* manifest validation
* extracted-file validation
* Blender import validation
* render validation
* SMX structural validation
* AoE2 data validation
* scenario validation
* optional in-game visual verification

Validation failures should identify the responsible stage and provide actionable diagnostics.

---

## Manifest-Driven Design

Pipeline stages should communicate through explicit manifests where practical.

A manifest may contain:

```json
{
  "unit": "praetorian_guard",
  "source_definition": "variantmeshes/variantmeshdefinitions/praetorian_guard.variantmeshdefinition",
  "models": [],
  "textures": [],
  "materials": [],
  "animations": [],
  "render_jobs": [],
  "aoe2_graphics": []
}
```

The exact schema will evolve, but manifests should remain:

* machine-readable
* deterministic
* versioned
* inspectable by humans
* suitable for caching
* suitable for debugging

Avoid passing important state only through temporary filenames or implicit directory conventions.

---

## Error Handling

The pipeline should fail clearly and as early as practical.

Errors should include enough context to diagnose the problem.

Examples:

* missing VariantMeshDefinition
* recursive reference cycle
* missing pack archive
* missing model
* unresolved texture
* unsupported model version
* Blender import failure
* skeleton mismatch
* empty render
* invalid SMX
* duplicate AoE2 ID
* scenario generation failure

Errors should report:

* pipeline stage
* affected source file
* original pack-relative path
* relevant reference chain
* external command
* exit code
* log location

Warnings should be used when a fallback is possible.

---

## Testing Strategy

### Unit Tests

Unit tests should cover isolated logic such as:

* binary reading
* path normalization
* VariantMeshDefinition parsing
* first-variant selection
* recursive reference resolution
* cycle detection
* manifest generation
* frame ordering
* anchor calculations
* SMX structure generation
* AoE2 scenario serialization

Unit tests should use local fixtures and should not depend on a game installation.

---

### Integration Tests

Integration tests may cover:

* RPFM extraction from small test packs
* Blender command-line execution
* Blender model import
* render generation
* SMX generation
* AoE2 mod-directory generation
* scenario generation

External-tool integration tests should be clearly separated from fast local unit tests.

---

### End-to-End Tests

An end-to-end test should eventually perform:

```text
Rome II unit
    → dependency manifest
    → extracted assets
    → Blender scene
    → rendered animation
    → SMX
    → AoE2 mod
    → AoE2 scenario
```

The Praetorian Guard is currently the primary reference unit for the Rome II asset extraction and assembly stages.

---

## Non-Goals

Unless explicitly requested, contributors should NOT:

* implement a custom Rome II `.pack` parser
* replace RPFM
* replace Blender
* replace QtRME
* rewrite working modules for stylistic reasons
* merge independent pipeline stages into one monolithic component
* introduce new languages or build systems without a clear architectural benefit
* sacrifice determinism for small performance gains
* remove tests to make builds pass

Architectural changes should preserve the modular pipeline design and be justified with measurable benefits.

---

## Development Rules for Automated Coding Agents

Before implementing a task, Codex or another coding agent should:

1. Read this README completely.
2. Inspect the relevant existing code and tests.
3. Read the documentation for the affected pipeline stage.
4. Identify the files it intends to modify.
5. Preserve existing working behaviour.
6. Avoid broad refactoring unrelated to the requested task.
7. Add or update automated tests.
8. Report assumptions explicitly.
9. Report unrelated test failures separately.
10. Avoid starting a later pipeline stage before the current stage has a testable interface.

The coding agent should not treat a partial stage implementation as completion of the overall project.

For example:

* parsing VariantMeshDefinitions does not complete Rome II extraction
* extracting models does not complete unit assembly
* rendering PNG files does not complete SMX generation
* generating an SMX does not complete AoE2 mod integration
* generating a mod does not complete in-game validation

Every task should be understood in the context of the complete Rome II-to-AoE2 conversion pipeline.

---

## Current Project Status

### Completed or Partially Completed

* C++20 and CMake project structure
* `BinaryReader`
* AoE2 scenario parsing
* AoE2 scenario generation
* AoE2 mod generation
* insertion of generated units into test scenarios
* diagnostic scenario generation
* initial SMX and custom-unit loading investigation
* VariantMeshDefinition format investigation
* RPFM architecture investigation
* initial first-variant VariantMeshDefinition resolver
* deterministic JSON dependency manifest generation
* CTest integration for the Python resolver

### Current Active Work

* recursive VariantMeshDefinition reference resolution
* cycle detection
* missing-definition diagnostics
* dependency provenance
* Rome II pack extraction design and integration

### Major Remaining Work

* complete RPFM extraction integration
* Rome II material and texture resolution
* skeleton and animation extraction
* Blender import automation
* Rome II character assembly
* command-line animation rendering
* frame processing
* anchor calculation
* SMX generation for variable-length animations
* AoE2 graphic registration
* complete mod generation
* complete scenario generation
* end-to-end validation

---

## Proposed Repository Documentation

As the project grows, documentation should be divided as follows:

```text
README.md
docs/
├── PROJECT.md
├── ROADMAP.md
├── PIPELINE.md
├── ARCHITECTURE.md
├── CURRENT_TASK.md
├── DECISIONS.md
└── RESEARCH/
    ├── RomeII.md
    ├── VariantMeshDefinition.md
    ├── RPFM.md
    ├── Blender.md
    ├── AoE2.md
    └── SMX.md
```

### `README.md`

Provides:

* project vision
* high-level pipeline
* project principles
* current status
* basic build and usage instructions
* links to detailed documentation

### `docs/PROJECT.md`

Provides a more detailed product definition, scope, expected user workflow, and success criteria.

### `docs/ROADMAP.md`

Tracks milestones and implementation progress.

### `docs/PIPELINE.md`

Documents every pipeline stage, including inputs, outputs, and failure conditions.

### `docs/ARCHITECTURE.md`

Documents components, interfaces, dependencies, process boundaries, and data flow.

### `docs/CURRENT_TASK.md`

Describes the currently active implementation stage and its acceptance criteria.

### `docs/DECISIONS.md`

Records important architectural decisions and their rationale.

Examples include:

* using RPFM instead of a custom pack parser
* using Blender as an external process
* allowing Python helper scripts
* keeping C++ as the primary orchestrator
* using manifest-driven stage boundaries

### `docs/RESEARCH/`

Stores investigations, reverse-engineering notes, format analysis, external-tool evaluations, and experiments.

---

## Long-Term Command-Line Interface

The desired interface may eventually resemble:

```bash
rome2aoe2 convert \
    --unit "Praetorian Guard" \
    --output MyAoE2Mod
```

Additional commands may include:

```bash
rome2aoe2 resolve \
    --unit "Praetorian Guard"
```

```bash
rome2aoe2 extract \
    --manifest build/praetorian_guard/assets.json
```

```bash
rome2aoe2 render \
    --manifest build/praetorian_guard/render.json
```

```bash
rome2aoe2 build-mod \
    --unit praetorian_guard \
    --output MyAoE2Mod
```

```bash
rome2aoe2 generate-scenario \
    --mod MyAoE2Mod \
    --unit praetorian_guard
```

```bash
rome2aoe2 batch \
    --faction Rome \
    --output RomanUnits
```

The exact command-line structure is not final, but the interface should support running stages independently for development and debugging.

---

## Definition of Success

The project reaches its primary goal when a user can:

1. select a Rome II unit
2. execute one conversion command
3. receive a generated AoE2:DE mod
4. open the generated scenario
5. see the converted unit in-game
6. observe its standing, walking, attacking, and dying animations
7. repeat the process deterministically for other Rome II units

The result should require no manual Blender editing, no manual SMX construction, and no manual scenario modification during the normal conversion workflow.

---

## Long-Term Vision

Rome2AoE2 should become a robust open-source conversion framework capable of transforming large collections of Rome II units into playable AoE2:DE content.

The architecture should remain general enough to support:

* multiple units
* multiple visual variants
* different animation frame counts
* batch faction conversion
* configurable rendering styles
* additional Total War source games
* reusable output stages for other sprite-based games

The immediate focus remains Rome II to AoE2:DE, but the project should avoid unnecessary assumptions that prevent future extension.
