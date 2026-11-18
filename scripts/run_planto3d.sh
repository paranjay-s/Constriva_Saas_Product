#!/usr/bin/env bash
# Run the PlanTo3D service for this app: on 127.0.0.1 only, with no CORS.
#
#   scripts/run_planto3d.sh              http://127.0.0.1:8080
#   PLAN3D_PORT=8090 scripts/run_planto3d.sh
#
# PlanTo3D has no login. It must never be reachable from another machine: browsers reach
# it only through our backend (/api/v1/3d), which signs users in and checks ownership.
# That is why this script accepts no --host and no --cors. If you change the port, set
# PLAN3D_SERVICE_URL for the backend to match.
set -euo pipefail
cd "$(dirname "$0")/../services/planto3d"
for arg in "$@"; do
  case "$arg" in
    --host|--cors) echo "run_planto3d.sh always binds 127.0.0.1 and never enables CORS."; exit 2 ;;
    # developers: the review page (opened directly at http://127.0.0.1:<port>/web/edit.html?job=<id>) offers
    # "Save as reference", which writes the corrected plan to docs/reference/truth/ (git-ignored)
    --dev) export PLAN3D_TRUTH_DIR="$(cd ../.. && pwd)/docs/reference/truth" ;;
  esac
done
if [ -z "${BLENDER:-}" ] && ! command -v blender >/dev/null 2>&1; then
  for p in /Applications/Blender.app/Contents/MacOS/Blender "$HOME/Applications/Blender.app/Contents/MacOS/Blender"; do
    [ -x "$p" ] && export BLENDER="$p" && break
  done
fi
[ -d node_modules/three ] || { echo "Run scripts/setup_planto3d.sh first."; exit 1; }
exec python3 server.py --host 127.0.0.1 --port "${PLAN3D_PORT:-8080}"
