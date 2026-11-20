"""Unreal Engine 5 stills through the Movie Render Queue from the command line (feat/pro_2, C3.3).

Step 1, this script, in the editor (synchronous: it saves assets and returns, so -unattended is fine):

    UnrealEditor tools/unreal/HouseProto/HouseProto.uproject -ExecutePythonScript="tools/unreal/mrq_setup.py" \
        -unattended -stdout -FullStdOutLogOutput -nosplash

  loads /Game/Maps/House (made by import_render.py: the house, the lights and a CineCameraActor per shot), and
  for each camera saves a one-frame LevelSequence /Game/Stills/Still_<camera> with a camera cut to that camera,
  plus one MoviePipelinePrimaryConfig /Game/Stills/StillConfig (deferred pass, PNG, 1920x1080, warm-up frames
  for Lumen, output to PLAN3D_UE_OUT).

Step 2, the render, a separate process that renders and exits by itself (no editor UI, no script ticks):

    UnrealEditor tools/unreal/HouseProto/HouseProto.uproject /Game/Maps/House -game \
        -LevelSequence=/Game/Stills/Still_view_room_living -MoviePipelineConfig=/Game/Stills/StillConfig \
        -windowed -resx=1280 -resy=720 -log -stdout -nosplash

Every step prints "MRQ ..." so the log says where it stopped.
"""

import os

import unreal

OUT = os.environ.get("PLAN3D_UE_OUT", "/tmp/ue_stills")
WARMUP = 64
log = unreal.log


def step(msg):
    log(f"MRQ {msg}")


tools = unreal.AssetToolsHelpers.get_asset_tools()
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
step("load level " + str(les.load_level("/Game/Maps/House")))
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
cams = [a for a in eas.get_all_level_actors() if isinstance(a, unreal.CineCameraActor)]
step(f"cameras {[c.get_actor_label() for c in cams]}")
step("factories " + ", ".join(n for n in dir(unreal) if "MoviePipeline" in n and "Factory" in n))

for cam in cams:
    name = "Still_" + cam.get_actor_label()
    path = f"/Game/Stills/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    seq = tools.create_asset(name, "/Game/Stills", unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    seq.set_display_rate(unreal.FrameRate(24, 1))
    seq.set_playback_start(0)
    seq.set_playback_end(1)
    binding = seq.add_possessable(cam)
    try:
        track = seq.add_track(unreal.MovieSceneCameraCutTrack)
    except Exception as e:  # older API name
        step(f"add_track failed ({e}); trying add_master_track")
        track = seq.add_master_track(unreal.MovieSceneCameraCutTrack)
    section = track.add_section()
    section.set_range(0, 1)
    try:
        bid = seq.get_binding_id(binding)
    except Exception:
        bid = seq.make_binding_id(binding, unreal.MovieSceneObjectBindingSpace.LOCAL)
    section.set_camera_binding_id(bid)
    unreal.EditorAssetLibrary.save_asset(path)
    step(f"sequence {path}")

cfg_path = "/Game/Stills/StillConfig"
if unreal.EditorAssetLibrary.does_asset_exist(cfg_path):
    unreal.EditorAssetLibrary.delete_asset(cfg_path)
cfg_cls = getattr(unreal, "MoviePipelinePrimaryConfig", None) or getattr(unreal, "MoviePipelineMasterConfig")
factory = None
for fname in ("MoviePipelinePrimaryConfigFactory", "MoviePipelineMasterConfigFactory", "MoviePipelineConfigFactory"):
    if hasattr(unreal, fname):
        factory = getattr(unreal, fname)()
        break
cfg = tools.create_asset("StillConfig", "/Game/Stills", cfg_cls, factory)
if cfg is None:  # no factory for this class: make the object in a new package
    pkg = unreal.find_package("/Game/Stills/StillConfig") or unreal.load_package("/Game/Stills/StillConfig")
    cfg = unreal.new_object(cfg_cls, outer=pkg, name="StillConfig")
step(f"config {cfg}")
out = cfg.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
out.output_resolution = unreal.IntPoint(1920, 1080)
out.output_directory = unreal.DirectoryPath(OUT)
out.file_name_format = "{sequence_name}"
cfg.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
cfg.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
aa = cfg.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
aa.spatial_sample_count = 4
aa.temporal_sample_count = 1
aa.engine_warm_up_count = WARMUP
aa.render_warm_up_count = WARMUP
aa.override_anti_aliasing = True
step("saved config " + str(unreal.EditorAssetLibrary.save_loaded_asset(cfg)))
step("DONE")
