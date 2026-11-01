# Godot implementation plan

**Decision date: 1 November 2026. Status: approved platform direction; implementation milestones below remain proposed unless marked complete.**

Godot is now the primary runtime and deployment target for Open Planet Designer. Develop the explorable planet and its authoring controls there. Preserve Blender as an optional source of meshes, scans, asset baking and diagnostic references. A deployed planet must run without Blender, Python, the Blender MCP server or a C# installation.

The product goal remains photographic terrain and ecosystems that retain their identity from orbit to ground level, with real foreground geometry and user-controlled detail budgets. “Continuous zoom” means refining available/generated detail down to a declared minimum feature size within bounded memory. It does not mean unlimited measured resolution or an unlimited resident mesh.

This document supersedes the **future implementation sequence** in the [expanded Blender discussion](EXPANDED_DISCUSSION.md). That document and the development reports remain the record of research, completed experiments and known failures. No new visual or performance milestone is claimed by this plan.

**Implementation update — 0.2.0-alpha.1:** the first native foundation is now implemented: profiling/replay and Windows export; scalar-precision coordinates and canonical regional/procedural data; bounded stitched terrain generation; and deterministic ecosystem streaming with per-instance LOD and budgets. See [implementation details, verification and remaining limits](GODOT_NATIVE_DEVELOPMENT.md). The complete photographic, temporal and hardware exit gates below remain separate qualifications.

Completed parts of the next batch: ~~route replay/profiling and test export~~; ~~canonical coordinates, physical altitude and height/mask providers~~; ~~first bounded terrain streaming region with coarse fallback~~; ~~native ecology cells, nearby LOD upgrades and budget controls~~. Velocity-aware prefetch, full temporal/HLOD appearance, texture/raster paging, photographic approval and target-hardware qualification remain open.

## 1. Starting point and changes in direction

Baseline: `godot-import` at `2d8e85c`, the [first Godot import](GODOT_IMPORT.md). The local 0.1 project package is a migration prototype, not an exported standalone application.

| Work inherited from Blender | Established result | Godot disposition |
| --- | --- | --- |
| Real terrain displacement | Five frozen review locations, roughly 500,000 terrain triangles each, import successfully | Retain as fixtures; replace camera-specific snapshots with native terrain providers and streamed meshes |
| Measured regional landforms | One 20 km Rainier region and one 10 km canyon region; physical heights and provenance retained | Convert their source height data into native tile pyramids; preserve footprints, datum offsets and finite resolution |
| More varied vegetation and stable placement | Mature/young/dead forms; 42 prepared model/LOD variants; exported IDs and transforms | Keep accepted assets and reference fixtures; generate complete candidate populations per native ecology cell |
| Physical grass size and source-derived distant plants | Structural corrections implemented; seamless motion and photographic quality remain open | Carry forward; rebuild HLOD, contact handling and transitions for movement in Godot |
| Ground scan layers | Four aligned CC0 scans; a basic Godot substrate blend already exists | Improve masks, scale, projection, repetition and real close geometry |
| Daylight and indirect illumination | Matched Blender sun/sky and finite static captures; dense foliage remains difficult | Establish one Godot sun/sky and qualify a native indirect-light strategy for streaming |
| Crown normal repair | Inward legacy atlas normals corrected; Godot grass vertex tint/material slots retained | Keep these asset fixes; regenerate empty/poor atlas views and improve directional crown shading |
| Alpha-aware Eevee capture and raised probe-floor experiment | Bake-only support trimming worked; raised floor regressed the forest and is off | Keep historical findings; the Eevee-specific bake workaround is outside the Godot runtime plan |
| Clear-air entry | Spherical prototype exists in Blender; washed-out land and full transport remain unresolved | Reimplement shared sky/terrain atmospheric transport in Godot and validate land contrast and lighting |
| Ocean | Displaced wave geometry imported at frame 240 | Replace the static snapshot with world-anchored animated waves and a native optical surface |
| Engine matching | Eevee/Cycles still differ, especially in canopy illumination | Retire parity as a release gate. Use Godot motion/quality gates and photographic references; occasional offline references remain optional |
| Demo and deployment | Released Blender 1.3 beta; bounded cached descent; Godot source/project ZIP | Keep releases identifiable. Future interactive releases are exported Godot applications with their source and asset manifests |

