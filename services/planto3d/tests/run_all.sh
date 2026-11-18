#!/usr/bin/env bash
# detector on the sample drawing (and on the private fixtures when present), furniture clashes on the sample and on
# every detected plan, stair / wall walking and every opening against its plan on every built house.
# The browser test is separate: tests/test_site.mjs
cd "$(dirname "$0")/.."
set -e
python3 tests/test_sample.py
python3 tests/test_detect.py
python3 tests/test_doorway.py
python3 tests/test_reader.py
python3 tests/test_rooms.py
python3 detect.py examples/sample_plan.pdf /tmp/planto3d_sample.json > /dev/null
for p in /tmp/planto3d_sample.json jobs/*/plan.json; do
  [ -f "$p" ] || continue
  out=$(python3 furnish.py "$p")
  echo "$out" | grep -q CLASH && { echo "$p"; echo "$out"; exit 1; } || echo "no furniture clashes: $p"
done
for m in jobs/*/meta.json; do [ -f "$m" ] && node tests/test_walk.mjs "$m"; done
for m in jobs/*/meta.json; do [ -f "$m" ] && node tests/test_storeys.mjs "$m"; done
for m in jobs/*/meta.json; do [ -f "$m" ] && node tests/test_water.mjs "$m"; done
for m in jobs/*/meta.json; do [ -f "$m" ] && node tests/test_openings.mjs "$(dirname "$m")"; done
echo ALL PASS
