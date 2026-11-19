# Stage 0: reproduction check of the style handover

Command, in a fresh Blender 5.3.0 process on the M1 Pro, with `nice -n 10`:
`blender -b -P build.py -- --shot bedroom --samples 26 --out <scratch>/bedroom_repro.png` (built and rendered in 56 s;
the handover took 136 s on its Ryzen 7 5825U CPU).

Compared with the delivered `renders/raw/stop_bedroom.png` (1920 x 1080):

| Metric | Result |
|---|---|
| identical pixels | 47.1 % |
| mean absolute difference | 0.37 / 255 |
| largest difference | 40 / 255 (single pixels) |
| pixels off by more than 8 / 255 | 0.17 % |
| PSNR | 49.4 dB |

The difference image (`bedroom_repro_compare.png`, amplified 8x, git-ignored) shows only sampling noise along edges,
on the lattice screen and in the olive leaves. That is expected between Apple Silicon and the original AMD CPU (the
README says Cycles is bit-identical only on the same CPU type). Composition, light and materials match.
