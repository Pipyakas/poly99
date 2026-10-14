"""Shared helpers for poly99 Blender asset scripts.

Conventions
-----------
* 1 Blender unit = 1 meter. Final asset sizes are authored in centimeters
  and converted with cm().
* Blender axes: +X forward (asset "front"), +Y left, +Z up.
  UE axes: +X forward, +Y right, +Z up. FBX export uses axis_forward="X",
  axis_up="Z" so a model built facing Blender +X faces UE +X and Z stays up.
* Pivots (object origins) sit at the base center (floor contact) for
  props and enemies.
* Materials: one simple Principled material per color role, named
  ``M_<Role>`` (e.g. M_VoxelBody). Emissive roles use a separate material
  with an emission shader. Every mesh also carries a vertex color
  attribute named "Col"; UE replaces the materials anyway.
"""

import bmesh
import bpy
import mathutils
import os

BLENDER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_DIR = os.path.join(BLENDER_ROOT, "export")
PREVIEW_DIR = os.path.join(EXPORT_DIR, "previews")
SOURCE_DIR = os.path.join(BLENDER_ROOT, "source")

BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

CM = 0.01  # centimeters -> Blender units (meters)


def cm(v):
    """Centimeters -> Blender units."""
    return v * CM


def ensure_dirs():
    for d in (EXPORT_DIR, PREVIEW_DIR, SOURCE_DIR):
        os.makedirs(d, exist_ok=True)


def clear_scene():
    """Idempotent start: remove every object, then orphaned datablocks."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras,
                 bpy.data.lights, bpy.data.curves, bpy.data.metaballs,
                 bpy.data.collections):
        for block in list(coll):
            if block.name.startswith("Collection") and block.users > 0:
                continue
            if getattr(block, "users", 0) == 0:
                coll.remove(block)


def get_or_make_material(name, color, emissive_color=None,
                         emissive_strength=0.0, roughness=0.6, metallic=0.0):
    """One simple Principled material per color role, named M_<Role>."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emissive_color is not None and emissive_strength > 0.0:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emissive_color, 1.0)
            bsdf.inputs["Emission Strength"].default_value = emissive_strength
    mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def set_vertex_colors(mesh, face_role_map, palette):
    """Flat vertex color per face, attribute name "Col".

    face_role_map: list parallel to mesh.polygons, entry = role key.
    """
    if "Col" in mesh.color_attributes:
        mesh.color_attributes.remove(mesh.color_attributes["Col"])
    col = mesh.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    for poly_idx, role in enumerate(face_role_map):
        rgba = (*palette[role][0], 1.0)
        for loop_idx in mesh.polygons[poly_idx].loop_indices:
            col.data[loop_idx].color = rgba


def origin_to_base_center(obj):
    """Move the object origin to the base center (floor contact).

    Works for un-rotated objects: shifts the mesh so the
    bounding-box center-X/Y land on the local origin and the
    bounding-box min-Z (floor contact) lands at Z=0, then
    zeroes the object location. The mesh is translated by
    (-cx, -cy, -zmin): the negatives bring the bbox center
    to (0, 0) and the bottom face to the floor (zmin is
    negative when the mesh hangs below the origin, e.g. a
    cube added at the origin, so -zmin lifts it up).
    """
    corners = [mathutils.Vector(c) for c in obj.bound_box]
    cx = sum(v.x for v in corners) / 8.0
    cy = sum(v.y for v in corners) / 8.0
    zmin = min(v.z for v in corners)
    obj.data.transform(
        mathutils.Matrix.Translation(
            mathutils.Vector((-cx, -cy, -zmin))))
    obj.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()


def apply_all_transforms(obj):
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.select_all(action="DESELECT")


# ------------------------------------------------------- voxel construction

# Counter-clockwise quad corners (seen from outside) for the 6 cube faces,
# expressed as offsets in [0, 1]^3, ordered +Z, -Z, +X, -X, +Y, -Y.
_FACE_CORNERS = (
    (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1),
    (0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0),
    (1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1),
    (0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0),
    (0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0),
    (0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1),
)
_FACE_NORMALS = (
    (0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0),
)


