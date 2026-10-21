# Development

The internal add-on package remains `open_planet_lab` for compatibility with existing saved files. Public branding is Open Planet Designer. The release is 1.3.0-beta.1; Blender's numeric add-on version is `(1, 3, 0)`.

## Source and assets

Clone the repository, download the complete add-on release ZIP, and run:

```text
python tools/restore_assets.py /path/to/Open-Planet-Designer-1.3.0-beta.1.zip --sha256 CHECKSUM_FROM_RELEASE
python -m unittest discover -s tests -p "test_planet_*.py"
```

The source package requires Blender's `bpy`. Pure-Python tests do not require Blender. Asset preparation/data scripts may additionally require NumPy, Pillow and network access. Scene generation is an offline workflow and can take substantial time.

The prepared source libraries retain Poly Haven source assets and derived LODs. Runtime assets do not need to be downloaded separately after installing the complete release ZIP. Rebuilding source libraries is a distinct operation and requires the original downloads listed in the manifests.

## Existing authoring tools

Tools retain the original authoring paths for reproducibility. Place the current beta example at `output/planets/realism/Open_Planet_Realism_Priorities.blend` when using `render_planet_descent.py`. `build_realism_review.py` expects an earlier saved baseline and is an implementation record, not a one-command clean-checkout build.

The public demo has a one-second intro plus a continuous 576-frame descent at 24 fps (25 seconds total). `tools/render_planet_descent.py` resolves the destination terrain/scatter once, holds the detail camera fixed, then moves the actual render camera continuously from orbit to 2.2 m above the grassland. Sky weight and camera clipping follow the moving camera. This bounded route cache avoids repeated retessellation; it does not qualify general streaming or invisible dynamic LOD transitions.

## Validation records

`docs/verification/` contains the recorded integration, terrain/instance, camera-clearance and paired-render reports. The broad photorealism proposal intentionally has stricter gates than this beta passes. Treat unimplemented roadmap items as research directions, not supported product features.
