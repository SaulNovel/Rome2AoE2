# Rome II runtime render-backend feasibility

Date: 2026-08-09

## Decision

The actual Rome II renderer is the best **reference** backend and the least-cost
next visual proof, but it is not yet demonstrated to be a practical production
backend. Camera and ordinary pause/capture are available now; deterministic
animation sampling and foreground isolation are not.

Recommended next proof: make one deliberately manual, HUD-free, paused custom
battle capture of standard `roman_hastati` in sunny/dry conditions using the
existing Roma II Total War Camera Mod. Capture a useful 3/4 soldier at maximum
native/DSR resolution, without post-processing. This answers whether a clean
runtime master is materially superior before any scripting, capture injection,
camera mod, or Asset Editor adapter is built.

## Installed control

- Total War: ROME II Emperor Edition, Steam app 214950.
- Installed executable reports product/file version 2.4.0.0.
- Installed Steam manifest build ID: 11535779.
- A local `auto_save.replay` proves replay recording is active, but the format is
  opaque binary and is not an image or stable animation-frame cache.
- Official Assembly Kit DB includes `battle_cameras` (min/max height and movement
  multipliers), weather types (`dry`, `fog`, `rain`, `snow`), climate-to-weather
  mappings, weather effects, and battle cinematic event tables.

## Existing tools and workflows

### Roma II: Total War Camera Mod (Steam Workshop 188195987)

- Data mod, source and explicit reuse license not published.
- Updated for patch 15/Emperor Edition; recent March 2026 user report says it
  still works on the current game.
- Edits land, naval, campaign, and cinematic unit camera constraints.
- Claims ground-level to roughly 50-foot movement and full rotation.
- Strong fit for a manual one-frame proof and repeatable-looking viewpoints.
- Does not expose numeric camera state, programmatic capture, animation time, or
  orthographic projection.

### Consul Scriptum

- Current open-source Rome II/Attila/ToB Lua/debug console, GPL-3.0.
- Current documentation/version page reports v0.10.0 and provides Rome II
  Workshop/standalone packages.
- Executes Lua and reloadable script files inside the running game.
- Rome II battle mode exists but is explicitly experimental and enabled through
  `/use_in_battle`; it is not evidence of stable camera or entity-animation
  setters.
- Useful future probe for discovering callable battle interfaces without game
  restarts. It should not be adopted as the production controller until a tiny
  battle-state experiment proves the required bindings.

### Rome II battle Lua and extracted documentation

- The engine loads `battle_scripted.lua` when entering battle.
- Battle events and a battle manager exist, and DB/script evidence proves
  scripted battle infrastructure.
- Available public/decompiled documentation is incomplete and warns that some
  extracted names may be wrong. No proven binding was found for assigning an
  individual soldier animation clip/time or numeric battle-camera transforms.
- Engine flags expose camera limits/speeds, a debug camera type, cinematic-camera
  movement constants, entity speed modifiers intended for cinematic capture,
  and camera events. Flags prove internal capability, not a supported runtime API.

### Replays and normal game controls

- Rome II records and plays battle replays and supports ordinary pause/time-speed
  controls and HUD-free cinematic viewing.
- Replays reproduce simulation inputs/state rather than storing rendered frames.
  They are sensitive to game/mod changes and do not supply exact animation sample
  indexes. They are useful for revisiting a pose, not sufficient for deterministic
  `16 x N` production.

### RenderDoc / graphics debuggers

- Rome II uses a capturable Direct3D render path, so RenderDoc may expose color,
  depth, and intermediate targets for diagnosis.
- This is an inference from the graphics API/tool class, not a tested Rome II
  workflow. It would be intrusive, manual, build-sensitive, and unsuitable as the
  first proof. It is potentially useful later to inspect depth/material buffers.

## Capability classification

### Proven

- The actual game produces the desired Hastati material appearance.
- Custom battles can place standard Hastati with `rom_rome` faction colours.
- Battle camera limits are data-driven; the existing camera mod permits much
  closer, fully rotating cinematic-unit views.
- Normal game pause/time-speed, replay, screenshots, HUD hiding, dry-weather
  selection/data, and high display resolutions exist.
- Battle Lua is loaded and the engine contains battle scripting/cinematic systems.

### Likely, requiring one small proof

- A paused custom battle plus camera mod can produce a materially better 3/4
  high-resolution source image than Blender P5.
- DSR/DLDSR or a high-resolution virtual/display mode can increase screenshot
  pixels, subject to GPU/display availability and Rome II's resolution list.
- A minimal custom battlefield can stabilize sunlight, unit placement, and an
  uncluttered background.
- Consul Scriptum may let a live battle script control UI/state or issue stable
  unit orders, but Rome II battle support is experimental.