The [daylight report](DAYLIGHT_GROUND_DEVELOPMENT.md) and [foliage report](FOLIAGE_DEVELOPMENT.md) explain why their broader priorities remain open. Previously struck-through structural fixes stay completed in their original scope; they do not make the corresponding native Godot subsystem complete.

## 2. Platform and architecture decisions

Start with the installed **Godot 4.7.2, Forward+, desktop Vulkan** configuration. Windows x86-64 is the first export target; Linux qualification follows. Mobile, Web, Compatibility rendering, VR, multiplayer and multiple simultaneously streamed planets are later scope. Keep project code GPL-3.0-or-later and distributable assets CC0/public domain or explicitly verified compatible licenses; retain the AI disclosure.

Use GDScript for control flow, tools and the first bounded terrain prototype. Profile before moving sampling, mesh generation or scatter packing into a pinned C++ GDExtension. Any extension must ship prebuilt binaries and reproducible source/build instructions. A custom double-precision Godot build is a contingency, not a prerequisite for the first release.

Godot distinguishes 64-bit GDScript scalar floats from the standard build's 32-bit vector components. Engine double-precision support also has costs and does not make ordinary shader arithmetic double precision. Keep absolute planetary calculations out of ordinary `Vector3` values. [Godot large-world documentation](https://docs.godotengine.org/en/stable/tutorials/physics/large_world_coordinates.html).

Split the current viewer incrementally into the following **planned** responsibilities; preserve the imported review mode while each replacement becomes usable.

| Planned area | Responsibility / contract |
| --- | --- |
| `godot/scripts/world/` | `PlanetDefinition`, versioned generator settings, scalar-precision planet locations, local frames and rebase notifications |
| `godot/scripts/terrain/` | Canonical height/mask providers, cube-face addressing, tile error bounds, mesh selection, border stitching and morphing |
| `godot/scripts/streaming/` | Job scheduler, immutable worker results, request cancellation, cache keys, residency and upload/retirement budgets |
| `godot/scripts/ecology/` | Stable cell ownership/IDs, habitat sampling, physical sizes, shared population descriptors and representation selection |
| `godot/scripts/rendering/` and shaders | Ground/foliage materials, sun/sky, atmosphere, clouds, water and reflection contracts |
| `godot/scripts/navigation/` | Free flight, radial up/altitude, optional walking/clearance, collision bubble and camera route replay |
| `godot/scripts/tools/` | Planet controls, region import, bookmarks, saved projects, quality presets and diagnostic overlays |
| `godot/tests/` and `tools/` | Native tests, provider golden fixtures, route measurements, asset conversion and standalone export/package checks |

Do not mechanically translate Blender dependency-graph updates or rebuild the globe on every camera event. Reuse the algorithms, data and tests that remain useful.

## 3. Milestones and dependency order

The frozen import and first native implementations of M0–M3 are available. Their measured scope is recorded in the native guide; availability does not close every exit gate. Deliver each subsequent stage as a runnable Godot build, recorded checks and an updated known-limits section. Dates/effort for the remaining work require the accumulated measurements.

