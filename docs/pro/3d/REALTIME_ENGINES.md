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

Apple M1 Pro (10 CPU cores, 16-core GPU, 32 GB), on AC power, `nice -n 10`, 2 minutes between stills:

| Renderer | What | Time |
|---|---|---|
| Blender Cycles (Metal GPU), the handover look, 1920 x 1080, 96 adaptive samples, denoised | 13 room stills, evening | 98-119 s each, 108 s on average |
| same | 4 elevations, evening / day | 21-27 s / 17-22 s each |
| same | 2 room stills by day | 73-78 s each |
| fast tour from the stills (CPU, NumPy) | 17 shots -> 51.5 s at 1080p | 12 s depth + 5.6 min film |
| Unreal Engine 5.8 (Lumen) | glTF import and scene | 20 s import (523 assets), 299 meshes, editor start about 3 min |
| Unreal Engine 5.8 | living room and front elevation stills | not made: the editor quit before the capture (two attempts, see LOG.md) |

**Default renderer: Blender**, by measurement and by what can be measured: it renders every still headless on
the same machine as the builds, with the reference look, in about 110 s per room on this laptop (a server GPU is
several times faster; `scripts/benchmark_high.sh`). Unreal gives no measured still yet, needs a windowed editor on
a GPU and the Unreal seat subscription for a company above USD 1 M revenue. It stays behind
`PLAN3D_RENDERER=unreal`.

Rough estimates for an NVIDIA T4 (16 GB, the common cloud GPU), assuming it renders Cycles 1.5-2x as fast as this
M1 Pro on Metal (an assumption, not a measurement or a looked-up benchmark): a room still 55-75 s, an elevation
12-18 s, a 15-room villa about 20 minutes for the evening set. Run `scripts/benchmark_high.sh` on the server for
real numbers.

## Sources

- [Unreal Engine, Twinmotion and RealityCapture pricing update](https://www.unrealengine.com/en-US/blog/we-are-updating-unreal-engine-twinmotion-and-realitycapture-pricing-in-late-april)
- [Unreal Engine EULA](https://www.unrealengine.com/en-US/eula) and [EULA change log](https://www.unrealengine.com/en-US/eula-change-log/unreal)
- [Twinmotion licence FAQ](https://www.twinmotion.com/en-US/license); [third-party 2026 pricing guide](https://www.renderahouse.com/blog/twinmotion-pricing)
- [Pixel Streaming reference](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-pixel-streaming-reference); [getting started](https://dev.epicgames.com/documentation/en-us/unreal-engine/getting-started-with-pixel-streaming-in-unreal-engine); [Mac build report](https://forums.unrealengine.com/t/cant-build-cross-platform-project-that-uses-pixelstreaming-on-mac/758336)
