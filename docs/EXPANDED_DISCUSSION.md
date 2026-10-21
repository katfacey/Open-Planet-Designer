# Open Planet Designer: photorealism research and implementation guide

**Research date: 20 October 2026. Beta status updated: 21 October 2026.**

This expanded discussion records the research, diagnosis, implementation direction and remaining goals for Open Planet Designer. The first three highest-priority structural corrections have been implemented in the beta and are struck through below. The research originally preceded implementation; later sections remain design proposals unless the beta status explicitly says otherwise. See [the realism guide](REALISM_GUIDE.md) for the actual implementation, tests and limitations.

**Completed structural pass:** more varied forest ages/forms; coherent measured regional terrain; fixed-size grass and vegetation representations derived from shared placements. These are scoped implementation milestones. Photographic approval, close engine agreement, hero cliff meshes, complete ecological rules and seamless animated LOD transitions remain open. The 25-second demo shows one continuous bounded descent with cached destination detail. It does not qualify arbitrary routes, dynamic LOD transitions or consumer hardware.

## 1. Recommended direction

Build a **continuous landscape with several representations of the same underlying terrain and ecosystem**. Use measured terrain and scanned foreground assets for the first photographic benchmark; add procedural generators for variation after that benchmark works. Spend geometry where it changes the visible shape, parallax, shadows, or reflections. Preserve the appearance of that geometry when replacing it at a distance.

The first milestone should be a convincing **grassland adjoining a pine woodland**, viewed at human height, from above the canopy, and during a descent. Establish this in a bounded test region before expanding the other biomes. This gives the generator a concrete photographic standard and exercises its weakest current transition: green distant land becoming individual plants.

Three complementary approaches are worth pursuing:

| Approach | Use | Decision |
| --- | --- | --- |
| Measured elevation + scanned plants, rocks, and ground materials | Highest-confidence route to a convincing first region | Primary implementation path |
| Procedural geology, erosion, habitat rules, and generated asset variants | Diverse fictional planets with consistent geography | Add progressively, comparing with the measured benchmark |
| Offline generation, tile caches, and appearance-preserving LOD | Keep the visible working set affordable during orbital-to-ground shots | Required infrastructure; benchmark on smaller GPUs |

Princeton's [Infinigen](https://infinigen.org/) is a relevant research and implementation reference: it generates natural scenes in Blender and explicitly emphasizes actual detailed geometry. Evaluate selected nature generators as an offline source of plant/rock variants. This is a proposed experiment, not evidence that Infinigen already supports our planet, target hardware, or Eevee/Cycles parity.

“Infinite zoom” should mean continuously revealing available or generated finer detail, within a declared minimum feature size and memory budget. A finite elevation map cannot reveal measured centimeter detail simply by subdivision. New detail must come from scans or appropriate procedural rules.

## 2. Diagnosis of the current saved result

Evidence inspected: the existing `PLANET_LIVING_GUIDE.md`, asset manifests, `biome.py`, `nodes.py`, `lod_mesh.py`, saved verification reports, and the existing comparison/descent images. These are observations and engineering inferences, not new Blender tests.

