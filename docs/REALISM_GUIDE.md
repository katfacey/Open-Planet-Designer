# Open Planet Designer 1.3: first three realism priorities

Updated 21 October 2026. This is a working revision of the generator and a separate review scene. It implements the first three highest-priority items in `EXPANDED_DISCUSSION.md`: forest structure, meaningful terrain geometry, and representations that preserve more of the landscape as detail changes. It is not a claim that every view is now photographic or that the full proposal is complete.

## Review and use

Install **Open-Planet-Designer-1.3.0-beta.1.zip** from GitHub Releases, enable **Open Planet Designer**, and open **Open-Planet-Designer-Beta-Demo.blend**. The public file opens in Solid mode for responsiveness; press F12 to render the actual materials. The authoring baseline and old packages remain local development backups and are not part of the release.

The review opens in Forest at frame 240. **N → Open Planet → Shot camera** selects Forest, Grassland, Alpine, Desert or Ocean. The first four have paired rendered review images in the same output folder. **Living Surface → Upgrade Terrain & Forest Structure** applies the new mode to an existing rocky planet. It anchors measured regions once to authored Alpine/Desert sites when those cameras exist; it does not move the terrain when the camera moves. A scene without those authored sites still receives the new vegetation mode, but no automatic measured-region placement.

Change tree/plant heights, density, scatter distance, **Individual tree distance**, terrain triangle budget, scatter triangle budget and maximum instances in the existing controls. Sizes/distances display in scene units. Internal distances remain radius-normalized, so changing planet radius still scales the ecosystem. **Measured terrain height scale** controls imported terrain amplitude. Refresh Camera Detail applies the current settings. Rebuild materials/geometry after changing the terrain-region configuration itself.

## 1. Forest structure and source quality

The new library has seven tree forms: three mature pines, two different young pines, a fir, and a dead snag. There are also three fern forms, two scanned grass forms, curved blade clusters and a boulder. Placement uses a stable age/form choice, groups with different densities, and small clearings rather than one evenly varied mature-tree plantation.

The mature-tree foreground meshes use the source provider's **LOD1**, retaining **826,954 / 514,980 / 703,322** triangles before runtime selection. The two young pines retain **142,506 / 133,403** triangles and the fir **19,016**. Medium meshes reduce these costs. Distant trees use six-triangle crossed/top representations with color and normal atlases rendered from the corresponding source mesh. These are ordinary PBR materials, not a permanently sun-lit beauty image.

Source material assignments and named texture-coordinate attributes are preserved. The fir's source uses a named attribute rather than a conventional UV layer; losing it produced gray opaque cards during development and was corrected. Atlas preparation also preserves face-to-material indices. All source images required by the prepared library are packed.