- RenderDoc can probably capture color/depth targets from a compatible run.

### Unknown / not proven

- Numeric camera transform/FOV setters callable from Rome II Lua.
- Orthographic battle rendering.
- A binding to force an individual animation clip and exact sample time.
- Deterministic frame stepping.
- Fixed random VMD representative selection in the game runtime.
- Native alpha/object-ID/segmentation render layers.
- Reliable unattended launch, battle load, capture, and filename control.

## Background isolation

| Method | Edge quality | Determinism | Assessment |
|---|---:|---:|---|
| Native alpha/render layer | Excellent | Unknown | No evidence it exists |
| Depth buffer via RenderDoc | Excellent hard geometry edges | Manual/build-sensitive | Best diagnostic possibility; not production-proven |
| Two known backgrounds | Potentially excellent | Requires pixel-identical scene | Best mathematical route if background can change without changing foreground lighting |
| Flat chroma battlefield | Good with careful colors | Moderate | Simple, but bronze/cloth/feathers risk spill and color collision |
| Known-background subtraction | Variable | High scene stability required | Fails around shadows/atmosphere if background-only plate is not exact |

For two-background matting, two captures obey
`C_i = alpha * F + (1-alpha) * B_i`. With identical foreground lighting and
camera, their difference estimates alpha and then foreground color. The crucial
constraint is that changing the visible background must not alter environment
lighting, exposure, fog, or reflections. Two separately lit battlefields would
not satisfy this.

Feathers, spear edges, and antialiasing favor depth or two-background matting over
a single chroma key. Ground shadow should be captured/derived separately rather
than baked into body alpha.

## Animation and camera assessment

Camera is feasible for a manual reference workflow now. The Workshop camera mod
supplies close, low, 360-degree cinematic views; a paused game supplies a stable
capture moment. It does not expose exact numeric yaw/pitch/FOV, so repeatability is
visual rather than machine deterministic.

Animation is the production blocker. Orders can induce idle/move/attack states,
pause freezes a moment, and replays revisit simulation, but no evidence establishes
clip selection plus exact per-frame sampling. External input automation would only
repeat timing heuristically and is explicitly outside this milestone.

## Capture quality

- Game screenshots are display-resolution captures; there is no discovered
  arbitrary-size offline renderer or tiled screenshot mode.
- DSR/DLDSR/custom high display resolution is the simplest supersampling route if
  available on the installed GPU/display.
- A close camera can devote most pixels to one soldier, which matters more for the
  first proof than exact projection matching.
- Rome II's perspective can be reduced with camera distance/narrower FOV if the
  camera data/mod permits it; orthographic projection is unproven.
- AA affects edges but does not explain the known material advantage and should
  remain at the user's normal high-quality game setting for the proof.

## Architecture matrix

| Backend | Visual parity | Automation | Transparency | Complexity | Biggest blocker |
|---|---|---|---|---|---|
| Actual Rome II runtime | Known best | Low/unknown for production; manual reference easy | None known; depth/two-background possible | Low for one proof, very high for `16 x N` | Exact animation/camera state and isolation |
| Asset Editor + adapter | Unproven but Total-War-aware | High after helper | Native transparent target | Medium | Exact resolved assembly plus proof of visual quality |
| Official Variant Editor | Proven poor on this installation | Low | None | Not worth pursuing | Overexposure, broken pose/environment control |
| Current Blender P5 | Known moderate | Excellent | Excellent | Already working | Source material response |
| Blender shader-parity port | Potentially high | Excellent | Excellent | Very high | Reconstructing Warscape shader/environment faithfully |

## Cost comparison and next decision gate

The manual runtime proof costs almost no renderer engineering and has the highest
chance of visual fidelity. If its close, paused capture is clearly superior and a
clean matte looks mechanically plausible, investigate only the smallest battle
state/control proof (possibly Consul Scriptum plus existing camera mod).

If runtime imagery is excellent but deterministic animation/segmentation remains
inaccessible, the next engineering choice should be the Asset Editor one-frame
adapter—not a full runtime automation system and not a Blender shader port. Asset
Editor already owns the offline primitives that Rome II runtime lacks: exact asset
assembly potential, animation sampling, orthographic camera, transparent targets,
and deterministic filenames.

## Sources

- CA Rome II Assembly Kit documentation: https://wiki.totalwar.com/w/Assembly_Kit_%28TWR2%29.html
- Roma II Total War Camera Mod: https://steamcommunity.com/workshop/filedetails/?id=188195987
- Consul Scriptum source/license: https://github.com/bukowa/ConsulScriptum
- Consul Scriptum documentation: https://consulscriptum.com/
- Extracted Rome II documentation: https://bukowa.github.io/twr2docs/
