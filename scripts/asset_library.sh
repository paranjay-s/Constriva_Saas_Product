#!/usr/bin/env bash
# The 3D asset library (services/planto3d/library) and the CC0 assets (services/planto3d/assets): rebuild, pack,
# copy or check them for a server (PART 3).
#
#   scripts/asset_library.sh rebuild              build every library piece not built yet, batch after batch, then the index
#   scripts/asset_library.sh pack OUT.tar.gz      library + assets into one archive (to copy to a server)
#   scripts/asset_library.sh unpack IN.tar.gz     unpack such an archive into services/planto3d
#   scripts/asset_library.sh copy USER@HOST:DIR   rsync library + assets to a server's PlanTo3D folder
#   scripts/asset_library.sh check                manifest and licences (tests/test_assets.py) and the library index
#
# BLENDER=... picks Blender (default: the macOS app, else `blender` on PATH). COOL_S=120 pauses between rebuild
# batches (laptops; 0 on a server). Each batch runs at most 9 minutes (library/build/build_all.sh).
set -euo pipefail
cd "$(dirname "$0")/../services/planto3d"
if [ -z "${BLENDER:-}" ]; then
  if [ -x /Applications/Blender.app/Contents/MacOS/Blender ]; then BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
  else BLENDER=$(command -v blender || true); fi
fi
export BLENDER
PY=${PYTHON:-python3}
case "${1:-}" in
  rebuild)
    for i in $(seq 1 30); do
      out=$(bash library/build/build_all.sh 2>&1); echo "$out"
      echo "$out" | grep -q "stopping before" || break
      sleep "${COOL_S:-0}"
    done
    "$PY" library/build/index.py
    ;;
  pack)
    tar -czf "${2:?archive path}" library assets
    ls -la "$2"
    ;;
  unpack)
    tar -xzf "${2:?archive path}" -C .
    "$0" check
    ;;
  copy)
    rsync -a --delete --info=stats1 library assets "${2:?user@host:/path/to/planto3d}"/
    ;;
  check)
    "$PY" tests/test_assets.py
    "$PY" -c "import json; e=json.load(open('library/index.json'))['entries']; print(len(e), 'library entries')"
    ;;
  *)
    sed -n 2,13p "$0"; exit 2
    ;;
esac
