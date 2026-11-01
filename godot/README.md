# Open Planet Designer — Godot import

This project imports the saved Blender development review into Godot 4.7.2 Forward+. It is a native, editable starting point for the FOSS runtime migration. The Blender source is preserved.

Godot is now the primary deployment target. The [implementation plan](../docs/GODOT_IMPLEMENTATION_PLAN.md) covers native streaming, ecosystems, photographic calibration, atmosphere/clouds, water, designer controls and standalone exports. The current project remains the frozen-import baseline for that work.

## Open and explore

Import `project.godot` in Godot and press **F5**. The first run can take time while Godot imports the models and textures. On Windows, `./launch.ps1 -Editor` finds an existing Godot Start-menu installation and opens the forest working scene; `./launch.ps1` starts the viewer.

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

Use Godot's Inspector to adjust materials, the `ImportedWorldEnvironment`, `ImportedSunDirection`, and the starting `FreeFlightCamera`. Make resources unique when changes should be specific to a location. Save the working `.tscn`. The viewer loads these working scenes, so your saved edits appear the next time that location loads. Press F5 for the free-flight viewer; the working scenes themselves are editable static imports.

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

This is **frozen Blender coverage**, not a completed native planet generator. The terrain and vegetation were evaluated at frame 240 around five saved cameras. You can fly freely through them, but moving outside their detailed coverage does not stream or generate new terrain or plants. The globe retains the exported coarse geometry elsewhere. Native procedural tile generation, background prefetch and evolving terrain LOD remain the next development stage.

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
