# Rendered tour: engine benchmark (Stage 9)

Machine: Apple M1 Pro, 14-core GPU (Metal), Blender 5.3, on AC power, `nice -n 10`, 10-minute cap per render.
House: the dock house as rebuilt tonight (Low light maps). Clip: the first 9 s of the guided tour's route
(`tools/tour_cinema.mjs --seconds 8`), 30 fps, 854x480. Command: `scripts/benchmark_tour.sh JOB 8 854x480`.

| engine | frames done | time | per frame | full tour (244.8 s, 7,344 frames) at 480p |
|---|---|---|---|---|
| EEVEE | 197 of 197 | 409 s | 2.07 s | about 4.2 hours |
| Cycles, 64 samples, denoised | 103 of 197 (stopped by the 10-minute cap) | 600 s | 5.82 s | about 11.9 hours |

At 720p (High) and 1080p (Ultra) the times grow with the pixel count: roughly 2.3x and 5x the 480p figures.

What the frames show (frame 80 side by side: `style_compare/tour_engines_frame80.png`, videos
`tour_eevee_8s_480p.mp4` and `tour_cycles_3s_480p.mp4`, all git-ignored):
- Cycles renders the white plaster wall white-grey. EEVEE renders the same wall saturated blue: its lighting lets the
  dusk sky tint matte surfaces far too much. High (EEVEE) needs this fixed before it is good enough.
- The clip starts outside the front door with the camera close beside a wall. The guided tour's route is right for
  walking but too close to walls for a film; the film path needs keys set back from walls.

Conclusions:
- A full tour on this laptop is not practical at any quality: over 4 hours even with EEVEE at 480p. The pipeline renders
  in resumable chunks (PlanTo3D `run_tour`), so it can run on a GPU server or overnight, but the default product
  should be a short tour (about 60 s of the main rooms), or frames rendered at 15 fps with the in-between frames
  blended (`cinema.py --step 2`).
- Recommended: High = EEVEE once the blue cast is fixed; Ultra = Cycles on a GPU server only.
