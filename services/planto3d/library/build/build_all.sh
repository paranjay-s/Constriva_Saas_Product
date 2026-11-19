#!/bin/bash
# Build the library pieces that are not built yet (one Blender process each), then write ../index.json. Runs under
# nice and stops starting new pieces after 9 minutes, so one batch counts as one render under the laptop rules; run
# it again (after the cooldown) for the rest. Logs go to build/out/.
#   bash build_all.sh [name ...]          FORCE=1 rebuilds pieces that exist
cd "$(dirname "$0")" || exit 1
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
mkdir -p out
names=("$@")
if [ ${#names[@]} -eq 0 ]; then
  names=($("$BLENDER" -b --factory-startup --python-expr "import sys; sys.path.insert(0, '.'); import pieces; print('NAMES', ' '.join(pieces.PIECES))" 2>/dev/null | grep '^NAMES' | cut -d' ' -f2-))
fi
t0=$(date +%s)
for n in "${names[@]}"; do
  if [ -z "$FORCE" ] && ls ../*/"$n"/entry.json >/dev/null 2>&1; then continue; fi
  if [ $(( $(date +%s) - t0 )) -gt 540 ]; then echo "batch time used: stopping before $n"; break; fi
  nice -n 10 "$BLENDER" -b --factory-startup -P make_library.py -- "$n" --samples 32 > "out/$n.log" 2>&1
  if grep -q "LIBRARY OK" "out/$n.log"; then echo "ok   $n"; else echo "FAIL $n: $(grep -E 'Error' "out/$n.log" | head -1)"; fi
done
/usr/bin/python3 index.py
