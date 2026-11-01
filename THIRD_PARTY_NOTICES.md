# Third-party assets and data

Project code is GPL-3.0-or-later. Third-party assets and the Godot engine retain their own licenses.

- Poly Haven models, textures and environment data: CC0 1.0. Sources are recorded in `open_planet_lab/assets/CREDITS.json` and `open_planet_lab/assets/ground/CREDITS.json`. See https://polyhaven.com/license and https://creativecommons.org/publicdomain/zero/1.0/.
- USGS 3DEP elevation: public domain. Export requests, physical dimensions, transformations, retrieval metadata and checksums are retained in `open_planet_lab/assets/terrain/` and its `regions/` directory. Native converted data retain those records in `godot/assets/native/regions.json`.
- The source-derived vegetation atlases and reduced models are modifications of the credited CC0 assets. Regional elevation is artistically relocated to a fictional planet; it is not a georeferenced Earth reconstruction.
- Earth woodland appearance maps (including Forest Ground 03 and Forest Leaves 02) and the retained pure-sky HDRI are Poly Haven CC0 assets. Original file URLs, physical scales and SHA-256 hashes are in `godot/assets/appearance/CREDITS.json` and the app's `source-credits/appearance.json`. Derived hybrid plant representations and the fixed-layout forest study retain their source records alongside them.
- Godot Engine: MIT, with its compiled third-party component notices. Native app/source archives include `GODOT_NOTICES.txt` generated from the pinned engine's license/copyright APIs. The native app's `source-credits/` directory contains the model, ground, catalogue and regional manifests.

Research links in the expanded discussion are references. Infinigen, Houdini and the linked research implementations are not bundled dependencies. Their licenses are not being relabeled CC0.

The archived Blender beta ZIP on GitHub Releases contains its binary assets. Native app and hydrated source archives contain their curated runtime assets; GitHub's automatic source ZIP contains manifests and code only. Preserve the corresponding complete package before running offline reconstruction scripts.