def voxel_mesh_from_occupancy(name, voxels, voxel_size_cm, palette):
    """Build one merged mesh from a 3D occupancy grid.

    voxels: dict {(i, j, k): role}; role is a key in `palette`.
    palette: role -> (rgb, emissive_rgb_or_None, emissive_strength).

    Returns the object. Only faces between a filled and an empty voxel are
    emitted (no interior faces); shading is flat.
    """
    vs = cm(voxel_size_cm)
    verts = []
    faces = []
    face_roles = []
    vert_cache = {}

    def vid(p):
        if p not in vert_cache:
            vert_cache[p] = len(verts)
            verts.append(p)
        return vert_cache[p]

    filled = set(voxels.keys())
    for key in sorted(voxels):
        role = voxels[key]
        ox, oy, oz = key[0] * vs, key[1] * vs, key[2] * vs
        for f in range(6):
            n = _FACE_NORMALS[f]
            if (key[0] + n[0], key[1] + n[1], key[2] + n[2]) in filled:
                continue  # interior face
            quad = []
            for c in range(4):
                off = _FACE_CORNERS[f * 4 + c]
                quad.append(vid((ox + off[0] * vs, oy + off[1] * vs,
                                 oz + off[2] * vs)))
            faces.append(quad)
            face_roles.append(role)

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    bm.from_mesh(mesh)
    for f in bm.faces:
        f.smooth = False
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    roles = []
    for role in face_roles:
        if role not in roles:
            roles.append(role)
    mesh.materials.clear()
    role_index = {}
    for role in roles:
        role_index[role] = len(mesh.materials)
        spec = palette[role]
        emissive = spec[1] if len(spec) > 1 else None
        strength = spec[2] if len(spec) > 2 else 0.0
        mesh.materials.append(get_or_make_material(
            "M_" + role, spec[0], emissive_color=emissive,
            emissive_strength=strength))
    for poly_idx, role in enumerate(face_roles):
        mesh.polygons[poly_idx].material_index = role_index[role]

    set_vertex_colors(mesh, face_roles, palette)
    return obj


def export_fbx(obj, filename):
    """Export one object to FBX with the poly99/UE conventions.

    Axis settings: axis_forward="X", axis_up="Z" map Blender +X
    (asset front) to UE +X and keep Blender +Z up.

    Scale: the scene is authored in meters (1 BU = 1 m), but UE's
    FBX importer multiplies raw vertex data by
    UnitScaleFactor / 100. The FBX exporter writes
    UnitScaleFactor = 100 (i.e. "file units are centimeters")
    for apply_scale_options='FBX_SCALE_UNITS' with a meter
    scene, yet leaves the vertex data in meters -- so UE lands
    100x too small (a 300 cm pillar imports as 3 cm). The fix
    is global_scale=100: the exporter then writes the vertex
    data in centimeters (matching the declared UnitScaleFactor),
    so UE computes cm * (100/100) = the authored centimeter
    size. Axis mapping and pivot are unaffected.
    """
    ensure_dirs()
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        apply_scale_options="FBX_SCALE_UNITS",
        mesh_smooth_type="FACE",
        use_mesh_modifiers=True,
        add_leaf_bones=False,
        axis_forward="X",
        axis_up="Z",
        global_scale=100.0,
        bake_space_transform=True,
    )
    return path


def measure_fbx(path):
    """Re-import an FBX into a scratch scene; return (tris, bbox cm xyz)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    tris = 0
    bbmin = [float("inf")] * 3
    bbmax = [float("-inf")] * 3
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        tris += len(obj.data.polygons)
        for c in obj.bound_box:
            w = obj.matrix_world @ mathutils.Vector(c)
            bbmin = [min(bbmin[i], w[i]) for i in range(3)]
            bbmax = [max(bbmax[i], w[i]) for i in range(3)]
    dims = tuple((bbmax[i] - bbmin[i]) * 100.0 for i in range(3))
    return tris, dims
