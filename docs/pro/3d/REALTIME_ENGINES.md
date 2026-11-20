# Real-time engines for High quality (PART 2, E)

Written 2026-11-20. Question: should High stills and tours come from Blender (Cycles, EEVEE) or from a real-time
engine (Unreal Engine 5, Twinmotion), and how would the web walkthrough be streamed? No account was signed in to;
Unreal Engine 5.8 was already installed on this Mac (`/Users/Shared/Epic Games/UE_5.8`, 41 GB).

## Options

| Engine | Picture | Automation | Server | Licence for us |
|---|---|---|---|---|
| Blender 5.3 Cycles (current High stills) | path traced, the style handover's look (look.py) | full Python, headless (`blender -b`), one process per job | Linux + NVIDIA (OptiX) or CPU; already in the Dockerfile | GPL, run as a separate process; our scripts and output are ours |
| Blender EEVEE (current High tours) | rasterised with screen-space ray tracing; fast | same | needs a GPU | same |
| Unreal Engine 5 (Lumen, Path Tracer, Movie Render Queue) | real-time GI (Lumen); MRQ adds anti-aliasing samples and the path tracer | Python in the editor, MRQ from the command line; no headless mode without a GPU | Windows or Linux with an NVIDIA GPU; the editor and its shader cache are tens of GB | Epic EULA: rendered video and stills are "non-engine products" with no royalty; non-game companies above USD 1 M revenue need the seat subscription (USD 1,850 per seat per year announced in 2024); an app that ships Engine code to clients (e.g. a packaged walkthrough) pays royalties like a game |
| Twinmotion | Unreal-based, presets for architecture | almost none (no headless batch API) | desktop app | free under USD 1 M annual revenue, a paid seat above (USD 445 per year per third-party guides; not on Epic's own page in our search); no longer part of the Unreal subscription from 2026-05-27 |
| three.js (current walkthrough) | baked light maps, real-time in any browser | ours | static files | MIT |

## Interchange

`blender/export_engine.py` writes the built house as glTF 2.0 (.glb, no Draco, textures inside, every transform
applied so meshes sit at the origin) and USD (.usdc). Nandu villa: 62 MB glb, 6 MB usdc, 3 s. Unreal imports the
glb through Interchange (`tools/unreal/import_render.py`) and the usdc through its USD Importer plugin.

## Pixel Streaming

Pixel Streaming 2 streams an Unreal app to a browser over WebRTC. Epic's reference lists Windows and Ubuntu (and
a tested macOS version) but hardware encoding needs NVIDIA NVENC or AMD AMF; community reports say the Mac build
excludes the encoders, so it is not run here. Setup for a GPU server is in `docs/deploy-3d.md` ("Pixel Streaming,
off by default"); the plugin is disabled in `tools/unreal/HouseProto/HouseProto.uproject`. Cost: one GPU per
concurrent viewer session (or a few with a large GPU), against zero for the three.js walkthrough, which stays the
default.

## Measured

See "Renderer measured" in [../SUMMARY.md](../SUMMARY.md); the per-still times and hardware are filled in from the
runs of this stage.

## Sources

- [Unreal Engine, Twinmotion and RealityCapture pricing update](https://www.unrealengine.com/en-US/blog/we-are-updating-unreal-engine-twinmotion-and-realitycapture-pricing-in-late-april)
- [Unreal Engine EULA](https://www.unrealengine.com/en-US/eula) and [EULA change log](https://www.unrealengine.com/en-US/eula-change-log/unreal)
- [Twinmotion licence FAQ](https://www.twinmotion.com/en-US/license); [third-party 2026 pricing guide](https://www.renderahouse.com/blog/twinmotion-pricing)
- [Pixel Streaming reference](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-pixel-streaming-reference); [getting started](https://dev.epicgames.com/documentation/en-us/unreal-engine/getting-started-with-pixel-streaming-in-unreal-engine); [Mac build report](https://forums.unrealengine.com/t/cant-build-cross-platform-project-that-uses-pixelstreaming-on-mac/758336)