| Priority | Evidence | Likely contribution to the artificial appearance | Proposed correction |
| --- | --- | --- | --- |
| ~~Highest~~ | ~~Forest crowns and thin trunks repeat; little age or structural diversity~~ | ~~The forest reads as copies of a few objects~~ | Add young, mature, damaged and dead forms; habitat-dependent grouping; inspect original source LODs |
| ~~Highest~~ | ~~Broadly smooth alpine/desert surfaces; canyon structure is weak~~ | ~~More triangles reproduce the same soft shape~~ | Preserve terrain in meters; use regional elevation and drainage/erosion structure; add real cliff meshes |
| ~~Highest~~ | ~~Grass changes into wider, flatter distant clumps; canopy becomes a noise proxy~~ | ~~Representation changes alter the landscape's coverage and shape~~ | Derive distant representations from the same patches and tree placements |
| High | Similar ground treatment across large areas; generic soil/rock transitions | Surface detail lacks geological and ecological relationships | Layer materials using slope, deposition, wetness, substrate and vegetation masks |
| High | Explicit sun, two unshadowed fill suns, and an HDRI all contribute | Lighting may flatten depth or contain inconsistent sun directions | Calibrate a single sun/sky system and test indirect lighting separately |
| High | Descent storyboard becomes largely uniform haze before vegetation resolves | Mid-altitude land structure and atmospheric continuity are inadequate | Preserve regional land-cover structure and use altitude-aware scattering |
| Medium | Ocean has real waves but repeated patterns and a simple crest foam mask | Water lacks a convincing range of wave scales and foam behavior | Evaluate a spectral ocean with persistent world-space phase and cached foam |

The current implementation already has useful foundations: actual displaced terrain, shared instances, stable placement IDs, budgets, and a floating origin. Retain those ideas. The photographic problem is not solved by increasing every triangle cap or loading every texture at 8K.

Existing 960×540 engine comparisons report mean display-space RGB differences of about **2.67% grassland, 4.86% forest, 1.42% ocean, 0.53% alpine and 1.44% desert**. These measure agreement between two synthetic images. They do not measure realism, and a low average can conceal conspicuous local shadow or foliage differences. Existing performance results also do not establish consumer-GPU suitability.

## 3. Terrain: use believable structure at every scale

### 3.1 Replace repeated normalized terrain stamps with regional data

Use a defined regional footprint, real horizontal spacing, and heights in meters. Keep source projection, vertical datum, no-data masks, and the transformation into planetary coordinates. The current Rainier/Canyon data are resampled and artistically repeated; they should remain legacy examples rather than the photographic reference.