| Order | Milestone | Depends on | Exit deliverable |
| --- | --- | --- | --- |
| M0 | Benchmark, profiling and feasibility checks | Existing import | Reproducible camera routes, memory/frame report, photographic reference board, recorded precision/GI/atmosphere decisions |
| M1 | Planet coordinates and canonical data | M0 | Native height/mask queries and local frames work across a cube-face seam and at a pole |
| M2 | Bounded terrain streaming | M1 | Continuous flight beyond the imported patch generates/loads new terrain with no holes, bounded caches and coarse fallback |
| M3 | Native ecosystem streaming and LOD | M2 | Plants/rocks persist across movement, eviction, re-entry and quality changes; contact and coverage remain stable |
| M4 | First photographic woodland/meadow | M3; early material/light tests in M0 | Accepted stills and moving views under front, side, back and overcast light, within the measured working set |
| M5 | Clear planetary atmosphere and entry | M1–M4 | Continuous entry and reverse exit share terrain, sky, solar lighting and aerial perspective |
| M6 | Fly-through clouds | M5 | Cloud passage, shadows and temporal reconstruction survive entry, rebase and camera turns |
| M7 | Animated ocean | M2–M5; may precede M6 after profiling | Offshore descent resolves stable geometric waves, reflection and absorption; shoreline remains a separate gate |
| M8 | Canyon, alpine and richer ecology | M2–M4; share M5 rendering | Real cliff/rubble contacts, coherent strata, rock/snow masks and habitat-specific assets pass close/aerial review |
| M9 | Godot designer and public runtime beta | First vertical slice, then progressively M5–M8 | Saved planet projects, useful controls, tested hardware presets and editor-free exported application |

Export a minimal runnable Windows build during M0 and update it at each milestone. M9 is qualification and product completion, not the first time export is attempted. Release an explicitly scoped streaming alpha after M3; do not hold all useful builds until clouds, water and every biome are finished.

## 4. M0–M1: benchmark, precision and data ownership

### Establish evidence before expanding the runtime

Preserve the five imported scenes and their exact assets/cameras as regression fixtures. Add a woodland/meadow route at human and canopy height, a route crossing the original detail boundary, a measured-region boundary route, and a coarse orbital/polar route. Record generator revision, settings, seed, asset hashes, camera/FOV, sun, time, exposure, engine, driver, resolution and hardware. Use actual photographs with documented usage rights for appearance review; existing Blender renders help diagnose regressions but cannot establish realism.

Measure main-thread work, worker latency, render/GPU time where available, frame intervals, submitted geometry, batches, texture residency estimates, resident tiles, pending jobs, cache bytes and process RAM. Validate GPU memory estimates against driver/tool measurements; a triangle counter cannot qualify VRAM. Include cold and warm runs, fast turns, rapid descent, reversal and a repeated five-minute route. Separate shader/import warmup from steady-state results and report both.

Run three bounded risk checks early: close-to-orbital projection precision; foliage/indirect lighting during a rebase; and a depth-aware spherical atmosphere pass with alpha-cutout leaves and a water test surface. Record failures and select an approach before expanding those systems. APIs in the online stable docs must be checked against the pinned engine; the MultiMesh guide itself carries a version-update caveat.

### Coordinate contract

Represent a planet location with canonical cube-face coordinates/height and scalar-precision Cartesian calculations as needed. Integer tile coordinates and double scalar fractions remain precise before subtracting the local origin. Use ordinary float vectors only for small local offsets and orientation. Keep radius, sea level, terrain heights and object dimensions in metres.

Compute altitude and up from the actual planet centre and canonical surface, replacing the viewer's current fixed `global_y` height approximation. Free flight can retain a stable radial horizon or use explicit six-degree-of-freedom space flight. Avoid a pole singularity by transporting the local frame rather than deriving east from a cross product that vanishes at the pole.

A rebase moves local terrain, vegetation, physics and effect anchors together. It must not change terrain samples, plant identity, UV phase, wind/wave phase, sun direction or exposure. Notify temporal effects to transform/reset their histories explicitly. Test centimetre-sized local motion at Earth-scale radius, poles, face corners and repeated rebases. This measures coordinate repeatability, not DEM accuracy.

Start with one camera-relative render space. If the projection spike cannot keep near-ground detail and the orbital globe stable, evaluate a separate scaled-space far view with explicit depth/occlusion, lighting and atmosphere composition. Do not commit the main renderer to a two-camera composite before that test passes. A double-precision engine build is another measured alternative, requiring matching editor/export templates and extension binaries.

### One authoritative terrain provider

