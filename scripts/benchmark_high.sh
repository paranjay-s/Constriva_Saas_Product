#!/usr/bin/env bash
# High-quality benchmark for a GPU server (PART 2, E). Builds one plan, renders its High stills (Cycles, the style
# handover's look) and a short High tour, and prints seconds per still and per frame with the GPU in use.
#
#   scripts/benchmark_high.sh [JOB_PLAN_JSON] [OUT_DIR]
#
# Needs Blender 5.x on PATH (or BLENDER=...), node, ffmpeg and an NVIDIA GPU with OptiX/CUDA (nvidia-smi).
# Nothing here signs in anywhere or calls an AI. Estimates for an NVIDIA T4 (16 GB, the common cloud GPU) from
# the Apple M1 Pro measurements of this run are in docs/pro/SUMMARY.md ("Renderer measured").
set -euo pipefail
cd "$(dirname "$0")/.."
P3D=services/planto3d
BLENDER=${BLENDER:-blender}
PLAN=${1:-$P3D/examples/sample_plan.json}
OUT=${2:-/tmp/plan3d_bench}
mkdir -p "$OUT"
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader \
  | sed 's/^/GPU: /' || echo "GPU: none found (Cycles will use the CPU)"
echo "CPU: $(nproc 2>/dev/null || sysctl -n hw.ncpu) threads"
if [ ! -f "$PLAN" ]; then
  python3 $P3D/detect.py $P3D/examples/sample_plan.pdf "$OUT/plan.json" > /dev/null
  PLAN="$OUT/plan.json"
fi
t=$(date +%s)
"$BLENDER" -b --factory-startup -P $P3D/blender/gen.py -- "$PLAN" "$OUT" --quality high > "$OUT/build.log" 2>&1
echo "High build (with bake): $(( $(date +%s) - t )) s"
python3 $P3D/tools/still_shots.py "$OUT/meta.json" "$PLAN" "$OUT/shots.json" "$OUT/tour.json"
t=$(date +%s)
"$BLENDER" -b "$OUT/house_baked.blend" -P $P3D/blender/cinema.py -- "$OUT/tour.json" "$OUT/stills" \
  --shots "$OUT/shots.json" --look lantern --meta "$OUT/meta.json" --res 1920x1080 --samples 96 > "$OUT/stills.log" 2>&1
n=$(grep -c '^SHOT ' "$OUT/stills.log" || true)
echo "High stills: $n in $(( $(date +%s) - t )) s"
grep '^SHOT ' "$OUT/stills.log" | awk '{s+=$3; n++} END {if (n) printf "  %.1f s per still on average (render only)\n", s/n}'
node $P3D/tools/tour_cinema.mjs "$OUT/meta.json" "$OUT/tour_full.json" --seconds 10
t=$(date +%s)
"$BLENDER" -b "$OUT/house_baked.blend" -P $P3D/blender/cinema.py -- "$OUT/tour_full.json" "$OUT/tour" --frames \
  --start 0 --end 59 --res 1920x1080 --engine eevee > "$OUT/tour.log" 2>&1
echo "High tour (EEVEE 1080p): 60 frames in $(( $(date +%s) - t )) s"
t=$(date +%s)
"$BLENDER" -b "$OUT/house_baked.blend" -P $P3D/blender/cinema.py -- "$OUT/tour_full.json" "$OUT/tour_ultra" --frames \
  --start 0 --end 29 --res 1920x1080 --engine cycles --samples 64 > "$OUT/tour_ultra.log" 2>&1
echo "Ultra tour (Cycles 1080p, 64 samples): 30 frames in $(( $(date +%s) - t )) s"
