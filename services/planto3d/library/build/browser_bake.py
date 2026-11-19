"""The browser model of a library asset: every mesh joined (modifiers applied), decimated to a triangle budget, new
UVs, the colours of the procedural materials baked into one 1024 px atlas, glowing and glass parts as flat glTF
materials, metals as flat metallic ones (a colour bake turns metals black), exported as a Draco .glb.
Used by make_library.py and the creator agent's worker. Changes the scene: call it last."""
import math
import os

import bpy

import style

GLOW = {"Cove", "CoveSoft", "Downlight", "Bulb", "Shade", "Lantern", "MirrorRing"}
CLEAR = {"Glass", "FlutedGlass"}
METALS = {"Brass": ("#b08d57", 0.3), "Bronze": ("#4b3a27", 0.35), "DarkMetal": ("#1c1a18", 0.5),
          "Chrome": ("#d9dcdd", 0.12), "Mirror": ("#f2f4f4", 0.02)}


def tris(obs):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for o in obs:
        if o.type == "MESH":
            me = o.evaluated_get(dg).to_mesh()
            n += sum(len(p.vertices) - 2 for p in me.polygons)
            o.evaluated_get(dg).to_mesh_clear()
    return n


def _flat(name, color, metallic=0.0, rough=0.5, emit=0.0, alpha=1.0):
    g = bpy.data.materials.new(name)
    g.use_nodes = True
    b = g.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = color
        b.inputs["Emission Strength"].default_value = emit
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    return g


def bake_browser(scene, name, folder, budget=20000):
    """-> (path of the .glb, its triangles)"""
    for o in list(scene.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    meshes = [o for o in scene.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    if tris([ob]) > budget:
        d = ob.modifiers.new("decimate", "DECIMATE")
        d.ratio = budget / tris([ob])
        bpy.ops.object.modifier_apply(modifier=d.name)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new(f"{name}_atlas", 1024, 1024)
    bakeable = [m for m in ob.data.materials if m and m.name not in GLOW | CLEAR | set(METALS)]
    metal = []
    for m in bakeable:
        n = m.node_tree.nodes.new("ShaderNodeTexImage")
        n.image = img
        m.node_tree.nodes.active = n
        for p in m.node_tree.nodes:      # a colour bake of a metal is black: bake it as a non-metal
            if p.type == "BSDF_PRINCIPLED" and not p.inputs["Metallic"].is_linked and p.inputs["Metallic"].default_value > 0:
                metal.append((m.name, p.inputs["Metallic"].default_value))
                p.inputs["Metallic"].default_value = 0.0
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 4
    scene.cycles.device = "CPU"
    if bakeable:
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=4)
    img.filepath_raw = os.path.join(folder, f"{name}_atlas.png")
    img.file_format = "PNG"
    img.save()
    atlas = bpy.data.materials.new(f"{name}_baked")
    atlas.use_nodes = True
    bsdf = atlas.node_tree.nodes["Principled BSDF"]
    tex = atlas.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    atlas.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.55
    if metal:
        bsdf.inputs["Metallic"].default_value = 0.0
    swap = {}
    for i, m in enumerate(ob.data.materials):
        if m is None or m.name in GLOW:
            swap[i] = _flat(f"{name}_glow", (1.0, 0.78, 0.52, 1), emit=3.0)
        elif m.name in METALS:
            # 0.55, not 1: the house's light bake is diffuse; the walkthrough adds the reflection above 0.5
            swap[i] = _flat(f"{name}_{m.name.lower()}", style.rgba(METALS[m.name][0]), 0.55, METALS[m.name][1])
        elif m.name in CLEAR:
            swap[i] = _flat(f"{name}_glass", (0.9, 0.95, 0.94, 1), rough=0.05, alpha=0.25)
        else:
            swap[i] = atlas
    for i, g in swap.items():
        ob.data.materials[i] = g
    out_tris = tris([ob])
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    path = os.path.join(folder, f"{name}.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_draco_mesh_compression_enable=True)
    return path, out_tris
