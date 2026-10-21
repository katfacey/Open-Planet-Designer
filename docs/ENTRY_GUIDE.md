# Open Planet Designer 1.1 — atmospheric entry and camera detail

The generator now supports orbit-to-low-altitude views with bounded camera-adaptive geometry and smooth distance fades for added terrain detail. Resolution is finite: Blender precision, the refinement limit and the triangle budget still apply.

## Start

Open `output/planets/entry/Open_Planet_Atmospheric_Entry.blend` with version 1.1 enabled. Scrub **frames 1–240** to descend from orbit, through the atmosphere and cloud altitude, to above inland terrain. Select a planet layer and open **N → Open Planet → Camera Detail & Entry**.

For an existing version 1.0 planet, choose a camera and click **Upgrade / Rebuild Entry Materials** once. This preserves the controller and keyframes while replacing its owned material/displacement graphs. **New Atmospheric Entry Shot** creates a separate demo scene. The original orbital library and city project are retained.

## Controls

| Control | Effect |
|---|---|
| Camera adaptive detail | Enables camera-driven topology and entry/detail shaders. Off freezes the last topology; Restore Uniform Meshes returns to regular meshes. |
| Live camera updates | Debounced updates when the chosen camera moves. Frame changes and renders also refresh. |
| Fit camera clipping to planet | Adjusts clipping as the camera moves. Turn off for manually managed clipping or foreground props. |
| Triangle budget | Cap for the generator's terrain, clouds, atmosphere, rings and core, before any additional user modifiers. |
| Target edge pixels | Desired projected near-camera cell size. Smaller values request more detail. |
| Full detail distance / radius | Full local displacement and material detail within this camera distance. |
| Detail fade distance / radius | Added detail fades smoothly to zero by this distance; geometry also becomes progressively coarser. |
| Maximum refinement depth | Limits subdivision of each cube-sphere face; capped at 20. |
| Local terrain height / radius | Added close-range geometric relief. |
| Local terrain frequency | Higher values generate smaller terrain features. |
| Local normal detail | Close-range material detail strength. |
| Local crevice shading | Inexpensive procedural contrast, not ray-traced ambient occlusion. |

Distances and heights are fractions of the planet radius. The panel also displays near/far distances in scene units. For an Earth-sized interpretation, `0.001 × radius` represents approximately 6.37 km regardless of the Blender-unit scale.

**Budget limited** means the cap is respected but the desired pixel target is unmet. Increase the cap or target pixel size, or shorten the detail distance. The demonstration uses a 60,000-triangle cap; caps of 2,048 and 12,000 are also tested.

## How it works

Six cube faces project onto a sphere. A deterministic best-first quadtree refines cells according to camera distance, projection, the near/far settings, view direction and available triangles. The globe remains complete: hidden regions stay coarse rather than being deleted. Fine-edge vertices are included in neighbouring coarse cells' triangle fans, including across cube-face boundaries, avoiding T-junction cracks. It never builds a giant full-resolution globe and then decimates it.

Python generates the bounded topology; the same Geometry Nodes graph displaces it for both engines. Faceless service meshes sample that exact displacement at the camera's radial footpoint to estimate local surface height. Terrain detail and shader octaves use a smooth distance ramp.

The atmosphere integrates exponential density over eight midpoint samples along a clipped camera ray. Surface aerial perspective handles ground views from inside; the sphere's far boundary supplies interior sky. Scattering phase and illumination remain visual approximations. Cloud undersides are visible from below, and close shell crossings fade. Clouds remain displaced translucent shells, not volumetric interiors.

## Limits and performance

