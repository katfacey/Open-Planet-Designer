# Open Planet Designer — Godot visual development

**0.2.0-alpha.2 opens the Earth Woodland Study.** See the [visual guide](../docs/EARTH_WOODLAND_LOOK.md) for the natural-daylight direction, CC0 assets, fixed-detail scope and controls. Press F2 or **Explore native planet** for the streamer. Use `launch.ps1 -Native` to run it directly. The study and native planet have different layouts; matching appearance throughout the planet remains work. The original five imported scenes remain a reference mode in the full checkout.

Godot is the primary deployment target. The [implementation plan](../docs/GODOT_IMPLEMENTATION_PLAN.md) covers the remaining photographic calibration, temporal LOD, atmosphere/clouds, water, designer controls and qualified releases. The native alpha and the preserved Blender reference have different generators/placements; photographic matching is not claimed.

Press **F5** or run `launch.ps1` for the study. Hold RMB to look, use WASD/E/Q to fly, Shift to boost and the wheel to change speed. Home resets the reference view; H hides the interface. In native mode, **Detail budgets** controls LOD and geometry limits, location buttons select regions, and F8 saves profiling data. Edit `default_planet.tres` to persist planet settings or `earth_woodland.tres` for appearance. The exported app needs its `.pck` beside the executable.

The sections below describe the preserved **frozen import reference**, available with F1 in the full project or `launch.ps1 -Review`. The smaller native source/runtime packages omit that optional reference content.

## Open and explore

Run `main.tscn` directly, press F1 from native mode, or use `launch.ps1 -Review`. On Windows, `launch.ps1 -Editor -Review` opens the forest working scene. The first editor import can take time while Godot processes models/textures. Press F1 in the reference viewer to return to native mode.

- Hold **right mouse** and move the mouse to look; **WASD** moves along the camera.
- **E / Q** moves up/down; **Shift** boosts speed; the **wheel** changes speed.
- **1–5** or the location buttons select Forest, Grassland, Alpine, Desert and Ocean.
- **Home** returns to the original Blender viewpoint. **O** shows a coarse globe geometry preview. Planetary atmosphere/space appearance is still pending.
- **V** toggles vegetation; **H** toggles the interface; **Esc** releases the mouse.
- **Trees (m)** and **Ground cover (m)** change visibility distances within the exported population. They do not generate new vegetation beyond it.

Vegetation visibility and range settings remain applied when switching locations.

There is no collision or terrain-following controller yet. This is free flight.

## Refine the imported scenes

Open the working scenes under `scenes/`. These inherit the generated native `.scn` scenes under `assets/generated/`; they contain real terrain MeshInstance3D nodes and spatial MultiMesh batches, plus the original camera pose and Sun direction.

Use Godot's Inspector to adjust materials, the `ImportedWorldEnvironment`, `ImportedSunDirection`, and the starting `FreeFlightCamera`. Make resources unique when changes should be specific to a location. Save the working `.tscn`. The reference viewer loads these working scenes, so edits appear the next time that location loads. F5 starts native mode; use F1 or run `main.tscn` for the reference viewer. The working scenes themselves are editable static imports.

Native terrain/plant nodes are grouped for efficient rendering. Individual vegetation transforms live in MultiMesh resources rather than thousands of separately editable object nodes.

## What transferred

- All five authored review locations, each with approximately 500,000 evaluated terrain triangles, including the measured mountain/canyon regions and displaced water snapshot.
- 42 shared prepared models/LOD variants, including scanned trees, saplings, dead wood, grass, ferns and rocks, with glTF PBR textures, UVs and normals.
- Exact exported instance counts, stable IDs, sizes and rotations. Models remain shared GPU instances.
- Original terrain biome attributes, reused by a native ground shader with the four existing CC0 ground scans at 2K resolution.
- Camera orientation/FOV, physical scale in metres, and Sun orientation.
- Source-selected model LOD near the camera, with cheaper prepared representations and distance culling farther away. Spatial batches make these transitions approximate at cell boundaries.

The importer restores Blender material-slot indices on export copies, removes aerial-perspective shader wrappers from those copies, corrects legacy crown normal maps, and explicitly preserves procedural grass vertex colors in Godot. It excludes the unrelated default Blender scene.

## Current limits

This reference mode is **frozen Blender coverage**. The terrain and vegetation were evaluated at frame 240 around five saved cameras. Moving outside their detailed coverage does not generate new detail in reference mode. Switch back to native mode for the new streaming generator, whose separate limitations are recorded in the native guide.

Blender shader graphs do not transfer directly. Ground layering is reimplemented from the same scans and biome attributes; Godot's sky/lighting is a first approximation. The original spherical clear-air shader, cloud shell, ocean optical shading and water-time animation are not ported. The imported waves are static geometry. Photographic approval and matching Blender renders are open.

Rendering uses camera-relative rebasing and an altitude-aware far/near clip ratio. This avoids the initial collapsed planetary projection/culling problem while retaining local camera precision. It is not yet a general planetary physics/coordinate system.

## Rebuild

From the repository root, with the complete Blender runtime assets available:

```text
blender --background --factory-startup --python-exit-code 1 --python tools/export_godot.py -- --source PATH_TO_PACKED_REVIEW.blend
python tools/validate_godot_export.py --source PATH_TO_PACKED_REVIEW.blend
godot --headless --path godot --editor --import --quit
```

`tools/check_godot_import.ps1` creates the editable native scene snapshots and runs Vulkan checks. `-Reload` checks loading them through the working scenes. Supply `-GodotPath` if the local default is different. The exporter never saves over the Blender source.

Generated assets and Godot's import cache are excluded from Git. The local prototype ZIP includes the generated assets; an automatic GitHub source ZIP does not. Re-exporting raw geometry does not replace the editable snapshots until the snapshot check is rerun. Back up your working scenes before rebuilding after significant geometry changes.

## Licensing and AI disclosure

Project code and original materials use GPL-3.0-or-later. Godot is MIT-licensed. Source scans are CC0 and USGS elevation is public domain; see the repository's `THIRD_PARTY_NOTICES.md`. This project was developed with substantial AI assistance; see `AI_DISCLOSURE.md`. No paid or proprietary-engine assets were introduced for this import.

The packaged project includes the original asset-credit and processing manifests under `source-credits/`.