Define deterministic queries for height, normal, water level and habitat/substrate fields from a canonical location. Rendering, scatter, collision and material masks use that same provider and revision. Compose a seeded base planet with geographically bounded measured-region overrides and explicit edge blending. Give measured data, generator changes and artistic offsets separate version fields.

Convert the existing 4096² Rainier/canyon height sources into versioned height/mask pyramids with no-data handling, physical extents, min/max heights and conservative geometric error bounds. Their approximate sample spacings are **4.88 m and 2.44 m**; sampling/subdividing them more finely does not create measured centimetre detail. Add smaller-scale procedural relief and scanned rock/soil geometry as separate declared detail sources.

Port the portable ideas/tests in `lod_mesh.py`, `ecology.py` and `look_math.py` through small golden fixtures. Blender shader-graph field evaluation is not a native Godot height provider; specify and test its native replacement. Freeze legacy imported fixtures independently when a revised generator intentionally changes terrain.

## 5. M2: terrain generation and residency

Use a cube-sphere quadtree with local mesh patches. Begin by testing reusable 65 × 65 vertex grids, refining by projected **displaced-surface error**, visibility and a user error threshold. Keep neighbouring levels within one step and stitch shared borders, including rotated cube-face borders. Generate border heights from the same canonical samples; skirts alone do not pass the seam gate. Morph between parent and child surfaces without shifting features. Unknown error bounds require conservative refinement or a declared limitation, not a zero-error assumption.

The first vertical slice streams a bounded woodland/meadow region and procedural surroundings before adding the full measured-region datasets. A coarse complete planet stays resident. Keep a valid parent until all required children and their boundary transitions are ready; retain rollback coverage during eviction. Narrow the near-ground error tolerance around visible plant/rock contacts.

Use a state machine such as `requested → CPU-ready → upload-ready → resident → retiring`, with failure/cancellation states. Workers perform file decoding, height/mask sampling and array generation on owned data. Integrate scene nodes/resources through a bounded main-thread queue; use supported rendering-thread APIs for custom GPU work. Godot's active scene tree and arbitrary GPU/resource operations are not generally safe worker-thread jobs. [Thread-safe APIs](https://docs.godotengine.org/en/stable/tutorials/performance/thread_safe_apis.html).

Key cached results by planet/generator revision, seed, dataset checksum, face/level/x/y, material/field revision where relevant, and format version. Include bounds, channel metadata, checksums and atomic writes; reject stale/corrupt entries. Store mutable caches under `user://`, separately from bundled read-only content. Retire obsolete requests by generation token and discard late results safely.

Prioritize visible error, proximity and predicted travel; prefetch ahead with a capped horizon and retain some coverage behind the camera for turns. Limit jobs, staging bytes, resident CPU/GPU data and disk cache separately. Budget uploads **and destruction** per frame. A timer around submission does not guarantee a driver upload will finish within that time: measure resulting frame stalls and reduce patch/upload size when necessary.

When demand exceeds budget, retain coarse coverage and reduce permitted detail progressively. Do not let a rapid descent exhaust memory or expose an empty tile while waiting. Expose the current achievable detail rather than silently claiming all requested detail is resident.

**M2 gate:** fly laterally beyond the original snapshot and descend over newly supplied terrain; turn back and revisit it. Check topology, shared border heights/normals, morph bounds, no-data/region transitions, texture phase and cache invalidation. Residency must plateau under repeated travel rather than grow with distance. Inject delayed/failed tile requests to verify coarse fallback.

## 6. M3: ecosystems, assets and movement

Generate vegetation/rocks in stable ecological cells independent of render tile LOD. Define ownership at cube-face boundaries to prevent duplicate plants. Use a collision-safe full cell/instance identity; the existing per-site 32-bit exported IDs are useful fixtures but are not sufficient proof of global uniqueness. Namespace legacy imports separately. Seed variation from canonical identity, never from camera position, worker completion order or resident tile number.

