"""Import the Blender armor set + helmet and wire them into DA_Hero_Default (idempotent).

    from poly99_pipeline import armor; armor.run()

- /Game/Characters/Hero/Armor/SKM_Armor_<Slot>   skeletal, bound to metahuman_base_skel
- /Game/Characters/Hero/Armor/SM_Helmet_A        static, attached to the `head` socket
- /Game/Characters/Hero/Armor/Materials/M_HeroArmor  master (PrimaryColor, SecondaryColor,
  EmissiveColor, Dissolve: the names UPoly99HeroAppearanceComponent drives) + one MI per role
"""

from __future__ import annotations

import unreal

SRC = "C:/UnrealProjects/poly99/unreal/blender/armor/export"
DST = "/Game/Characters/Hero/Armor"
MATS = DST + "/Materials"
SKELETON = "/MetaHumanCharacter/Female/Medium/NormalWeight/Body/metahuman_base_skel.metahuman_base_skel"
LOADOUT = "/Game/Poly99/Data/DA_Hero_Default"
BODY = "/Game/Characters/Hero/Unpacked/MHC_Hero/Body/SKM_MHC_Hero_BodyMesh"
SLOTS = ["Chest", "Shoulders", "Arms", "Hands", "Legs", "Feet", "Back"]

# Role -> (SecondaryMix, EmissiveMix, Darken, Roughness, Metallic). Base colour is
# lerp(PrimaryColor, SecondaryColor, SecondaryMix) * (1 - Darken); emissive is EmissiveColor * EmissiveMix.
ROLES = {
    "M_ArmorPrimary": (0.0, 0.0, 0.0, 0.34, 0.85),
    "M_ArmorSecondary": (1.0, 0.0, 0.0, 0.44, 0.80),
    "M_ArmorEmissive": (0.0, 1.0, 0.6, 0.30, 0.20),
    "M_Visor": (0.0, 0.0, 0.7, 0.08, 0.45),
    "M_Undersuit": (0.0, 0.0, 0.75, 0.80, 0.05),
}

_assets = unreal.AssetToolsHelpers.get_asset_tools()
_lib = unreal.EditorAssetLibrary
_mel = unreal.MaterialEditingLibrary


def _import(name: str, skeletal: bool):
    ui = unreal.FbxImportUI()
    ui.automated_import_should_detect_type = False
    ui.import_mesh = True
    ui.import_as_skeletal = skeletal
    t = unreal.FBXImportType.FBXIT_SKELETAL_MESH if skeletal else unreal.FBXImportType.FBXIT_STATIC_MESH
    ui.mesh_type_to_import = t
    ui.original_import_type = t
    ui.import_materials = False
    ui.import_textures = False
    ui.import_animations = False
    ui.create_physics_asset = False
    if skeletal:
        ui.skeleton = unreal.load_asset(SKELETON)
    else:
        # The helmet FBX stores head-bone-local geometry under a node carrying the head rest
        # transform; keep the vertices local so the mesh sits correctly on the `head` socket.
        ui.static_mesh_import_data.set_editor_property("transform_vertex_to_absolute", False)
        ui.static_mesh_import_data.set_editor_property("bake_pivot_in_vertex", False)
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


