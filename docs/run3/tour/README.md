# Tour: still-plus-depth (handover) against the EEVEE tour (today's High)

Same house (the dock house, Low build with the sand scheme), same Blender scene (`house_baked.blend` through
`blender/cinema.py`), same cameras: two interior shots (living area, kitchen) at 1280x720 on this Mac (M1 Pro, Metal).
Picture: `eevee_vs_cycles_interiors.png` (git-ignored); left EEVEE, right Cycles.

| | EEVEE (High tour today) | Cycles still (input of a still-plus-depth tour) |
|---|---|---|
| time per 1280x720 image | 4-6 s (32 samples) | 31-34 s (64 spp, denoised) |
| look | flat grey ceilings, cool and even | warm bounce light from the lamps on ceilings and walls; reads as a lit room |

Estimated for a tour the length of the handover's (421 frames at 30 fps, about 14 s):

- EEVEE, every frame rendered: about 421 x 5 s = 35 min (the last EEVEE tour of this house measured 3.3 s a frame at
  854x480).
- Still-plus-depth (handover method: 8 finished stills, each with a world-position pass; per-room dolly of 0.4-1.7 m by
  forward splatting with far-side hole filling; 60-frame segments with cross-dissolves): 8 x 33 s + 8 position passes
  (a few seconds each) + the warp (well under a second a frame) = about 6-7 min, and every frame has Cycles light.

What was not measured: the warp itself was not built, so the artefacts it makes where the camera sees behind an
object (disocclusion) and how far a dolly can go before they show are the handover's numbers, not ours. The motion is
limited to short moves inside each room joined by dissolves; it is not a walk from room to room.

Recommendation: build the still-plus-depth tour for High (about 5x faster and better lit than EEVEE at the same size)
and keep Ultra as a true Cycles animation, as the spec says. Decide whether High's motion (short dollies and
dissolves instead of one continuous glide) is acceptable to the firm first: that is the trade.
