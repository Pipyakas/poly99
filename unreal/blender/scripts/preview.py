"""Render a 512x512 PNG preview per asset (Workbench,
3/4 top-down view) into export/previews/, and save the
generating .blend into blender/source/.

Run after the asset scripts; each asset is rebuilt
from its builder (same code path as the FBX export),
framed on a turntable-style 3/4 top-down camera.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common  # noqa: E402
from common import bpy, mathutils  # noqa: E402

PREVIEW_SIZE = (512, 512)


def render_preview(obj, name):
    scene = bpy.context.scene

    # EEVEE render: shows the actual material
    # colors and emissive roles.
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = PREVIEW_SIZE[0]
    scene.render.resolution_y = PREVIEW_SIZE[1]
    scene.render.film_transparent = False

    # Dark world background so the neon reads.
    world = bpy.data.worlds.get("PreviewWorld")
    if world is None:
        world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg is not None:
        bg.inputs[0].default_value = (0.02, 0.02, 0.03, 1.0)
        bg.inputs[1].default_value = 0.3
    scene.world = world

    # 3/4 top-down camera.
    center = sum((mathutils.Vector(c)
                  for c in obj.bound_box),
                 mathutils.Vector()) / 8.0
    size = (obj.dimensions.x, obj.dimensions.y,
            obj.dimensions.z)
    biggest = max(size)
    # Distance so the asset fills the frame
    # with a 50 mm lens (horizontal FOV on a
    # 512 px square sensor is ~40 deg).
    dist = max(biggest * 1.9, common.cm(60))
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    bpy.context.collection.objects.link(cam)
    # Elevated 3/4 view: front-right-above,
    # looking down.
    cam.location = center + mathutils.Vector(
        (dist * 0.75, -dist * 0.75, dist * 0.75))
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat(
        "-Z", "Y").to_euler()
    scene.camera = cam

    # Sun light for the shaded look.
    # Key light from the front-right-above.
    sun_data = bpy.data.lights.new(
        "PreviewSun", "SUN")
    sun_data.energy = 6.0
    sun = bpy.data.objects.new("PreviewSun", sun_data)
    bpy.context.collection.objects.link(sun)
    sun.location = center + mathutils.Vector(
        (common.cm(400), common.cm(-300),
         common.cm(700)))
    # Aim the sun at the object.
    sun.rotation_euler = (
        (center - sun.location)
        .to_track_quat("-Z", "Y").to_euler())

    # Fill light from the left so faces are
    # never pure black.
    fill_data = bpy.data.lights.new(
        "PreviewFill", "SUN")
    fill_data.energy = 3.0
    fill = bpy.data.objects.new("PreviewFill",
                                  fill_data)
    bpy.context.collection.objects.link(fill)
    fill.location = center + mathutils.Vector(
        (common.cm(-400), common.cm(300),
         common.cm(300)))
    fill.rotation_euler = (
        (center - fill.location)
        .to_track_quat("-Z", "Y").to_euler())

    # Rim light from behind for edge definition.
    rim_data = bpy.data.lights.new(
        "PreviewRim", "SUN")
    rim_data.energy = 2.0
    rim = bpy.data.objects.new("PreviewRim",
                                   rim_data)
    bpy.context.collection.objects.link(rim)
    rim.location = center + mathutils.Vector(
        (common.cm(-200), common.cm(-400),
         common.cm(200)))
    rim.rotation_euler = (
        (center - rim.location)
        .to_track_quat("-Z", "Y").to_euler())

    path = os.path.join(common.PREVIEW_DIR, name + ".png")
    scene.render.filepath = path
    # Write 8-bit PNG.
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    return path


def build_all_assets():
    """Rebuild every asset (same code path as export)
    and yield (object, preview_name)."""
    import enemy_voxel
    import arena_kit

    common.clear_scene()
    voxels = enemy_voxel.grasshopper_grid()
    obj = common.voxel_mesh_from_occupancy(
        "SM_Enemy_Grasshopper", voxels,
        enemy_voxel.VOXEL_CM,
        enemy_voxel.PALETTE_CRIMSON)
    common.origin_to_base_center(obj)
    yield obj, "SM_Enemy_Grasshopper"

    common.clear_scene()
    voxels = enemy_voxel.wanderer_grid()
    obj = common.voxel_mesh_from_occupancy(
        "SM_Enemy_Wanderer", voxels, enemy_voxel.VOXEL_CM,
        enemy_voxel.PALETTE_AMBER)
    common.origin_to_base_center(obj)
    yield obj, "SM_Enemy_Wanderer"

    # Debris cube (same construction as build_debris,
    # without the FBX export).
    common.clear_scene()
    common.bpy.ops.mesh.primitive_cube_add(
        size=common.cm(6.0))
    obj = common.bpy.context.active_object
    obj.name = "SM_VoxelDebris"
    bevel = obj.modifiers.new("Bevel", "BEVEL")
    bevel.width = common.cm(0.4)
    bevel.segments = 1
    bevel.limit_method = "NONE"
    common.apply_all_transforms(obj)
    common.origin_to_base_center(obj)
    yield obj, "SM_VoxelDebris"

    for name, builder in arena_kit.BUILDERS:
        common.clear_scene()
        obj = builder()
        common.origin_to_base_center(obj)
        common.apply_all_transforms(obj)
        obj.name = name
        yield obj, name


def main():
    common.ensure_dirs()
    for obj, name in build_all_assets():
        png = render_preview(obj, name)
        blend = os.path.join(common.SOURCE_DIR,
                             name + ".blend")
        bpy.ops.wm.save_as_mainfile(filepath=blend)
        print("WROTE", png)
        print("WROTE", blend)


if __name__ == "__main__":
    main()