Sample habitat, slope, soil/moisture and water exclusions from canonical fields. Preserve physical sizes, age structure, clearings and density patches; add minimum spacing and trunk/large-rock clearance. Anchor roots to canonical ground, not a changing display mesh. A quality reduction changes representation/spending, not which trees exist. Regeneration after eviction must reproduce the same population.

Build a shared asset catalogue with source hash/license, dimensions, map conventions, texture footprint, all accepted LODs, bounds and image-error evidence. Deduplicate maps/resources across glTF LODs and variants instead of loading repeated embedded textures. Keep high-resolution masters offline; distribute curated runtime textures and meshes by measured need. The current 1.1 GB project ZIP is not the texture-memory target.

Mipmaps improve sampling but do not by themselves unload high-resolution textures. Start with explicit runtime texture tiers and bounded resource loading; evaluate finer-grained texture streaming only when measurements justify its complexity. Eviction must release cache and scene references as well as job buffers, and account for deferred GPU retirement.

Validate silhouettes, alpha coverage, normals, backfaces, roughness and shadow response at intended size and several directions. Regenerate the empty dead-tree atlas views. Retain geometric foreground leaves/blades where cards fail; reduce scanned source meshes by observed shape/coverage error rather than an arbitrary percentage. Source mature-tree variants can be very expensive, so the generator must be able to choose a detailed mesh near **any** newly visited tree without making every tree a hero mesh.

