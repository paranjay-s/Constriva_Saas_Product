#!/bin/bash
# Benchmark the rendered tour engines on one built house: the same short clip with EEVEE and with Cycles, under the
# laptop rules (nice, at most 10 minutes per render, 2 minutes' cooldown between renders).
#   scripts/benchmark_tour.sh JOB_DIR [SECONDS=8] [RES=854x480] [OUT_DIR]
# JOB_DIR is a PlanTo3D job folder with house.blend and meta.json. Prints seconds per frame per engine and what the
# full tour would take; writes OUT_DIR/<engine>/frames and, when ffmpeg is installed, OUT_DIR/<engine>.mp4.
set -euo pipefail
JOB=${1:?job folder}; SECONDS_=${2:-8}; RES=${3:-854x480}
OUT=${4:-$(mktemp -d -t tourbench)}
HERE="$(cd "$(dirname "$0")/.." && pwd)"; P3D="$HERE/services/planto3d"
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
CAP=${CAP:-600}; COOL=${COOL:-120}
mkdir -p "$OUT"
node "$P3D/tools/tour_cinema.mjs" "$JOB/meta.json" "$OUT/clip.json" --seconds "$SECONDS_"
node "$P3D/tools/tour_cinema.mjs" "$JOB/meta.json" "$OUT/full.json" | tee "$OUT/full.txt"
FULL=$(awk '{for (i = 1; i <= NF; i++) if ($i == "about") print $(i + 1)}' "$OUT/full.txt")
first=1
for ENGINE in eevee cycles; do
  [ $first = 1 ] || { echo "cooling down ${COOL}s"; sleep "$COOL"; }
  first=0
  t0=$(date +%s)
  perl -e 'alarm shift; exec @ARGV' "$CAP" nice -n 10 "$BLENDER" -b "$JOB/house.blend" -P "$P3D/blender/cinema.py" -- \
    "$OUT/clip.json" "$OUT/$ENGINE" --frames --res "$RES" --engine "$ENGINE" > "$OUT/$ENGINE.log" 2>&1 || true
  secs=$(( $(date +%s) - t0 ))
  n=$(ls "$OUT/$ENGINE/frames" 2>/dev/null | grep -c "\.jpg$" || true)
  if [ "$n" -gt 0 ]; then
    per=$(echo "scale=2; $secs / $n" | bc)
    est=$(echo "scale=0; $per * $FULL * 30 / 60" | bc)
    echo "$ENGINE: $n frames in ${secs}s = ${per}s per frame at $RES; the full tour (${FULL}s) would take about ${est} min"
    if command -v ffmpeg >/dev/null; then
      ffmpeg -loglevel error -y -framerate 30 -pattern_type glob -i "$OUT/$ENGINE/frames/f_*.jpg" -c:v libx264 \
        -pix_fmt yuv420p "$OUT/$ENGINE.mp4" && echo "  video: $OUT/$ENGINE.mp4"
    fi
  else
    echo "$ENGINE: no frame rendered in ${secs}s (see $OUT/$ENGINE.log)"
  fi
done