For the first mountainous or canyon region, investigate USGS 3DEP **1-meter elevation where available**, with a coarser outer region. USGS describes its [3DEP products](https://www.usgs.gov/3d-elevation-program/about-3dep-products-services) and the newer [Seamless 1-Meter product](https://www.usgs.gov/3d-elevation-program/new-product-3d-elevation-program-seamless-1-meter-digital-elevation-model-s1m). Availability must be checked for the chosen location. The [USGS collection catalog](https://data.usgs.gov/datacatalog/data/USGS%3A3a81321b-c153-416f-98b7-cc8e5f0e17c3) identifies 3DEP products as public domain.

Use bare-earth terrain for the ground. A surface model containing tree crowns must not also receive a second full-height forest. One-meter terrain still needs separate centimeter-scale soil, rubble, roots and rock detail near the camera. Heightfields also cannot represent overhangs: canyon ledges, undercuts, caves and near-vertical hero faces require separate meshes or local volumetric terrain generation.

For a fictional planet, place selected regions coherently in the planetary coordinate system and connect their boundaries through compatible landforms. Do not repeat a recognizable mountain every few kilometers. High-resolution regions can be generated and cached on demand; a first prototype may cover only the demonstration route, and must identify that coverage honestly.

### 3.2 Make terrain, materials and scatter follow the same processes

Generate a reusable set of fields: elevation, slope, curvature, drainage/flow accumulation, sediment/debris, substrate, soil depth, moisture, water level, temperature and habitat suitability. Treat some as artistic approximations initially; a full climate simulation is not a prerequisite.

Use these relationships: exposed steep faces receive rock; loose debris accumulates below cliffs; grass prefers suitable soil; trees avoid open water and unsuitable slopes; wet hollows differ from dry ridges. Canyon strata should follow a defined rock structure rather than a generic world-height color ramp. Snow needs slope/aspect/exposure and accumulation masks rather than a uniformly whitened summit.

For procedural regions, bake erosion at several scales before rendering. [SideFX's HeightField Erode documentation](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_erode.html) demonstrates hydraulic/thermal erosion and useful sediment, debris and flow outputs; its [flow-field guide](https://www.sidefx.com/docs/houdini/heightfields/flowfields.html) also connects those fields to scattering. These are technical references. The default plan does not require buying Houdini: start with measured terrain and derived masks, then evaluate an erosion implementation independently.

### 3.3 Allocate real geometry by visible error

Maintain terrain tiles with minimum/maximum height and a bound on the difference from the next finer surface. Refine using the **displaced terrain's error**, including silhouettes, rather than only distance to the reference sphere. Keep coarse/fine borders identical; morph terrain between resolutions without moving the underlying geographic features.

Retain the current spherical quadtree initially and improve its bounds, caching and transitions. [Losasso and Hoppe's geometry clipmaps](https://hhoppe.com/geomclipmap.pdf) and [Strugar's CDLOD paper](https://www.tandfonline.com/doi/abs/10.1080/2151237X.2009.10129287) are useful design references for bounded working sets and smooth terrain LOD. Their original GPU performance does not transfer automatically to Blender's Python/dependency-graph workflow.

Use one evaluated displaced mesh in both engines for the baseline. Small unresolved detail may use normal/bump maps; features affecting outline, contact or camera parallax need geometry. Blender documents this distinction in [Displacement](https://docs.blender.org/manual/en/latest/render/materials/components/displacement.html). Current [EEVEE material documentation](https://docs.blender.org/manual/sl/5.2/render/eevee/material_settings.html) also describes true vertex displacement: do not assume Eevee is limited to bump mapping. Shared explicit geometry is chosen for control and comparison, not because Eevee cannot displace vertices.

## 4. Plants and rocks: build ecosystems, then reduce their cost

### 4.1 Choose assets by their rendered appearance

Compare the existing imported pine LOD2 variants against their original higher-detail sources before replacing or decimating them. A triangle count alone cannot tell whether the crown, needle density, bark or branch silhouette is suitable.

For the first woodland, assemble a curated set with several mature silhouettes, saplings, irregular/dead trees, shrubs, ground-cover species, litter, roots and fallen wood. Keep the species compatible with the chosen habitat. The counts are an art requirement to evaluate, not a fixed quota that makes a scene realistic.

Use real leaf/blade geometry for prominent close plants where cards visibly fail in silhouette or parallax. Carefully cut alpha cards can remain useful farther away. Check front/back normals, translucency, leaf thickness, roughness and transparent shadows under front light, backlight and overcast light. Avoid making foliage waxy with arbitrary transmission or uniformly dark with multiplied AO. [NVIDIA's tree-rendering chapter](https://developer.nvidia.com/gpugems/gpugems3/part-i-geometry/chapter-4-next-generation-speedtree-rendering) explains why silhouette, leaf lighting, self-shadowing and antialiasing all matter.

Evaluate Infinigen Nature on a separate future test: generate a handful of bounded assets, inspect their geometry/materials and costs, and export accepted variants to the common library. The official repository currently directs natural-scene users to [nature-stable](https://github.com/princeton-vl/infinigen/tree/nature-stable); [2.0's documentation](https://github.com/princeton-vl/infinigen/blob/main/docs/source/Infinigen2.md) describes a preview with incomplete asset coverage. Pin a suitable version after testing. The [main license is BSD-3-Clause](https://github.com/princeton-vl/infinigen/blob/main/LICENSE); inspect individual files and dependencies, including the separately licensed [GPL component repository](https://github.com/princeton-vl/infinigen_gpl), before incorporating code. Do not label every dependency or generated/exported package CC0 by assumption.

### 4.2 Place assets through stable habitat rules

Replace the visible jittered plantation effect with deterministic patches and minimum spacing. Separate large habitat structure from small placement variation. Include clearings, dense young groups, older widely spaced trees, shaded understory, sparse ridges and drainage corridors. Apply slope, substrate and water exclusions, then collision/clearance checks for trunks and large rocks.

Anchor plants to the canonical terrain height, not a changing coarse display mesh. Constrain terrain LOD error around visible contacts so feet, roots and embedded rocks remain attached. Keep ecology sizes in meters, independent of planet radius. Generate wind from world position, a stable instance seed and absolute time; changing camera or LOD must not restart it.

### 4.3 Preserve coverage through LOD

| View | Representation to evaluate | What must remain consistent |
| --- | --- | --- |
| Foreground | Detailed instanced plants, branches, blades and stones | Real contact, silhouette, parallax and shadows |
| Middle distance | Simplified meshes with rebaked normals and carefully preserved foliage area | Crown shape, plant height, visible density, color and shadow coverage |
| Distant resolved patches | Cluster meshes or tested multi-view depth/normal impostors | Same patch/crown positions, edge silhouettes and response to viewing direction |
| Subpixel vegetation / orbital land | Filtered land-cover and canopy descriptors from the same habitat/tile data | Average coverage, reflectance, roughness and large clearings |

Do not widen distant grass tufts to conceal missing instances. Replace their aggregate appearance with a calibrated patch representation. Do not substitute unrelated canopy noise for visible trees. Start by deriving proxies from one accepted region, then build a lazy tile hierarchy so the entire planet need not be populated at once.

[Bruneton and Neyret's forest-rendering research](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-8659.2012.03016.x) is especially relevant: it treats trees and their distant aggregate lighting as connected representations. A Blender implementation will need its own prototype; the paper's specialized shaders are not native drop-in nodes.

Use hysteresis and smooth transitions. Prefer shape morphs for terrain; test complementary dithered transitions for foliage while checking double shadows and transparency noise. Preserve stable instance membership across revisits. Validate low-detail meshes against the original from multiple directions, especially against the sky; generic decimation can remove most apparent foliage while retaining a large trunk.

## 5. Materials, illumination and camera response

Use physically scaled scanned surfaces with a small number of coherent layers: mineral/bedrock, loose soil, fine gravel, vegetation/litter and optional moisture/snow. Add macro variation from terrain/habitat fields, mesoscopic displacement for clods and stones, and fine roughness/normal detail. Fine noise everywhere cannot substitute for those scales.

At asset ingestion, record physical coverage and displacement amplitude; separate color textures from data maps; verify normal-map convention and tangent basis. Use high-precision height data where appropriate. When rotating or blending texture projections, transform their normals consistently. Make stochastic tiling preserve aligned color/roughness/normal/height channels and avoid blending distinctive rocks into a blurred surface.

Use AO as a controlled occlusion aid, not permanent dark lighting baked into every base color. Avoid double application between packed material maps and scene occlusion. Bake geometric detail into lower LODs where appropriate; Blender's [baking documentation](https://docs.blender.org/manual/en/latest/render/cycles/baking.html) covers normal and displacement transfers. Filter disappearing normal detail into the lower-detail roughness response and check specular shimmer in motion.

For lighting, establish one solar direction and a consistent sky for illumination, reflections and camera background. Use either a calibrated HDRI with a compatible sun contribution, or a procedural physical sky/sun. Check for a duplicated sun highlight. Remove the two unshadowed fill suns in an isolated future comparison; replace their useful indirect contribution through an appropriate sky/GI solution instead of merely darkening the image.

Use a neutral material swatch, a diffuse sphere and a reflective sphere to diagnose illumination before tuning plants. Fix camera field of view, exposure, white balance and display transform for comparisons. Use scene-linear masters and one display transform, initially AgX if supported by the pinned Blender version. Blender's [color-management guide](https://docs.blender.org/manual/en/4.4/render/color_management.html) explains scene-linear workflows and display transforms. Do not use heavy bloom, fog, sharpening or shallow depth of field to conceal unresolved scene problems.

## 6. Atmosphere, clouds and ocean

### Atmosphere and cloud entry

Replace the arbitrary orbital-shell/interior-sky handoff with one altitude-aware model for sky radiance, atmospheric transmittance and aerial perspective. Investigate [Bruneton's precomputed scattering implementation](https://ebruneton.github.io/precomputed_atmospheric_scattering/index.html) and [Hillaire's scalable atmosphere paper](https://sebh.github.io/publications/egsr2020.pdf). Both are relevant to a ground-to-space transition.

**Feasibility experiment:** precompute lookup textures offline, encode them in formats native Blender shaders/compositing can sample, and test a clear-sky sphere plus terrain at ground, aircraft and orbital heights. Reconstruct the same planet-local sun/up directions everywhere. The research implementations use specialized graphics pipelines; porting their lookup and lighting logic is real development work.

The compositing model is `observed radiance = transmittance × surface radiance + atmospheric in-scattering`. A single depth-based post-effect is insufficient for multiple transparent layers, foliage edges and water reflections. Validate those cases explicitly and keep sky illumination consistent with the visible atmosphere. Do not apply a second unrelated haze on top.

Clouds need an actual density field or a tested cached local volume along the flight corridor, with consistent cloud base, thickness, wind and large-scale pattern. A photographed HDRI cannot provide parallax during passage through a cloud. Prototype cloud shadows and cloud contributions to water reflections early: these remain high-risk parity features. Native Eevee and Cycles volumes have different capabilities, so full cloud entry must have its own acceptance gate rather than being declared solved by a matching sky background.

### Ocean and shoreline

Evaluate a cached spectral ocean as the default broad-water surface. [Tessendorf's course notes](https://jtessen.people.clemson.edu/reports/papers_files/coursenotes2004.pdf) provide the underlying frequency-domain method. Blender's [Ocean modifier documentation](https://docs.blender.org/manual/fr/5.2/modeling/modifiers/physics/ocean.html) describes its deep-ocean surface and foam workflow.

Use a few distinct wavelength bands: geometric swell and resolved chop nearby; filtered normal/roughness contributions for unresolved ripples. Anchor simulation coordinates and time to the planet so a moving camera patch does not make waves swim or reset. Avoid double-counting the same wave energy in geometry and bump. Keep low-frequency geometry and the apparent wave slope distribution consistent across patch boundaries.

Add foam persistence/advection and distinguish foam from a permanently white crest mask. Tune water absorption/color against depth and sediment, with the same sky reflected in both engines. A shallow-water spectrum does not by itself produce physically convincing breaking surf: shoreline interaction, breaking waves and spray need a separate bounded simulation/cache, introduced after open water passes. Nearshore and underwater views require additional tests for refraction, waterline and participating media.

## 7. Distance controls and a realistic hardware budget

### Control error in the image, then enforce budgets

For a perspective camera, a useful first estimate is:

`projected error in pixels ≈ geometric error in meters × focal length in pixels / view depth in meters`

Use a conservative tile error/bounding volume rather than its center alone; handle near-plane intersections separately. Start by testing a terrain target of **0.5–1 pixel for final output** and **2–4 pixels for preview**, measured at the requested resolution. These are proposed tuning ranges, not validated guarantees. At grazing angles, cliffs and silhouettes need special scrutiny.

Expose understandable controls: foreground detail distance, plant/rock/shadow distances, terrain pixel error, texture quality, memory budget, minimum feature size, and a “lock detail for this shot” option. Distances are maxima constrained by budgets. Report actual achieved coverage and when quality is reduced.

Budget more than triangles: unique geometry, expanded visible instance cost, alpha overdraw, texture residency, shadow/probe pools, volume grids, CPU preparation time, cache size and render time. Off-camera geometry can still cast visible shadows or appear in reflections/probe captures; frustum culling alone is insufficient.

| Candidate hardware tier | Initial experiment | Required evidence before advertising support |
| --- | --- | --- |
| 8 GB GPU | 1080p output; small hero region; mostly 1K–2K maps, selective 4K foreground maps | Peak memory, no swapping failure, stable shadows and usable render times |
| 12 GB GPU | 1080p/1440p; larger cached region and selective higher-resolution surfaces | Same measurements during the entire descent |
| 16 GB+ GPU | Evaluate 4K output and richer foreground assets | Peak rather than average memory, plus temporal quality |

These are benchmark starting points, not measured presets. Reserve capacity for Blender, frame buffers and driver overhead. For scale, an uncompressed 4096² RGBA8 texture is 64 MiB, about 85 MiB with a complete mip chain; actual Blender formats and allocations vary. An 8K version has four times as many pixels. File download size is not VRAM usage.

Create a bounded tile/asset cache with prefetch along the camera route, explicit residency management and recoverable disk caches. Merely hiding objects does not establish that textures or meshes have been released from GPU memory. Bake/capture expensive work once; avoid rebuilding the entire topology and scatter on every animation frame. Start with a shot-baking workflow; interactive flight can follow measured optimization.

Keep double-precision logical planetary coordinates and tile-local geometry. Subtract the local origin before float conversion; keep shader texture coordinates similarly local. The existing origin rig is a starting point, not proof of arbitrary close-up precision. Test rebasing, clipping and horizon landmarks across seams and at several planet sizes. Do not fix precision by clipping required distant mountains out of the shot.

## 8. Eevee/Cycles strategy and limits

Blender's [EEVEE overview](https://docs.blender.org/manual/en/latest/render/eevee/index.html) explains the shared material system and different rendering approach. Its [limitations](https://docs.blender.org/manual/en/latest/render/eevee/limitations/limitations.html) document approximate BSDFs, limited screen-space information, refraction restrictions and single-scattering volumetrics. Almost identical results are a target to validate for supported shots, not a universal guarantee for every lighting/volume/reflection arrangement.

| System | Shared baseline | Engine-specific work to investigate |
| --- | --- | --- |
| Terrain and assets | Same evaluated meshes, positions, LODs, animation and texture data | Sampling/visibility settings only after geometry agreement |
| Surface shading | Common supported PBR nodes and identical physical parameters | Leaf thickness, transparent shadows and indirect response |
| Indirect lighting | Same sun/sky and geometry | Local Eevee probe volumes compared with converged Cycles illumination |
| Water | Same geometric waves, normals and absorption parameters | Reflection/refraction coverage and off-screen geometry |
| Atmosphere/clouds | Same medium parameters, sun, density and timing | Common lookup/pass approach where feasible; native differences measured explicitly |

[Blender's light-probe volume documentation](https://docs.blender.org/manual/id/5.1/render/eevee/light_probes/volume.html) describes static baked diffuse lighting and the memory cost of capture. Bake bounded regions after their scatter is locked; test probe behavior during rebasing and invalidate caches when sun or habitat changes. Moving wind-blown plants and changing daylight need explicit treatment. Do not assume static probes solve dynamic global illumination.

Allow separate engine quality settings, but do not compensate by replacing physical surface shading with emission, removing shadows, or flattening the Cycles reference. If a feature cannot meet the visual tolerance, record the failure and its supported conditions instead of weakening the photographic standard silently.

## 9. Asset shortlist for later evaluation

Poly Haven's [asset license](https://polyhaven.com/license) permits modification and redistribution of its CC0 assets. Website/gallery content is separately governed; do not assume example renders have the asset license. ambientCG's [license](https://docs.ambientcg.com/license/) covers its downloadable assets under CC0. Use documented APIs within their terms for future retrieval. Preserve provenance even where attribution is optional.

| Candidate | Purpose | Evaluation before accepting |
| --- | --- | --- |
| [Pine Tree 01](https://polyhaven.com/a/pine_tree_01), original available LODs | Reassess current mature-tree source | Crown and bark quality at actual camera distance; avoid arbitrary crown stretching |
| [Pine Sapling Small](https://polyhaven.com/a/pine_sapling_small) | Different age/branch structure | Habitat fit and useful variation; species choice should follow the reference |
| [Fir Sapling Medium](https://polyhaven.com/a/fir_sapling_medium) | Additional form where ecologically appropriate | Do not mix species solely to meet a variant count |
| [Grass Medium 01](https://polyhaven.com/a/grass_medium_01) | Scan reference and usable grass forms | Compare geometric blades, cards and material under backlight; add compatible species/forms |
| [Forest Ground 05](https://polyhaven.com/a/forest_ground_05) and the [forest-floor catalog](https://polyhaven.com/textures/ground-terrain/forest-floor?origin=natural&setting=outdoor) | Soil/litter layers beyond the existing material set | Physical texel density, displacement scale, repeated motifs and reference photographs |
| [Bark Debris 01](https://polyhaven.com/a/bark_debris_01) | Dead ground cover for a matching dry habitat | Reduce by image error; do not transplant desert debris indiscriminately into wet forest |
| [A Verdant Trail](https://polyhaven.com/collections/verdant_trail) / [Namaqualand](https://polyhaven.com/collections/namaqualand) collections | Coherent grassveld and arid-region asset candidates | Curate each ecosystem; scene availability is not proof of engine parity |
| USGS 3DEP regional elevation | Physical terrain structure | Location coverage, source resolution, datum, artifacts and project metadata |
| Selected Infinigen Nature generators | Procedural plant/rock variation and geometric detail | Version, file/dependency licenses, export/material compatibility, memory and image quality |

For every accepted asset, record source URL, author, license/notices, retrieval date, checksum, dimensions, texture coverage, map interpretation and transformations. Store original masters separately from reduced variants. Record LOD error, texture resolution and tested view distance. Free commercial renders and permission to redistribute source assets are different permissions; unverified marketplace/free-sample assets should not enter the distributable library.

## 10. Expanded implementation roadmap

The sequence below is the broader roadmap. Parts of terrain, source assets and cheaper representations are now implemented; full photographic and motion gates remain open. Keep the existing scene and package as a recoverable baseline. Do not start by rebuilding all five biomes.

| Stage | Work | Deliverable / gate |
| --- | --- | --- |
| 0. Freeze the benchmark | Record Blender version, hardware, current controls and source revisions. Choose real photographic references with usable rights; match habitat, camera height, field of view, weather and light direction. | Reference board, fixed cameras, baseline images and manifest; distinguish photos from promotional CG |
| 1. Resolve risky assumptions | Small tests for leaf lighting in both engines, static local GI, shared displacement, clear-sky altitude transitions and cloud/water limitations. Evaluate a few Infinigen/scan candidates separately. | Decision log showing usable methods and failures; avoid building the whole system around an untested port |
| 2. Establish terrain and scale | Build a bounded regional height/mask dataset with local geometry and real units. Inspect a neutral clay pass before materials; add hero cliffs/rocks where needed. | Convincing landform silhouette, exposed rock structure and contact geometry at intended distances |
| 3. Make one photographic region | Build a grassland/woodland edge with accepted assets, terrain-driven distribution, layered ground and calibrated sun/sky. Keep high detail fixed for the first still comparisons. | Human-height and canopy-height 4K stills that pass photographic review in Cycles and are closely matched in Eevee |
| 4. Derive its cheaper representations | Construct tree/grass patch LODs, filtered canopy/land-cover data, tile error bounds, transitions and cache/prefetch. | Same region remains recognizable from ground through aerial views; no artificial density rings or proxy replacement |
| 5. Reconnect orbital descent | Make the globe's regional terrain/cover derive from those same fields; integrate the tested atmosphere approach. Include cloud passage only after its separate gate passes. | Continuous entry and exit with consistent geography, light and vegetation; declared limits outside detailed coverage |
| 6. Extend the method | Open-ocean spectral waves, then shoreline; canyon strata/rubble; alpine rock/snow. Each receives its own reference and foreground/aerial test. | Five distinct convincing biomes, not one material/noise recipe with different colors |
| 7. Qualify hardware and package | Tune measured quality tiers, bake/cache the route, verify clean loading and document supported conditions. | Reproducible scene/package, licenses, peak-memory and render-time report, paired engines and descent movie |

Suggested code ownership when implementation resumes: `lod_mesh.py` for terrain error/caching/transitions; `biome.py` for stable habitat placement, contacts, LOD and lighting; `nodes.py` for coherent surface/atmosphere/water fields; asset preparation tools/manifests for source quality and reduction. New terrain-data, cache and validation modules are likely preferable to adding every responsibility to those files. Ownership suggestions are guidance; see the realism guide for modules already added in the beta.

## 11. Acceptance checks: keep realism, parity and scalability separate

### Photographic appearance

- Review 4K stills and 100% crops against real references, including neutral daylight. Judge landform shape, species/form/scale, placement, surface layering, lighting and camera response independently.
- Use foreground, canopy-height, kilometer-scale and orbital views. Include side/backlight and overcast cases; a flattering low sun alone is insufficient.
- Reject obvious repeating crowns, striped scatter, enlarged distant grass clumps, floating roots, uniform orange terrain, snowy smooth blobs, texture scale errors and thick bright atmospheric rims.
- Verify actual geometry with clay, wireframe, grazing views and contact shadows. Normal-map detail alone does not pass a foreground geometry requirement.

### Matching the engines

- Freeze geometry/LOD, camera, time, exposure and display transform. First converge each engine enough to distinguish renderer noise from a persistent lighting difference; sample counts need not be identical.
- Compare scene-linear masters and display images, plus crops/masks for foliage, ground, sky, water and silhouettes. Record mean error, high-percentile error and signed brightness bias. Do not let empty sky dominate the average.
- As a provisional engineering target, investigate **≤2% mean normalized display-RGB absolute difference in each major region**, alongside visual inspection. This threshold is a starting target, not evidence of perceptual identity. Tune it after the benchmark; disclose conspicuous local differences even when averages pass.
- Inspect tree contact shadows, thin backlit foliage, off-screen reflections, horizon haze, cloud shadows and shoreline refraction explicitly. Compare against the photographic reference as well as against each other.

### Motion, scale and hardware

- Render a continuous entry and reverse exit, not just sparse storyboard frames. Cross tile borders, cube-face seams, origin changes and every LOD transition; revisit the same site.
- Test low passes and lateral movement as well as straight-down entry. Include camera turns, several lens widths, two cameras/stereo where supported, wind/waves and motion-blur subframes.
- Check world-locked textures/waves, stable IDs and placement, leaf shimmer, popping, terrain cracks, contact drift, sudden shadow loss and cloud/sky handoffs.
- Lock or precompute deterministic LOD for final animation. Hysteresis must not make the image depend on scrubbing frames in a different order; use a reproducible route bake or a deterministic selection rule.
- Measure peak VRAM/RAM, CPU preparation, render duration and cache growth throughout the route on each claimed GPU tier. Halving a triangle budget on a 5090 is not a substitute for testing a smaller-memory card.

## 12. Continuing development checklist

1. Read this proposal and the current living guide; preserve the existing scene/package.
2. Record the actual Blender build and hardware without changing the project; pin documentation/API assumptions to that build. The online “latest” manual identified itself as 5.2 LTS during this research; avoid relying on 5.4 search results as installed features.
3. Establish the photographic benchmark and run the bounded feasibility tests in Stage 1.
4. Select a small coherent terrain/asset set; retain source rights and physical dimensions.
5. Build the first woodland/grassland still benchmark and diagnose shape, materials and lighting before enabling aggressive LOD.
6. Advance only when the corresponding visual and engineering gates pass; log partial support and unresolved differences plainly.

The proposal's main dependency is artistic validation of one region. Scans, real displacement and published algorithms make higher realism plausible; their successful integration, consumer-hardware performance and near-matching engines remain work to demonstrate.