Use spatial MultiMesh batches per species/material/LOD, with independently adjustable full-detail distance, transition distance, maximum reach and shadow reach. Include batch bounds in distance selection so nearby crowns are not lost at cell edges. Godot culls a MultiMesh as a group; splitting by region is necessary for useful culling. Native HLOD ranges provide per-node transitions and hysteresis, not a complete ecosystem streaming system. [MultiMeshes](https://docs.godotengine.org/en/stable/tutorials/performance/using_multimesh.html), [visibility ranges](https://docs.godotengine.org/en/stable/tutorials/3d/visibility_ranges.html).

Derive medium meshes, directional crown/patch proxies and subpixel land-cover descriptors from the same population. Make distant grass preserve average coverage without widening tufts. Test complementary transitions for duplicated shadows, alpha noise, TAA ghosting and density rings. Wind uses canonical position, instance seed and absolute simulation time; changing LOD must not restart it. Far descriptors must be generated hierarchically or analytically, without enumerating a whole planet's individual blades.

Add a small, budgeted collision/clearance bubble around the camera. Start with terrain plus nearby significant rocks/trunks; no per-blade colliders. Coordinate collider replacement/rebasing at physics boundaries, retaining a safe old collider until its replacement is ready. Walking is optional; free flight remains available. Newly loaded or changed terrain must not drop the camera through an uncovered collision region.

**M3 gate:** repeated boundary crossings, evictions, save/reload and low/high quality switches preserve tree identity, scale and contact. Native generation upgrades detail near a newly visited tree; it is no longer restricted to the LOD selected by the original Blender camera. Shadows/coverage must remain recognizably consistent through transitions. CPU, draw calls and memory stay bounded.

## 7. M4: close-range photographic benchmark

**Current work: 0.2.0-alpha.2.** Visual development has been brought forward, with natural daylight and subtle cinematic color, CC0 Earth assets, a bounded original-layout woodland study and shared native appearance improvements. See [the visual development report](EARTH_WOODLAND_LOOK.md). Broader framework expansion and other planets are deferred. The full photographic/motion exit gate below remains open.

Finish one coherent woodland/meadow edge before polishing every biome. Review neutral daylight, side/backlight and overcast stills at human/canopy height, plus a moving low pass. Keep a fixed high-detail mode to diagnose materials/lighting separately from LOD. A dark frame or low average pixel error does not pass photographic review.

Ground layers use aligned color/roughness/normal/height channels at physical scale, shared habitat and substrate masks, stable geographic phase, and slope-appropriate projection. Add controlled stochastic repetition reduction without misaligning the maps. Introduce actual clods, gravel, roots and embedded stones where they produce visible parallax/contact; unresolved detail may transfer into normals/roughness. Desert strata and snow are separate habitat/geology work, not recolored meadow material.

Use one solar direction and consistent sky illumination/reflections/background. Establish exposure with neutral swatches and reject clipped pale crowns or crushed canopy. Qualify a practical canopy indirect-light solution using Godot's GI options and a bounded cache/probe experiment if necessary. Compare quality, memory, update cost and rebase/streaming behavior before selecting a default. SDFGI is demanding and does not support dynamic occluders; a moving/rebased streamed world must be tested explicitly. Screen-space effects do not establish off-screen canopy transport. [GI overview](https://docs.godotengine.org/en/stable/tutorials/3d/global_illumination/introduction_to_global_illumination.html), [SDFGI limits](https://docs.godotengine.org/en/stable/tutorials/3d/global_illumination/using_sdfgi.html).

Keep the legacy raised-capture-floor experiment off. Do not replace missing occlusion with foliage emission, unrelated fill suns or globally multiplied dark AO. Decide which static diffuse/visibility data can be reused as daylight changes, and invalidate data that actually depend on the sun, geometry or material. If an affordable approach fails, record the limitation rather than certifying dynamic GI.

**M4 gate:** review actual 4K stills/100% crops and runtime-resolution motion against the reference board. Evaluate geometry, habitat, scale, contacts, materials, illumination and temporal stability separately. Record a human visual decision alongside measurements. A renderer comparison remains diagnostic, not the release score.

## 8. M5–M6: atmosphere and clouds

Implement spherical clear-air transport using one `PlanetAtmosphere` parameter set for radius, density profiles, scattering/absorption, sun and exposure. Evaluate a LUT approach against a numerical reference, starting with an Earth-like atmosphere and declared parameter bounds. [Bruneton's reference implementation](https://ebruneton.github.io/precomputed_atmospheric_scattering/) provides tested transport/reference ideas; review licenses separately before reusing implementation code.

Use consistent transmittance/in-scattering for sky rays and rays ending on terrain or foliage. Couple solar attenuation and the sky used for surface lighting/reflections to those same parameters. Preserve regional land contrast and smooth night-side/horizon behavior. The visible sky alone is not atmospheric entry, and the atmosphere seen by the camera is not automatically the correct lighting at every ground location.

Prototype a depth-aware Godot compositor pass for opaque terrain/alpha-cutout foliage and a matching sky path. Validate reverse-Z reconstruction, MSAA-resolved depth, near/far clipping and local-to-planet conversion. Select its actual callback stage after testing the sky/back-buffer/reflection ordering. The compositor runs on the rendering thread and its API is experimental; pin/test it with the engine. [Compositor](https://docs.godotengine.org/en/stable/tutorials/rendering/compositor.html), [CompositorEffect stages](https://docs.godotengine.org/en/stable/classes/class_compositoreffect.html).

Water and other genuinely transparent layers need explicit per-layer transport/composition; applying one post-process using opaque depth will not solve their ordering. Avoid applying haze twice. Keep the simpler opaque water test until its atmospheric composition contract passes. Surface/sky/cloud reflections must not silently use a different atmosphere.

Then add a bounded volumetric cloud layer with stable weather fields, density/detail levels, sun shadows and atmosphere-aware composition. Use reduced-resolution integration/temporal reconstruction only after history rejection works during rebase, fast flight, disocclusion and exposure changes. Preserve shared wind/time phase. An unlit orbital shell can remain a declared preview while the volume develops; it does not pass the fly-through gate.

**M5/M6 gates:** uninterrupted descent and reverse ascent from orbit to ground, lateral flight, day/twilight/night-side views, 99/100/101 km boundary stress cases and new radii within supported bounds. Test cloud entry/exit separately. Check bright rims, washed-out terrain, double haze, alpha halos, depth artifacts, history trails and lighting handoffs. Include clear-air-only results to distinguish cloud failures.

## 9. M7–M8: water, geology and ecosystem breadth

Replace the imported frozen waves with a canonical, time-continuous ocean surface. Begin with a small deterministic multi-scale geometric-wave test to establish the mesh/phase/LOD/CPU query contracts. Evaluate a spectral FFT ocean for offshore shots, with user wind/direction and finite wave bands, on the actual GPU budget. RenderingDevice compute is available in Forward+/Mobile, not Compatibility; custom GPU work needs correct synchronization/resource lifetime. [Godot compute shaders](https://docs.godotengine.org/en/stable/tutorials/shaders/compute_shaders.html).

Wave displacement is real geometry where resolved; fading wave bands contribute appropriate normal/roughness energy farther away. Use camera-relative phase inputs, stable absolute time and shared edge samples. Rebase/LOD changes must not swim or reset waves. Add Fresnel response, absorption, sky/terrain reflection fallback and foam from a meaningful breaking/compression measure with persistence. Verify atmospheric composition at the water surface. Shoreline bathymetry, shoaling, breaking surf, wet sand and underwater transitions are separate later gates, not implied by an offshore FFT.

For canyon/alpine regions, improve landform detail before increasing triangle caps. Preserve regional height differences, add separate real overhang/cliff meshes where a heightfield cannot represent the shape, and generate talus/rubble with canonical contact/ownership. Strata follow geological orientation; snow depends on slope, exposure and accumulation fields. Curate compatible rock, vegetation and soil assets by reference appearance. New assets retain source rights, hashes, transformations and source-versus-runtime LOD evidence.

**M7/M8 gates:** an offshore orbit-to-wave descent and revisit; low canyon passes and close cliff views; alpine ground and aerial views. Inspect geometry in clay/wireframe and grazing views. Demonstrate geometry/parallax/contact, stable wave phase, coherent geology, correct material scale and bounded memory. Extend the first habitat's rules to other ecosystems after their source assets and references are accepted.

## 10. Budgets, quality controls and test routes

Initial qualification target: **an 8 GB desktop GPU and 16 GB system RAM at 1920 × 1080, 30 fps**, with a later 60 fps goal. These are proposed targets, not existing support claims; the RTX 5090 import tests do not qualify that tier. GPU architecture/driver matter as well as capacity. Do not certify the target until a representative device actually runs the route.

| Initial tuning target | Proposed starting limit / check |
| --- | --- |
| Frame pacing | Warm-route p95 ≤33.3 ms, p99 ≤50 ms; disclose every >100 ms stall and cold-start shader/upload stalls |
| Main-thread streaming integration | Aim for ≤2 ms per frame; cap work/bytes and measure driver-induced stalls separately |
| Resident memory | Aim for ≤6 GB application GPU use and ≤10 GB process RAM on the target machine, with explicit overhead/measurement method |
| Terrain error | Start near 2 projected pixels, tighten around visible contacts; hard residency limits can override refinement with recorded fallback |
| Cache behavior | Separate configurable RAM/VRAM/staging/disk limits; repeated routes plateau and eviction reproduces the same results |

These numbers are starting experiments and may change with recorded evidence. Reserve working memory for parent/child transitions, texture uploads and effects rather than filling the entire allowance with visible meshes. Avoid prescribing universal tree-triangle limits before the visual/error and GPU-cost tests.

Expose settings in physical terms: terrain error, near detail radius, tree/ground-cover reach, transition width, shadow distance/resolution, texture allowance, CPU/cache/upload limits, atmosphere/cloud/water quality, and an optional adaptive-quality target. Provide named presets only after measurement. Adapt gradually with hysteresis and reveal the achieved detail; never reseed vegetation or change physical planet/plant dimensions to meet a frame target.

| Cost to reduce with distance / projected size | Policy to implement |
| --- | --- |
| Terrain and mesoscopic displacement | Coarsen real geometry using error bounds/morphing; retain landform silhouette and contact constraints; transfer unresolved relief into normals/roughness |
| Plants and rocks | Detailed mesh → reduced mesh → shared-population patch/crown representation → filtered land cover; user distances constrain the working set |
| Shadows and AO | Separate shadow reach/resolution and bounded local AO radius; fade unresolved contact detail without changing base albedo or leaving permanently dark distant vegetation |
| Textures and microdetail | Mipmaps, shared resources and measured residency/quality choices; keep color/data maps aligned and physical texture phase stable |
| Waves and volumetrics | Reduce resolved wave bands, cloud sampling and atmospheric pass resolution with measured transitions; retain phase, coverage and large-scale lighting |

Distance is a useful user control, but projected error and visibility determine which features are actually resolved. A distant mountain silhouette must survive even when its foreground microgeometry no longer needs rendering.

Required motion coverage includes a 2 m woodland low pass, canopy climb/descent, a newly generated patch, measured-region edge, cube-face seam/pole, origin changes, fast 180° turn, rapid orbital descent and reverse exit, water approach, and repeated five-minute travel. Include cache-cold/warm, reduced budgets, worker delays, edit invalidation, deterministic route replay and fresh-process save/reload. Separate numeric correctness, photographic review, temporal artifacts and hardware qualification in the report.

## 11. Designer workflow and deployment

Build a native planet resource/project containing seed, radius, providers/region transforms, sea level, habitat/material settings, atmosphere, daylight/time, asset catalogue revisions, user overrides and bookmarks/routes. Persist user-authored settings separately from discardable caches. Define edit invalidation by dependency so a camera move does not invalidate the world and a changed height provider cannot retain stale roots/colliders.

Preserve useful existing controls progressively: terrain/scatter budgets, biome parameters, ocean and atmosphere controls, saved locations and a deterministic descent recorder. Give current scenes a legacy-import mode. First support one living rocky planet, the woodland/meadow benchmark and offshore water. Other existing presets, gas giants/stars, rings, additional cloud types and broad artistic controls are later feature ports with their own supported-feature checklist; they are not silently claimed as present in Godot.

Package an exported Windows executable/data pack with a small accepted default planet, optional content packs, quality settings, controls, limits, notices and AI disclosure. Ship editable source and compatible asset manifests alongside it. Generated terrain caches belong in writable user storage. Verify required raw binary/provider files are explicitly included by the export preset, rather than assuming Godot's resource scan will discover them.

Use matching Godot export templates, and test on a clean machine/profile with no editor, Blender, source tree, cached imports or development absolute paths. [Godot export workflow](https://docs.godotengine.org/en/stable/tutorials/export/exporting_projects.html). Use a distinct release line such as `godot-v0.2.0-alpha.1`; retain the Blender `v1.3.0-beta.1` archive. Do not label the current project ZIP as a standalone Godot deployment.

The first public runtime beta requires the streaming/photographic benchmark, save/load, measured target hardware and a continuous entry/exit demonstration over declared supported content. Cloud passage, shoreline and other incomplete features remain separately labelled. Later Linux exports receive native launch, shader, file-path and performance checks before Linux support is advertised.

## 12. Next implementation batch

The first implementation pass of these three items is now available in the native alpha; their remaining qualification/extension work follows the gates above:

1. **M0 foundation:** add repeatable camera-route playback and structured profiling to the existing viewer; export a minimal Windows test app. Preserve the current frozen review as a selectable reference. Record the projection/GI/atmosphere feasibility checks and baseline memory, not just FPS.
2. **M1 provider and coordinates:** introduce `PlanetDefinition`, scalar-precision location/local-frame helpers and one native height/mask provider. Add small cross-language golden fixtures, polar/seam tests, physical altitude, and versioned region-data conversion.
3. **M2 first streaming terrain:** implement bounded worker jobs, cache/residency and stitched/morphed terrain patches around one woodland/meadow route. Fly beyond the original imported area with coarse fallback, cancellation and memory plateau checks. Add native ecosystem cells next, without expanding all five biomes first.

Do not restart Blender rendering/parity work to satisfy these items. Blender exports remain available when an asset or diagnostic reference actually needs them. Update this plan with each measured milestone; only strike through an item when its stated exit gate is demonstrated.