New downloads were [Pine Sapling Small](https://polyhaven.com/a/pine_sapling_small) and [Fir Sapling Medium](https://polyhaven.com/a/fir_sapling_medium), alongside the existing [Pine Tree 01](https://polyhaven.com/a/pine_tree_01), fern, grass and rock sources. Poly Haven distributes its assets under [CC0](https://polyhaven.com/license). Provenance is retained in `open_planet_lab/assets/CREDITS.json`, source downloads in `research/cc0/`, and preparation counts in `REALISM_LOD_MANIFEST.json`.

## 2. Measured geometry with a coherent regional footprint

The review uses a single **20 km Rainier region** and a single **10 km Grand Canyon region**, each exported as a 4096² elevation dataset from the official [USGS 3DEP elevation service](https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer). They replace the repeated normalized elevation stamps inside those footprints. Outside them, the new mode uses procedural terrain; the old stamp behavior remains available in the legacy mode.

The data retain their measured height differences: approximately **3,652 m** of relief in the Rainier export and **1,465 m** in the canyon export. A constant vertical offset relocates each region to the fictional planet's local terrain datum. The offset is stored in the scene's region descriptor and does not multiply the relief. Boundaries blend into the surrounding world. This is an artistic relocation of real topography, not a geographic reconstruction of Earth.

Export pixel spacing is about **4.88 m / 2.44 m**, respectively. The source service is a mosaic with varying native resolution; those pixel spacings are not claims of survey accuracy or newly measured detail. Metadata preserve the exact request, source extent, height range, checksum, license link and modifications. USGS identifies 3DEP products as public domain in its [collection catalog](https://data.usgs.gov/datacatalog/data/USGS%3A3a81321b-c153-416f-98b7-cc8e5f0e17c3).

Both engines evaluate the same displaced geometry. A CPU height guide samples the same regional data to improve refinement around raised landforms and steep relief. The conforming quadtree now tracks its actual triangle cost using the closed mesh's topology, rather than conservatively stopping around two-thirds of the chosen budget. Budget and seam tests cover this change.

The close plant sampler reads a separate canonical-ground position attribute. Distant canopy geometry is excluded from this ground reference, so changing the canopy representation no longer changes where a plant's roots are sampled.

## 3. Less disruptive changes in detail

Explicit trees and the distant canopy envelope now use the same deterministic cell layout, density test, age choice and height variation. Their positions are tied to the world. The canopy is an approximation of those crowns rather than an independent noise field. Coarse terrain cells suppress crown displacement they cannot resolve, avoiding angular crown spikes on the horizon.

The lower tree LODs preserve source silhouettes through their atlases. Runtime grass footprints remain physical-sized: the old outer-ring widening has been removed. High and medium ground-detail spending is limited so nearby plants cannot consume every available triangle before distant cover is considered. Distance thresholds vary slightly by persistent cell identity, spreading representation changes across the population.

The review retains a **500,000 terrain-triangle cap**, a separate **5,000,000 expanded scatter-triangle cap**, and a **90,000 instance cap**. These are review settings, not consumer-hardware presets. The controls can lower them, and integration checks exercise smaller caps. The high-detail review is an offline-shot workflow; every scrub can require substantial CPU preparation.

## Verification outputs

- `realism_review.json`: actual geometry counts, ecology counts, achieved reach, preparation and render times.
- `realism_metrics.json`: paired engine differences, including foreground and center crops; whole-image averages are not perceptual identity claims.
- `realism_integration.json`: geometry/instance caps, physical footprints, revisit stability, canonical-crown agreement, regional evaluator agreement and complete authored path clearance checks.
- `path_repairs.json`: any review camera frames raised to remain above the revised terrain.
- `realism_comparison.jpg`: four views in Eevee and Cycles. The full PNGs are alongside it.

Reproduction tools are `prepare_realism_assets.py`, `fetch_regional_elevation.py`, `build_realism_review.py`, `repair_realism_paths.py`, `compare_realism.py`, and `tests/blender_realism.py`. Source preparation and downloads are not needed after installing the complete packaged add-on. Run the path repair after rebuilding this review because changed terrain can intersect the old camera paths. The repair affects this demonstration file, not arbitrary user cameras.

### Recorded checks

The Blender integration run passed all five geometry/instance caps, the lower-budget cases, identical revisited plant identities/positions, all **120** sampled canonical crown cells, and ground clearance on **1,200** authored path frames. Regional CPU/GN elevation evaluation differed by at most **0.56 m** in the sampled points; that includes finite-precision projection and local surface detail. The terrain unit tests also check closed seams and budget use. The packaged ZIP passed its CRC check.

Paired 1280×720 renders produced the following display-space RGB absolute differences. These are the current review views, not a controlled numeric before/after comparison with the older 960×540 scene.

| View | Whole-image mean difference | Foreground mean difference |
| --- | --- | --- |
| Forest | 5.88% | 5.97% |
| Grassland | 3.30% | 3.77% |
| Alpine | 0.34% | 0.61% |
| Canyon / Desert | 1.55% | 1.62% |

The forest has a significant indirect-light/shadow difference and does not meet the proposal's provisional 2% target. Its Cycles view is especially dark under the dense canopy. A calibrated lighting and foliage-transmission pass is still needed; this revision does not hide that difference by flattening surface lighting. At review quality, preparation took roughly **14–28 seconds per view** on the development machine, separate from the renderer's additional work. Freeze Living Geometry can be useful while planning a shot; refresh detail for the final camera.

## Limits that remain

The library is still limited, heightfield canopy is an approximation, and the crossed distant tree representation is not a full view-dependent volumetric model. Individual mesh LOD swaps remain discrete; population staggering is not a guarantee of invisible transitions during motion. Full animated transition review, wind/subframe guarantees, slope-aware ecological succession and collision avoidance remain further work.

The measured regions have finite extent and resolution. They do not supply centimeter cliff scans, overhangs, rivers, a global terrain-streaming system or unlimited detail. The existing ocean and atmosphere approach is retained; spectral water, breaking surf, physical cloud entry, improved indirect lighting and photographic material layering remain separate proposal stages.

Eevee and Cycles receive the same geometry and PBR data, but foliage lighting, shadows and reflections can still differ. The metrics disclose measured differences rather than promising identical images. Performance has only been tested on the available development hardware; 8/12/16 GB GPU qualification is outstanding.
