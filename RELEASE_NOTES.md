# Open Planet Designer 1.3.0 Beta 1

An experimental Blender add-on for editable procedural worlds, real displaced terrain, living surface geometry and camera-adaptive detail.

This beta introduces more varied forest ages/forms, bounded measured mountain and canyon terrain, source-derived distant trees, fixed-size grass across detail levels, and improved terrain/scatter budgeting. The expanded discussion records the completed structural priorities and the remaining research and visual goals.

## Downloads

- **Open-Planet-Designer-1.3.0-beta.1.zip**: complete installable add-on, including runtime assets and licenses. Install this ZIP directly in Blender; keep its `open_planet_lab` module folder intact.
- **Open-Planet-Designer-Beta-Demo.blend**: packed example scene with five shot cameras. Opens in Solid mode for responsiveness; press F12 to render. Install the add-on for creation controls and adaptive updates.
- **open-planet-designer-beta-demo.mp4**: 25-second beta demo at 1280 × 720, 24 fps, H.264: one-second intro, then a continuous 24-second orbit-to-grassland descent. No audio. Geometry is cached for that route.
- **SHA256SUMS.txt**: checksums for the distributed files.

GitHub's automatically generated source archives contain code and manifests, not the large runtime libraries. Use the complete add-on ZIP above for installation.

## Tested scope and remaining work

Tested with Blender 5.2.0 LTS on RTX 5090 development hardware. Geometry budgets, stable placements, terrain seams and the 1,200 authored descent-path frame clearances passed their recorded checks. The movie shows one bounded continuous descent with cached geometry; it does not qualify dynamic LOD changes or other routes and hardware.

Dense foliage still shows material/lighting differences between Eevee and Cycles. Photorealism, smooth animated LOD transitions, smaller-GPU qualification, more physical atmosphere/clouds and richer ocean behavior remain goals. Detailed terrain has finite coverage and resolution.

Developed with substantial AI assistance from OpenAI Codex; see [AI_DISCLOSURE.md](https://github.com/katfacey/Open-Planet-Designer/blob/main/AI_DISCLOSURE.md). Code is GPL-3.0-or-later. Bundled assets retain their CC0/public-domain provenance and notices.