- This provides bounded orbit-to-surface scalability, not literal infinite resolution or a floating-origin planetary simulation. Numeric precision, clipping and refinement depth limit extreme close-ups and distances.
- Topology changes discretely. Detail fades continuously, but this is not a fully geomorphed terrain engine; fast motion or severe budget limits can expose refinement changes. Revisiting a frame produces the same mesh.
- The triangle cap is not a total GPU-memory cap. Shader complexity, transparency, samples, image resolution, other objects and extra modifiers still affect cost. Fading a contribution does not eliminate every shader calculation.
- Rebuilds cost CPU time; 60 fps navigation is not promised. The main development machine is an i9-14900K with an RTX 5090; its timings are not promises for consumer hardware.
- A lower-end GPU benchmark could not be run: this Blender runtime detects only the RTX 5090. Geometry-budget verification is independent of that GPU's speed.
- Use the configured scene/LOD camera. Arbitrary free-view viewport movement does not change that target.
- Keep the controller and full collection when transferring a planet. The enabled add-on is required for automatic camera/frame-driven topology updates. Do not edit the generated adaptive mesh expecting edits to survive rebuilding.
- Entry mode enables Blender's render interface lock to protect geometry updates while rendering.
- The demo camera's clearance is checked at all 240 integer frames. Other paths still need to avoid the terrain; no collision solver is included.
- Ordinary scene lights, shadows from unrelated geometry, physical multiple scattering, centimetre-scale ground assets, stereo/multiview and subframe motion-blur consistency are not validated targets.

## Research

[NVIDIA's geometry-clipmap chapter](https://developer.nvidia.com/gpugems/gpugems2/part-i-geometric-complexity/chapter-2-terrain-rendering-using-gpu-based-geometry) describes concentrating terrain resolution near an observer and transitioning between resolutions. This implementation uses that bounded-detail principle with a stitched cube-sphere quadtree, rather than GPU texture clipmaps, to deliver the same actual mesh to both Blender engines.

[Sean O'Neil's atmosphere chapter](https://developer.nvidia.com/gpugems/gpugems2/part-ii-shading-lighting-and-shadows/chapter-16-accurate-atmospheric-scattering) explains starting the integration at the camera when it is inside the atmosphere. That informed the clipped ray interval here; this shader is a simplified visual model rather than the chapter's complete physical algorithm.

[Blender's Eevee limitations](https://docs.blender.org/manual/en/latest/render/eevee/limitations/limitations.html) describe volumetric and precision constraints. A shared analytic sky/haze model and bounded actual geometry retain the project's engine-consistency approach without assuming native volumetrics match.

## Tests and artifacts

The five delivered 960 × 540 comparison pairs have mean visible RGB differences of **0.010–0.375%** between Eevee and Cycles. These are averages over visible pixels and channels in display-space PNGs, not maximum per-pixel differences. The camera moves from three radii above the surface to approximately **0.000035 radii** above terrain (about 223 m with an Earth-sized interpretation). The sampled views use **33,506–42,886 triangles** under the 60,000 cap. CPU topology updates took approximately **213–288 ms** on the development machine.

- `tests/test_planet_lod.py`: watertight edges, winding, cube seams/corners, deterministic output, budgets, near refinement and orthographic projection.
- `tests/blender_entry.py`: random-order scrubbing, positive sampled camera clearance, material preservation, three budget caps, uniform restoration, legacy upgrade, core/ring budget handling.
- `tools/check_entry_path.py` and `output/planets/entry/entry_path_check.json`: all 240 integer frames clear the terrain and respect the cap; maximum 42,886 triangles.
- `output/planets/entry/entry_verification.json`: counts, depth, clearance, update/render timings for the supplied shot.
- `output/planets/entry/entry_metrics.json`: saved PNG image differences for five Eevee/Cycles pairs. These measure display-space RGB, not physical radiance.
- `output/planets/entry/entry_comparison.jpg`: Eevee on the top row, Cycles on the bottom.

Rebuild with `blender --background --factory-startup --python tools/build_entry_demo.py`. Both engines use the same camera, geometry and color management. The test renderer uses 256 Eevee samples and 128 Cycles samples, with Cycles adaptive sampling and denoising off.
