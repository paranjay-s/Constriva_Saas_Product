# Unreal Engine stills through the Movie Render Queue (C3.3)

Measured 2026-11-20 on the Apple M1 Pro (UE 5.8, Metal, on AC power, `nice -n 10`).

feat/pro's two attempts captured nothing: with `-unattended` the editor quit as soon as the capture script
returned. This time the render runs as its own command-line process that renders and exits by itself:

1. `tools/unreal/mrq_setup.py` in the editor (synchronous, `-unattended` is fine): loads `/Game/Maps/House` (the
   house imported by `import_render.py`, with its lights and a CineCameraActor per shot), saves a one-frame
   LevelSequence per camera with a camera cut, and a `MoviePipelinePrimaryConfig` (deferred pass, PNG,
   1920 x 1080, 4 spatial samples, 64 warm-up frames for Lumen). **49 s.**
2. `UnrealEditor HouseProto.uproject /Game/Maps/House -game -LevelSequence=/Game/Stills/Still_<camera>
   -MoviePipelineConfig=/Game/Stills/StillConfig -windowed -Unattended`: **74 s** for the living room (the
   pipeline itself 54 s), **29 s** for the front elevation, start-up included.

Total Unreal time 2.5 minutes of the 15-minute cap. Result: `room_living_ue.jpg`, `elevation_front_ue.jpg`.

What the pictures show (honestly): the stills are made, but this is still a prototype.
- The house is the one imported in feat/pro's run (3.05 m ceilings, before this run's tray ceilings and details).
- The picture is mirrored left to right against Blender's: `import_render.py` flips Y for the cameras, but
  Interchange already converts the glTF's axes, so the flip is wrong (one sign to change and re-import).
- The middle of the living room is overexposed (fixed exposure tuned by guess; no look pass yet).
- The output name template `{sequence_name}` came out empty (files renamed by hand).

Blender stays the default renderer (`PLAN3D_RENDERER=blender`); `server.py`'s Unreal path still uses the old
in-editor capture and should be switched to these two steps before anyone turns it on.
