"""Unreal Engine 5 prototype (PART 2, E; PATCHES 58): import a built house and render the High still cameras.

Run inside the editor (no sign-in is needed for a local project; never log in to anything for this):

    UnrealEditor tools/unreal/HouseProto/HouseProto.uproject -ExecutePythonScript="tools/unreal/import_render.py" \
        -stdout -FullStdOutLogOutput -nosplash -windowed -ResX=640 -ResY=360

Measured on the M1 Pro (2026-11-20, UE 5.8): the import and the scene work (62 MB glb: 523 assets in 20 s, 299
meshes placed, lights, post-process volume and both cameras); with -unattended the editor quit three frames after
the script returned, before the capture (QUIT_EDITOR), so no Unreal still was made. Without -unattended the
editor should keep ticking until the script quits it; not yet verified (stopped after two attempts, LOG.md).

Environment (paths are absolute):
    PLAN3D_UE_GLB     the house from blender/export_engine.py (house_engine.glb, world-space meshes)
    PLAN3D_UE_SHOTS   shots.json from tools/still_shots.py (feet, Blender axes)
    PLAN3D_UE_OUT     where the PNG stills go
    PLAN3D_UE_ONLY    comma-separated shot names to render (default: room_living,elevation_front)
    PLAN3D_UE_MODE    evening (default) or day

What it does: a new empty level; the glTF imported through Interchange into /Game/House and every static mesh placed
at the origin; a sun (low in the west for the evening, high for the day), sky atmosphere, a real-time sky light,
height fog and an unbound post-process volume (Lumen GI and reflections, fixed exposure, AgX-like filmic tonemapper);
a CineCameraActor per shot (Blender metres -> Unreal centimetres, Y flipped: Unreal is left-handed); then each
camera is rendered with a high-resolution screenshot after the frames needed for Lumen to settle, and the editor
quits. Times per still are printed as "UE STILL <name> <seconds>".
"""

import json
import os
import time

import unreal

GLB = os.environ["PLAN3D_UE_GLB"]
SHOTS = json.load(open(os.environ["PLAN3D_UE_SHOTS"]))
OUT = os.environ.get("PLAN3D_UE_OUT", "/tmp/ue_stills")
ONLY = os.environ.get("PLAN3D_UE_ONLY", "room_living,elevation_front").split(",")
MODE = os.environ.get("PLAN3D_UE_MODE", "evening")
FT_CM = 30.48
SETTLE_FRAMES = 90          # frames rendered before each capture, for Lumen and the virtual shadow maps
os.makedirs(OUT, exist_ok=True)
log = unreal.log

# ------------------------------------------------------------------ level and import
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
les.new_level("/Game/Maps/House")
task = unreal.AssetImportTask()
task.filename = GLB
task.destination_path = "/Game/House"
task.automated = True
task.save = True
task.replace_existing = True
t0 = time.time()
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
log(f"UE IMPORT {time.time() - t0:.1f}s, {len(task.imported_object_paths)} assets")
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
meshes = [unreal.load_asset(p) for p in task.imported_object_paths]
meshes = [m for m in meshes if isinstance(m, unreal.StaticMesh)]
for m in meshes:
    a = eas.spawn_actor_from_object(m, unreal.Vector(0, 0, 0))
    a.set_actor_label(m.get_name())
log(f"UE PLACED {len(meshes)} meshes")

# ------------------------------------------------------------------ light
sun = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 1000))
pitch, yaw = (-6.0, 180.0) if MODE == "evening" else (-45.0, 135.0)
sun.set_actor_rotation(unreal.Rotator(0.0, pitch, yaw), False)
sl = sun.get_component_by_class(unreal.DirectionalLightComponent)
sl.set_intensity(4.0 if MODE == "evening" else 10.0)
sl.set_light_color(unreal.LinearColor(1.0, 0.62, 0.38, 1.0) if MODE == "evening" else unreal.LinearColor(1, 0.97, 0.92, 1))
try:
    sl.set_editor_property("atmosphere_sun_light", True)
