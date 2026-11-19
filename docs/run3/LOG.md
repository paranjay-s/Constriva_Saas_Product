# Run 3 log (branch feat/run3 from feat/3d-night)
stage | task | status | commit | note
- 0 | preflight: docs/reference/ (incl. style/) git-ignored, nothing tracked; free disk 300 GB | done | - |
- 0 | power at start: on battery, 35%, discharging | note | - | no renders until charging (rule); non-render work first
- 0 | read handover README, CHECKS, ASSET_INVENTORY, build.py, after_batch.sh | done | - | no notes.md exists in any docs/reference folder (images only); room targets taken from images and the prompt's descriptions
- 0 | after_batch.sh | skipped | - | it calls a Windows .venv python and writes to scripts/final (inside the reference folder); not needed: build.py + lantern_scene.py cover it. Any batch output goes under docs/run3/ or scratch
