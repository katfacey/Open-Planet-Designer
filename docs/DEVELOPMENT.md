# Development

## Primary target: Godot

Develop the runtime and deployment in Godot. The [implementation plan](GODOT_IMPLEMENTATION_PLAN.md) is the canonical sequence and acceptance checklist. The current native alpha implements the first profiling/export, coordinate/provider and terrain/ecosystem streaming pass; see [the native guide and checks](GODOT_NATIVE_DEVELOPMENT.md). The [frozen import](GODOT_IMPORT.md) remains a separate reference mode.

Open `godot/project.godot` with the pinned Godot 4.7.2 build and press F5. See [project instructions](../godot/README.md) for controls, inherited working scenes and launch scripts. The installed .NET editor can run this GDScript project; the project does not require C#.

Generated content and `.godot` caches are excluded from Git. A complete local migration project ZIP includes the generated assets, notices and credit manifests. GitHub's automatic source ZIP does not. To reconstruct the import from the complete packed Blender review/source asset set:

```text
blender --background --factory-startup --python-exit-code 1 --python tools/export_godot.py -- --source PATH_TO_PACKED_REVIEW.blend
python tools/validate_godot_export.py --source PATH_TO_PACKED_REVIEW.blend
godot --headless --path godot --editor --import --quit
```

On Windows, `tools/check_godot_import.ps1 -GodotPath PATH_TO_GODOT` renders the five raw imports and creates generated native scene snapshots. `-Reload` checks the inherited working scenes. **Snapshot creation replaces generated `.scn` files**; preserve user working scenes and any changes to generated resources before rebuilding. `python tools/package_godot.py` packages the editable project and generated content. It does not export a standalone application.

The first native batch now runs independently of Blender/Python in an exported Windows application. Use `prepare_godot_regions.py`, `prepare_godot_catalog.py`, `write_native_fixtures.py`, native test scripts and `export_godot_runtime.ps1` as described in the native guide. `package_godot_runtime.py` creates the app ZIP and hydrated native source ZIP; `package_godot.py` remains the older full frozen-import packager. Keep offline conversion dependencies outside the deployed application. Qualify matching export templates and new GPU/shader APIs before depending on them.

Retain `python -m unittest discover -s tests` as portable reference coverage while adding native Godot tests for ported algorithms. Python tests alone do not validate native shaders, rendering, threads or exported builds. Record actual hardware, cold/warm conditions, memory and moving-route results; do not promote stationary RTX 5090 measurements into consumer-tier claims.

## Preserved Blender source and assets

The internal add-on package remains `open_planet_lab` for saved-file compatibility. The public Blender release remains 1.3.0-beta.1. Preserved development is 1.4.0-dev, with Blender numeric version `(1, 4, 0)`, the optional Blender 5.2+ [daylight/ground pass](DAYLIGHT_GROUND_DEVELOPMENT.md) and [foliage follow-up](FOLIAGE_DEVELOPMENT.md). The latter's local package is `1.4.0-dev.2`; it does not replace the public beta.

These tools remain available for asset authoring/export, regression fixtures and diagnostic reference renders. Eevee/Cycles parity and Blender probe-workflow expansion are no longer active product milestones. Their unresolved visual problems remain in the Godot plan.

Clone the repository, download the complete add-on release ZIP, and run:

```text
python tools/restore_assets.py /path/to/Open-Planet-Designer-1.3.0-beta.1.zip --sha256 CHECKSUM_FROM_RELEASE
python -m unittest discover -s tests
```

The source package requires Blender's `bpy`. Pure-Python tests do not require Blender. Asset preparation/data scripts may additionally require NumPy, Pillow and network access. Scene generation is an offline workflow and can take substantial time.

The prepared source libraries retain Poly Haven source assets and derived LODs. Runtime assets do not need to be downloaded separately after installing the complete release ZIP. Rebuilding source libraries is a distinct operation and requires the original downloads listed in the manifests.

## Historical authoring tools and demo

Tools retain the original authoring paths for reproducibility. Place the current beta example at `output/planets/realism/Open_Planet_Realism_Priorities.blend` when using `render_planet_descent.py`. `build_realism_review.py` expects an earlier saved baseline and is an implementation record, not a one-command clean-checkout build.

The public demo has a one-second intro plus a continuous 576-frame descent at 24 fps (25 seconds total). `tools/render_planet_descent.py` resolves the destination terrain/scatter once, holds the detail camera fixed, then moves the actual render camera continuously from orbit to 2.2 m above the grassland. Sky weight and camera clipping follow the moving camera. This bounded route cache avoids repeated retessellation; it does not qualify general streaming or invisible dynamic LOD transitions.

## Validation records

`docs/verification/` contains the recorded integration, terrain/instance, camera-clearance and paired-render reports. The broad photorealism proposal intentionally has stricter gates than this beta passes. Treat unimplemented roadmap items as research directions, not supported product features.
