#!/usr/bin/env bash
# Set up the PlanTo3D service (services/planto3d): Blender, poppler, Node and ffmpeg, the
# three.js viewer library, and the CC0 textures and models (about 75 MB, into
# services/planto3d/assets, which is never committed).
#
#   scripts/setup_planto3d.sh            install what is missing, then check
#   scripts/setup_planto3d.sh --check    only say what is installed and what is missing
#
# macOS uses Homebrew. Debian and Ubuntu use apt (asks for sudo). Blender on Linux: install
# a build from blender.org and set BLENDER to it if the snap cannot read your project folder.
set -euo pipefail
cd "$(dirname "$0")/../services/planto3d"
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

blender_path() {
  if [ -n "${BLENDER:-}" ] && [ -x "$BLENDER" ]; then echo "$BLENDER"; return; fi
  command -v blender 2>/dev/null && return
  for p in /Applications/Blender.app/Contents/MacOS/Blender "$HOME/Applications/Blender.app/Contents/MacOS/Blender"; do
    [ -x "$p" ] && { echo "$p"; return; }
  done
  return 1
}
have() { command -v "$1" >/dev/null 2>&1; }

missing=()
have python3 || missing+=(python3)
have node || missing+=(node)
{ have pdftocairo && have pdftotext && have pdfinfo; } || missing+=(poppler)
have ffmpeg || missing+=(ffmpeg)
blender_path >/dev/null || missing+=(blender)

if [ "${#missing[@]}" -gt 0 ] && [ "$CHECK_ONLY" -eq 0 ]; then
  echo "Installing: ${missing[*]}"
  if [ "$(uname)" = "Darwin" ]; then
    have brew || { echo "Homebrew is needed on macOS: https://brew.sh"; exit 1; }
    for m in "${missing[@]}"; do
      case "$m" in
        blender) brew install --cask blender ;;
        python3) brew install python ;;
        *) brew install "$m" ;;
      esac
    done
  elif have apt-get; then
    pkgs=()
    for m in "${missing[@]}"; do
      case "$m" in
        poppler) pkgs+=(poppler-utils) ;;
        node) pkgs+=(nodejs npm) ;;
        *) pkgs+=("$m") ;;
      esac
    done
    sudo apt-get update && sudo apt-get install -y "${pkgs[@]}"
  else
    echo "Install these yourself, then run this script again: ${missing[*]}"; exit 1
  fi
fi

if [ "$CHECK_ONLY" -eq 0 ]; then
  [ -d node_modules/three ] || npm install --no-audit --no-fund
  python3 fetch_assets.py          # skips what is already on disk
fi

BL="$(blender_path || true)"
echo
echo "PlanTo3D setup"
printf '  %-10s %s\n' python3 "$(python3 --version 2>&1 || echo MISSING)"
printf '  %-10s %s\n' node "$(node --version 2>/dev/null || echo MISSING)"
printf '  %-10s %s\n' poppler "$(pdftocairo -v 2>&1 | head -1 || echo MISSING)"
printf '  %-10s %s\n' ffmpeg "$(ffmpeg -version 2>/dev/null | head -1 | cut -d' ' -f1-3 || echo MISSING)"
printf '  %-10s %s\n' blender "${BL:-MISSING} $([ -n "$BL" ] && "$BL" --version 2>/dev/null | head -1)"
printf '  %-10s %s\n' three.js "$([ -f node_modules/three/build/three.module.js ] && echo installed || echo MISSING)"
printf '  %-10s %s\n' materials "$(python3 -c 'import fetch_assets; m = fetch_assets.missing(); print("complete" if not m else "MISSING: " + ", ".join(m))')"
echo
echo "Start it with scripts/run_planto3d.sh, then open /health/deep on the API."
