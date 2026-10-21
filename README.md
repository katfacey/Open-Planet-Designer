# Open Planet Designer

**1.3.0-beta.1 · Experimental Blender add-on · Tested in Blender 5.2.0 LTS**

Build editable procedural worlds in Blender, from orbital planets to bounded regions with real terrain and living surface geometry. Open Planet Designer combines rocky worlds, gas giants and stars with camera-adaptive terrain, instanced vegetation, geometric ocean waves, and artistic controls for atmosphere, clouds, rings and surface appearance.

[Download the beta](https://github.com/katfacey/Open-Planet-Designer/releases/tag/v1.3.0-beta.1) · [User guide](docs/REALISM_GUIDE.md) · [Expanded discussion and roadmap](docs/EXPANDED_DISCUSSION.md) · [AI disclosure](AI_DISCLOSURE.md)

## What the beta can do

- Create eleven world presets, including terrestrial, ocean, desert, ice, gas-giant and stellar examples.
- Displace actual terrain geometry shared by Eevee and Cycles. The supplied review includes bounded measured mountain and canyon regions.
- Reveal instanced trees, saplings, ferns, grass and rocks near the camera. Mature, young and dead tree forms use deterministic world-anchored placement.
- Reduce detail with configurable camera distances, terrain/scatter triangle budgets and instance limits. Distant tree representations derive from the corresponding source assets.
- Use a floating origin for close surface work, with separate controls for terrain, plants, waves and shadows.
- Animate existing world controls, cloud drift and geometric waves. Render in Eevee or Cycles using the shared scene data.

## Install

1. Download **Open-Planet-Designer-1.3.0-beta.1.zip** from the beta release. GitHub's automatic source ZIP does not include the large runtime assets.
2. In Blender, open **Preferences → Add-ons → Install from Disk**, select that ZIP, and enable **Open Planet Designer**.
3. In the 3D Viewport, press **N → Open Planet**. Choose a world and select **Create Planet**. The existing Terra demo operator provides a ready-to-render orbital scene.
4. For the latest surface example, download and open **Open-Planet-Designer-Beta-Demo.blend** from the same release. The file opens in Solid mode; press **F12** for the actual materials. Select Forest, Grassland, Alpine, Desert or Ocean with **Shot camera**. Rendering or refreshing high-detail geometry can take time.

The internal Python module remains `open_planet_lab` so existing saved scenes and operators remain compatible. UI branding is Open Planet Designer. Blender 5.0+ is targeted; this release has been tested in 5.2.0 LTS only.

## Current limits

This beta does not promise unlimited measured detail or completed photorealism. High-resolution terrain has finite coverage; heightfields do not supply overhangs. Atmospheric/cloud rendering remains an approximation, and the ocean is not a spectral surf simulation. Detail swaps can still pop during movement.

Eevee and Cycles share geometry and PBR inputs, but dense forest lighting still differs visibly. The four supplied 720p paired stills have whole-image display-RGB mean differences of 5.88% forest, 3.30% grassland, 0.34% alpine and 1.55% canyon. Those values measure image agreement, not photographic quality. See the [recorded checks](docs/REALISM_GUIDE.md#recorded-checks).

Development rendering used an RTX 5090. Consumer-GPU memory/performance tiers are not yet qualified. Triangle limits do not bound all texture memory, transparency or shadow cost. The demo caches geometry along one fixed descent route; it is not evidence that a full orbital-to-ground route is temporally seamless.

## Project goals

Develop convincing terrain, materials and ecosystems across orbital, aerial and ground views; preserve landscape identity through detail changes; improve foliage illumination and Eevee/Cycles agreement; build predictable caches and measured hardware presets; and extend atmospheric entry, ocean behavior and ecological placement. The [expanded discussion](docs/EXPANDED_DISCUSSION.md) records the research, completed structural priorities and remaining acceptance gates.

## Development and licensing

Run `python -m unittest discover -s tests -p "test_planet_*.py"` for the pure-Python terrain/ecology checks. Restore the release assets before using Blender generation tools. Saved integration results are in [docs/verification](docs/verification).

Code: [GPL-3.0-or-later](LICENSE). Bundled source assets: CC0 or public domain, with [provenance and notices](THIRD_PARTY_NOTICES.md). This project was developed with substantial AI assistance; read the [AI disclosure](AI_DISCLOSURE.md).

## Beta demo

**25 seconds, 1280 × 720 at 24 fps.** A one-second title card followed by a continuous 24-second descent from orbit into the grassland. Actual Eevee renders, with no cuts during the descent and no audio. Destination detail is prebuilt and held fixed for this bounded route; this is not a general terrain-streaming or animated-LOD qualification.

[Play or download the beta demo](https://github.com/katfacey/Open-Planet-Designer/releases/download/v1.3.0-beta.1/open-planet-designer-beta-demo.mp4).




https://github.com/user-attachments/assets/bdcb1475-ff9b-4f42-affd-67e9080836a2

