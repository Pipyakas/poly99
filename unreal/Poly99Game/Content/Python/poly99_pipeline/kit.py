"""Import the Blender voxel enemies + arena kit as static meshes (idempotent).

    from poly99_pipeline import kit; kit.run()

- /Game/Poly99/Kit/SM_*   from unreal/blender/export/*.fbx, Nanite on (environment + enemies)
- /Game/Poly99/Kit/Materials/M_Kit + MI_<slot>: one MI per Blender material slot name. Voxel slots
  read the baked vertex colour ("Col"), arena slots use flat neon colours.
"""

from __future__ import annotations

import unreal

SRC = "C:/UnrealProjects/poly99/unreal/blender/export"
DST = "/Game/Poly99/Kit"
MESHES = [
    "SM_Enemy_Grasshopper", "SM_Enemy_Wanderer", "SM_VoxelDebris",
    "SM_Floor_Tile_400", "SM_Wall_400", "SM_Wall_Corner", "SM_Pillar", "SM_Edge_GlowStrip", "SM_Spawn_Gate",
]
NO_NANITE = {"SM_VoxelDebris"}  # Niagara mesh particles; keep it a plain tiny mesh

MATS = DST + "/Materials"

# slot -> (BaseColor, VCMix, EmissiveColor, EmissiveUseVC, EmissiveStrength, Roughness, Metallic)
CYAN = (0.0, 0.6, 1.0)
SLOT_LOOKS = {
    "M_VoxelBody": ((0.5, 0.5, 0.5), 1.0, (0, 0, 0), 0.0, 0.0, 0.55, 0.1),
    "M_VoxelDark": ((0.02, 0.02, 0.025), 0.0, (0, 0, 0), 0.0, 0.0, 0.6, 0.1),
    "M_VoxelEmissive": ((0.5, 0.5, 0.5), 1.0, (0, 0, 0), 1.0, 15.0, 0.4, 0.0),
    "M_VoxelDebris": ((0.5, 0.5, 0.5), 1.0, (0, 0, 0), 1.0, 2.0, 0.5, 0.0),
    "M_FloorBase": ((0.05, 0.055, 0.065), 0.0, (0, 0, 0), 0.0, 0.0, 0.35, 0.6),
    "M_FloorGrid": ((0.02, 0.3, 0.4), 0.0, CYAN, 0.0, 3.0, 0.3, 0.0),
    "M_WallBody": ((0.08, 0.085, 0.1), 0.0, (0, 0, 0), 0.0, 0.0, 0.4, 0.7),
    "M_WallDark": ((0.02, 0.02, 0.025), 0.0, (0, 0, 0), 0.0, 0.0, 0.6, 0.3),
    "M_WallTrim": ((0.0, 0.3, 0.5), 0.0, CYAN, 0.0, 8.0, 0.3, 0.0),
    "M_Glow": ((0.0, 0.3, 0.5), 0.0, CYAN, 0.0, 12.0, 0.3, 0.0),
}

_assets = unreal.AssetToolsHelpers.get_asset_tools()
_mel = unreal.MaterialEditingLibrary
_lib = unreal.EditorAssetLibrary


def _import(name: str) -> unreal.StaticMesh:
    # Re-imports over an existing asset reuse its stored import data, not the options below.
    if _lib.does_asset_exist(f"{DST}/{name}"):
        aid = unreal.load_asset(f"{DST}/{name}").get_editor_property("asset_import_data")
        aid.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
    ui = unreal.FbxImportUI()
    ui.automated_import_should_detect_type = False
    ui.import_mesh = True
    ui.import_as_skeletal = False
    ui.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    ui.original_import_type = unreal.FBXImportType.FBXIT_STATIC_MESH
    ui.import_materials = False
    ui.import_textures = False
    ui.static_mesh_import_data.set_editor_property("combine_meshes", True)
    # Voxel colours live in the FBX colour layer ("Col"); the default does not keep them.
    ui.static_mesh_import_data.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
    task = unreal.AssetImportTask()
    task.filename = f"{SRC}/{name}.fbx"
    task.destination_path = DST
    task.destination_name = name
    task.replace_existing = True
    task.automated = True
    task.save = True
    task.factory = unreal.FbxFactory()
    task.options = ui
    _assets.import_asset_tasks([task])
    return unreal.load_asset(f"{DST}/{name}")


