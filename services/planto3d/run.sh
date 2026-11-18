#!/usr/bin/env bash
# Start PlanTo3D: http://127.0.0.1:8080 (pass --port / --host / --cors to change). The home page reports anything missing.
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "install Python 3.9 or newer"; exit 1; }
[ -d node_modules/three ] || npm install || echo "npm install failed: the 3D viewer needs node_modules/three"
exec python3 server.py "$@"