def _scalar(m, name, default, x, y):
    e = _mel.create_material_expression(m, unreal.MaterialExpressionScalarParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", default)
    return e


def _vector(m, name, color, x, y):
    e = _mel.create_material_expression(m, unreal.MaterialExpressionVectorParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", unreal.LinearColor(*color))
    return e


def make_master() -> unreal.Material:
    path = MATS + "/M_HeroArmor"
    if _lib.does_asset_exist(path):
        return unreal.load_asset(path)
    m = _assets.create_asset("M_HeroArmor", MATS, unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    m.set_editor_property("used_with_skeletal_mesh", True)

    primary = _vector(m, "PrimaryColor", (0.08, 0.09, 0.11, 1), -1200, -300)
    secondary = _vector(m, "SecondaryColor", (0.55, 0.57, 0.6, 1), -1200, -100)
    emissive = _vector(m, "EmissiveColor", (0.0, 2.5, 4.0, 1), -1200, 300)
    sec_mix = _scalar(m, "SecondaryMix", 0.0, -1200, 100)
    emi_mix = _scalar(m, "EmissiveMix", 0.0, -1200, 500)
    darken = _scalar(m, "Darken", 0.0, -900, 100)
    rough = _scalar(m, "Roughness", 0.4, -400, 200)
    metal = _scalar(m, "Metallic", 0.8, -400, 100)
    dissolve = _scalar(m, "Dissolve", 0.0, -1200, 800)

    lerp = _mel.create_material_expression(m, unreal.MaterialExpressionLinearInterpolate, -900, -200)
    _mel.connect_material_expressions(primary, "", lerp, "A")
    _mel.connect_material_expressions(secondary, "", lerp, "B")
    _mel.connect_material_expressions(sec_mix, "", lerp, "Alpha")
    keep = _mel.create_material_expression(m, unreal.MaterialExpressionOneMinus, -700, 100)
    _mel.connect_material_expressions(darken, "", keep, "")
    base = _mel.create_material_expression(m, unreal.MaterialExpressionMultiply, -500, -200)
    _mel.connect_material_expressions(lerp, "", base, "A")
    _mel.connect_material_expressions(keep, "", base, "B")
    glow = _mel.create_material_expression(m, unreal.MaterialExpressionMultiply, -900, 400)
    _mel.connect_material_expressions(emissive, "", glow, "A")
    _mel.connect_material_expressions(emi_mix, "", glow, "B")

    # Dissolve: world-position noise thresholded against Dissolve (0 = solid, 1 = gone).
    noise = _mel.create_material_expression(m, unreal.MaterialExpressionNoise, -900, 700)
    noise.set_editor_property("scale", 0.08)
    noise.set_editor_property("output_min", 0.02)
    noise.set_editor_property("output_max", 1.0)
    cut = _mel.create_material_expression(m, unreal.MaterialExpressionSubtract, -600, 750)
    _mel.connect_material_expressions(noise, "", cut, "A")
    _mel.connect_material_expressions(dissolve, "", cut, "B")

    _mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    _mel.connect_material_property(glow, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    _mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    _mel.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    _mel.connect_material_property(cut, "", unreal.MaterialProperty.MP_OPACITY_MASK)
    m.set_editor_property("opacity_mask_clip_value", 0.0001)
    _mel.recompile_material(m)
    _lib.save_loaded_asset(m)
    return m


def make_instances(master) -> dict:
    out = {}
    for name, (sec_mix, emi_mix, darken, rough, metal) in ROLES.items():
        path = f"{MATS}/MI_{name[2:]}"
        mi = unreal.load_asset(path) if _lib.does_asset_exist(path) else _assets.create_asset(
            path.rsplit("/", 1)[1], MATS, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mi.set_editor_property("parent", master)
        for p, v in (("SecondaryMix", sec_mix), ("EmissiveMix", emi_mix), ("Darken", darken),
                     ("Roughness", rough), ("Metallic", metal)):
            _mel.set_material_instance_scalar_parameter_value(mi, p, v)
        _mel.update_material_instance(mi)
        _lib.save_loaded_asset(mi)
        out[name] = mi
    return out


def _assign(mesh, instances: dict) -> None:
    prop = "materials" if isinstance(mesh, unreal.SkeletalMesh) else "static_materials"
    out = []  # struct elements are copies: rebuild the array instead of editing in place
    for slot in mesh.get_editor_property(prop):
        mi = instances.get(str(slot.get_editor_property("material_slot_name")))
        if mi:
            slot.set_editor_property("material_interface", mi)
        out.append(slot)
    mesh.set_editor_property(prop, out)
    _lib.save_loaded_asset(mesh)


def helmet_offset() -> unreal.Transform:
    """Interchange bakes the helmet's head-rest node transform into the vertices (it ignores
    transform_vertex_to_absolute), so the mesh is in character space; undo the `head` rest pose."""
    body = unreal.load_asset(BODY)
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SkeletalMeshActor, unreal.Vector(0, 0, 0))
    try:
        comp = actor.skeletal_mesh_component
        comp.set_skinned_asset_and_update(body)
        head = comp.get_socket_transform("head", unreal.RelativeTransformSpace.RTS_COMPONENT)
    finally:
        actor.destroy_actor()
    return head.inverse()


def run(import_meshes: bool = True) -> None:
    instances = make_instances(make_master())
    armor = unreal.Map(unreal.Poly99ArmorSlot, unreal.SkeletalMesh)
    for slot in SLOTS:
        name = f"SKM_Armor_{slot}"
        mesh = _import(name, True) if import_meshes else unreal.load_asset(f"{DST}/{name}")
        _assign(mesh, instances)
        armor[getattr(unreal.Poly99ArmorSlot, slot.upper())] = mesh
    helmet = _import("SM_Helmet_A", False) if import_meshes else unreal.load_asset(f"{DST}/SM_Helmet_A")
    _assign(helmet, instances)

    da = unreal.load_asset(LOADOUT)
    da.set_editor_property("armor", armor)
    da.set_editor_property("helmet", helmet)
    da.set_editor_property("helmet_offset", helmet_offset())
    _lib.save_loaded_asset(da)
    for slot in SLOTS:
        b = unreal.load_asset(f"{DST}/SKM_Armor_{slot}").get_bounds()
        unreal.log(f"poly99 armor {slot}: extent cm {b.box_extent}")