def _param(m, cls, name, value, x, y):
    e = _mel.create_material_expression(m, cls, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", unreal.LinearColor(*value, 1) if isinstance(value, tuple) else value)
    return e


def make_master() -> unreal.Material:
    path = MATS + "/M_Kit"
    if _lib.does_asset_exist(path):
        return unreal.load_asset(path)
    m = _assets.create_asset("M_Kit", MATS, unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("used_with_nanite", True)
    m.set_editor_property("used_with_instanced_static_meshes", True)
    vc = _mel.create_material_expression(m, unreal.MaterialExpressionVertexColor, -1100, 0)
    base = _param(m, unreal.MaterialExpressionVectorParameter, "BaseColor", (0.5, 0.5, 0.5), -1100, -300)
    vc_mix = _param(m, unreal.MaterialExpressionScalarParameter, "VCMix", 0.0, -1100, 200)
    emi = _param(m, unreal.MaterialExpressionVectorParameter, "EmissiveColor", (0.0, 0.0, 0.0), -1100, 400)
    emi_vc = _param(m, unreal.MaterialExpressionScalarParameter, "EmissiveUseVC", 0.0, -1100, 600)
    strength = _param(m, unreal.MaterialExpressionScalarParameter, "EmissiveStrength", 0.0, -800, 700)
    rough = _param(m, unreal.MaterialExpressionScalarParameter, "Roughness", 0.5, -400, 300)
    metal = _param(m, unreal.MaterialExpressionScalarParameter, "Metallic", 0.0, -400, 200)

    base_lerp = _mel.create_material_expression(m, unreal.MaterialExpressionLinearInterpolate, -700, -200)
    _mel.connect_material_expressions(base, "", base_lerp, "A")
    _mel.connect_material_expressions(vc, "", base_lerp, "B")
    _mel.connect_material_expressions(vc_mix, "", base_lerp, "Alpha")
    emi_lerp = _mel.create_material_expression(m, unreal.MaterialExpressionLinearInterpolate, -700, 450)
    _mel.connect_material_expressions(emi, "", emi_lerp, "A")
    _mel.connect_material_expressions(vc, "", emi_lerp, "B")
    _mel.connect_material_expressions(emi_vc, "", emi_lerp, "Alpha")
    glow = _mel.create_material_expression(m, unreal.MaterialExpressionMultiply, -450, 500)
    _mel.connect_material_expressions(emi_lerp, "", glow, "A")
    _mel.connect_material_expressions(strength, "", glow, "B")

    _mel.connect_material_property(base_lerp, "", unreal.MaterialProperty.MP_BASE_COLOR)
    _mel.connect_material_property(glow, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    _mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    _mel.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    _mel.recompile_material(m)
    _lib.save_loaded_asset(m)
    return m


def make_instances(master) -> dict:
    out = {}
    for slot, (base, vc_mix, emi, emi_vc, strength, rough, metal) in SLOT_LOOKS.items():
        path = f"{MATS}/MI_{slot[2:]}"
        mi = unreal.load_asset(path) if _lib.does_asset_exist(path) else _assets.create_asset(
            path.rsplit("/", 1)[1], MATS, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mi.set_editor_property("parent", master)
        _mel.set_material_instance_vector_parameter_value(mi, "BaseColor", unreal.LinearColor(*base, 1))
        _mel.set_material_instance_vector_parameter_value(mi, "EmissiveColor", unreal.LinearColor(*emi, 1))
        for p, v in (("VCMix", vc_mix), ("EmissiveUseVC", emi_vc), ("EmissiveStrength", strength),
                     ("Roughness", rough), ("Metallic", metal)):
            _mel.set_material_instance_scalar_parameter_value(mi, p, v)
        _mel.update_material_instance(mi)
        _lib.save_loaded_asset(mi)
        out[slot] = mi
    return out


def _assign(mesh, instances: dict) -> None:
    out = []  # struct elements are copies: rebuild the array instead of editing in place
    for slot in mesh.get_editor_property("static_materials"):
        mi = instances.get(str(slot.get_editor_property("material_slot_name")))
        if mi:
            slot.set_editor_property("material_interface", mi)
        out.append(slot)
    mesh.set_editor_property("static_materials", out)


def run() -> dict:
    instances = make_instances(make_master())
    sizes = {}
    for name in MESHES:
        mesh = _import(name)
        _assign(mesh, instances)
        if name not in NO_NANITE:
            settings = mesh.get_editor_property("nanite_settings")
            settings.set_editor_property("enabled", True)
            mesh.set_editor_property("nanite_settings", settings)
        _lib.save_loaded_asset(mesh)
        box = mesh.get_bounding_box()
        size = box.max - box.min
        sizes[name] = (round(size.x, 1), round(size.y, 1), round(size.z, 1), round(box.min.z, 2))
        unreal.log(f"poly99 kit {name}: size cm {sizes[name][:3]} minZ {sizes[name][3]}")
    return sizes
