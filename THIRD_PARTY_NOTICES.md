# Third-party assets and data

The add-on code is GPL-3.0-or-later. Third-party assets retain their own licenses.

- Poly Haven models, textures and environment data: CC0 1.0. Sources are recorded in `open_planet_lab/assets/CREDITS.json` and `assets/ground/CREDITS.json`. See https://polyhaven.com/license and https://creativecommons.org/publicdomain/zero/1.0/.
- USGS 3DEP elevation: public domain. Export requests, physical dimensions, transformations, retrieval metadata and checksums are retained in `assets/terrain/` and `assets/terrain/regions/`.
- The source-derived vegetation atlases and reduced models are modifications of the credited CC0 assets. Regional elevation is artistically relocated to a fictional planet; it is not a georeferenced Earth reconstruction.

Research links in the expanded discussion are references. Infinigen, Houdini and the linked research implementations are not bundled dependencies. Their licenses are not being relabeled CC0.

Binary libraries, texture maps and atlases are distributed in the full installable beta ZIP on GitHub Releases. The source repository keeps their manifests; install/hydrate the full asset set before running scene-generation scripts.