except Exception:
    pass
eas.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0))
sky = eas.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 500))
skc = sky.get_component_by_class(unreal.SkyLightComponent)
skc.set_editor_property("real_time_capture", True)
skc.set_intensity(1.0)
eas.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0))
ppv = eas.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
ppv.set_editor_property("unbound", True)
ps = ppv.get_editor_property("settings")
for k, v in (("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
             ("override_auto_exposure_bias", True), ("auto_exposure_bias", 11.5 if MODE == "evening" else 13.0),
             ("override_dynamic_global_illumination_method", True),
             ("dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.LUMEN),
             ("override_reflection_method", True), ("reflection_method", unreal.ReflectionMethod.LUMEN),
             ("override_white_temp", True), ("white_temp", 4700.0 if MODE == "evening" else 6000.0)):
    try:
        ps.set_editor_property(k, v)
    except Exception as e:
        log(f"post-process setting skipped: {k} ({e})")
ppv.set_editor_property("settings", ps)
# warm lights in the rooms, as in the Blender stills: one rect light per shot's room, under the ceiling
for sh in SHOTS:
    if sh["name"].startswith("room_") and sh["name"] in ONLY:
        x, y, z = (v * FT_CM for v in sh["t"])
        rl = eas.spawn_actor_from_class(unreal.RectLight, unreal.Vector(x, -y, z + 90))
        rl.set_actor_rotation(unreal.Rotator(0.0, -90.0, 0.0), False)
        rc = rl.get_component_by_class(unreal.RectLightComponent)
        rc.set_intensity(40.0)
        rc.set_light_color(unreal.LinearColor(1.0, 0.8, 0.62, 1.0))

# ------------------------------------------------------------------ cameras
cams = []
for sh in SHOTS:
    if sh["name"] not in ONLY:
        continue
    p = [v * FT_CM for v in sh["p"]]
    t = [v * FT_CM for v in sh["t"]]
    loc = unreal.Vector(p[0], -p[1], p[2])
    look = unreal.Vector(t[0], -t[1], p[2] if sh.get("level") else t[2])
    cam = eas.spawn_actor_from_class(unreal.CineCameraActor, loc)
    cam.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(loc, look), False)
    cc = cam.get_cine_camera_component()
    cc.set_editor_property("current_focal_length", float(sh.get("lens", 18)))
    fb = cc.get_editor_property("filmback")
    fb.set_editor_property("sensor_width", 36.0)
    fb.set_editor_property("sensor_height", 20.25)
    cc.set_editor_property("filmback", fb)
    focus = cc.get_editor_property("focus_settings")
    focus.set_editor_property("focus_method", unreal.CameraFocusMethod.DISABLE)
    cc.set_editor_property("focus_settings", focus)
    cam.set_actor_label("view_" + sh["name"])
    cams.append((sh["name"], cam))
unreal.EditorLoadingAndSavingUtils.save_current_level()
log(f"UE CAMERAS {[n for n, _ in cams]}")

# ------------------------------------------------------------------ capture: one camera after another, then quit
state = {"i": 0, "frame": 0, "t": time.time(), "shot": False}


def tick(_dt):
    if state["i"] >= len(cams):
        unreal.unregister_slate_post_tick_callback(handle)
        log("UE DONE")
        unreal.SystemLibrary.quit_editor()
        return
    name, cam = cams[state["i"]]
    if state["frame"] == 0:
        unreal.EditorLevelLibrary.pilot_level_actor(cam)
        state["t"] = time.time()
    state["frame"] += 1
    if state["frame"] == SETTLE_FRAMES:
        unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, os.path.join(OUT, f"{name}_ue.png"), cam)
    if state["frame"] == SETTLE_FRAMES + 30:
        log(f"UE STILL {name} {time.time() - state['t']:.1f}")
        state["i"] += 1
        state["frame"] = 0


handle = unreal.register_slate_post_tick_callback(tick)
