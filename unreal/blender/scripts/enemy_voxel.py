"""Voxel enemies for poly99.

Two enemies built from 3D occupancy grids (voxel size 6 cm),
merged into one mesh each with only exterior faces, flat
shaded, plus a single beveled debris cube for Niagara
mesh particles.

Exports
-------
export/SM_Enemy_Grasshopper.fbx + _voxels.json
export/SM_Enemy_Wanderer.fbx    + _voxels.json
export/SM_VoxelDebris.fbx

Voxel centers in the JSON are in UE axes (X forward,
Y right, Z up), centimeters, relative to the mesh origin
at the base center (floor contact).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common  # noqa: E402

VOXEL_CM = 6.0

PALETTE_CRIMSON = {
    "VoxelBody": ((0.55, 0.07, 0.11), None, 0.0),
    "VoxelDark": ((0.24, 0.03, 0.05), None, 0.0),
    "VoxelEmissive": ((1.0, 0.18, 0.24), (1.0, 0.12, 0.18), 6.0),
}
PALETTE_AMBER = {
    "VoxelBody": ((0.85, 0.44, 0.06), None, 0.0),
    "VoxelDark": ((0.32, 0.15, 0.03), None, 0.0),
    "VoxelEmissive": ((1.0, 0.64, 0.12), (1.0, 0.55, 0.08), 5.0),
}


# ------------------------------------------------------------------ grids

def grasshopper_grid():
    """Aggressive chaser drone, ~60 cm across (X and Y),
    ~36 cm tall, crimson, twin emissive eyes on the front
    (+X) face, readable from top-down.

    Grid: i in [-5, 4] (X, 60 cm), j in [-5, 4]
    (Y, 60 cm), k in [0, 5] (36 cm tall).
    Teardrop plan: wide rear, pointed nose at +X.
    """
    g = {}
    for i in range(-5, 5):
        # plan half-width: rear (i=-5) -> 4, nose (i=4) -> 0
        t = (i + 5) / 9.0
        half_j = int(round(4 - 4 * t))
        if half_j < 0:
            half_j = 0
        for j in range(-half_j, half_j + 1):
            top = 5 if -3 <= i <= 1 else 4
            if half_j >= 3 and abs(j) == half_j:
                top = min(top, 4)
            for k in range(top):
                g[(i, j, k)] = "VoxelBody"
    # Brow slit: emissive voxels between/around the eyes,
    # front upper deck.
    for (i, j, k) in [(1, 0, 3), (2, 0, 3), (1, 0, 4), (2, 0, 4)]:
        g[(i, j, k)] = "VoxelEmissive"
    # Twin eyes on the front face (top layer, front columns).
    for (i, j, k) in [(3, -1, 4), (3, 1, 4)]:
        g[(i, j, k)] = "VoxelEmissive"
    # Rear antenna spikes (connect at k=4).
    for (i, j) in [(-5, -2), (-5, 2)]:
        for k in range(4, 6):
            g[(i, j, k)] = "VoxelDark"
    # Dark keel on the bottom layer and top skin.
    for (i, j, k) in list(g.keys()):
        if g[(i, j, k)] != "VoxelEmissive":
            if k == 0 or k >= 5:
                g[(i, j, k)] = "VoxelDark"
    return g


def wanderer_grid():
    """Bulky crawler / cube cluster, ~80 cm across, amber,
    emissive core.

    Grid: i, j in [-6, 6], k in [0, 7] core shell;
    four corner claw legs reach to +-6 (78 cm across).
    """
    g = {}
    R = 5
    # Solid rounded cube core (chunky).
    for i in range(-R, R + 1):
        for j in range(-R, R + 1):
            for k in range(0, 8):
                if max(abs(i), abs(j)) + max(0, k - 3) <= 6:
                    g[(i, j, k)] = "VoxelBody"
    # Carve to a chunky shell around a 3x3x4 emissive core.
    core = [(i, j, k) for i in range(-1, 2)
            for j in range(-1, 2)
            for k in range(2, 6)]
    for key in list(g.keys()):
        if key in core:
            continue
        i, j, k = key
        adjacent = any(((i + d[0], j + d[1], k + d[2]) in g
                        for d in ((1, 0, 0), (-1, 0, 0),
                                  (0, 1, 0), (0, -1, 0),
                                  (0, 0, 1), (0, 0, -1))))
        exposed = any(((i + d[0], j + d[1], k + d[2]) not in g
                       for d in ((1, 0, 0), (-1, 0, 0),
                                 (0, 1, 0), (0, -1, 0),
                                 (0, 0, 1), (0, 0, -1))))
        # Keep only surface voxels of the solid (shell).
        if not exposed:
            del g[key]
    for key in core:
        g[key] = "VoxelEmissive"
    # Dark underbelly.
    for key in [k for k, v in g.items() if v == "VoxelBody"]:
        if key[2] == 0:
            g[key] = "VoxelDark"
    # Four claw legs reaching diagonally out and down.
    for (si, sj) in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        for step in range(1, 3):
            i = si * (R - 1 + step)
            j = sj * (R - 1 + step)
            k = 1 if step < 2 else 0
            g[(i, j, k)] = "VoxelDark"
            g[(i, j, k + 1)] = "VoxelBody"
    # Crown spike with emissive tip.
    for k in range(8, 10):
        g[(0, 0, k)] = "VoxelEmissive" if k == 9 else "VoxelDark"
    return g


# ------------------------------------------------------------------ output

def build_enemy(grid_func, name, filename, palette):
    common.clear_scene()
    voxels = grid_func()
    obj = common.voxel_mesh_from_occupancy(
        name, voxels, VOXEL_CM, palette)
    common.origin_to_base_center(obj)
    common.apply_all_transforms(obj)
    obj.name = "SM_" + name
    obj.data.name = "SM_" + name

    # Grid origin in UE cm relative to the mesh origin
    # (base center). Before centering, voxel (i, j, k)
    # center was ((i+.5)vs, (j+.5)vs, (k+.5)vs); the
    # center shift was the bbox center (cx, cy) and
    # zmin = 0 (k starts at 0 for both enemies).
    keys = list(voxels.keys())
    vs = common.cm(VOXEL_CM)
    xs = [(k[0] + 0.5) * vs for k in keys]
    ys = [(k[1] + 0.5) * vs for k in keys]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    origin_cm = (-cx * 100.0, -cy * 100.0, 0.0)
    json_path = write_voxels_json(
        "SM_" + name + "_voxels.json", voxels, origin_cm)
    fbx_path = common.export_fbx(obj, "SM_" + name + ".fbx")
    return fbx_path, json_path


def write_voxels_json(filename, voxels, origin_cm):
    path = os.path.join(common.EXPORT_DIR, filename)
    entries = []
    for key in sorted(voxels.keys()):
        role = voxels[key]
        entries.append({
            "i": key[0], "j": key[1], "k": key[2],
            "center_ue_cm": [
                origin_cm[0] + (key[0] + 0.5) * VOXEL_CM,
                origin_cm[1] + (key[1] + 0.5) * VOXEL_CM,
                origin_cm[2] + (key[2] + 0.5) * VOXEL_CM,
            ],
            "color_role": role,
            "material": "M_" + role,
        })
    doc = {
        "asset": os.path.splitext(filename)[0],
        "voxel_size_cm": VOXEL_CM,
        "grid_origin_ue_cm": list(origin_cm),
        "axes": "UE: X forward, Y right, Z up; "
                "origin at base center (floor contact)",
        "voxel_count": len(entries),
        "voxels": entries,
    }
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=2)
    return path


def build_debris():
    """Single 6 cm cube with a small bevel (< 100 tris)."""
    common.clear_scene()
    common.bpy.ops.mesh.primitive_cube_add(size=common.cm(6.0))
    obj = common.bpy.context.active_object
    obj.name = "SM_VoxelDebris"
    bevel = obj.modifiers.new("Bevel", "BEVEL")
    bevel.width = common.cm(0.4)
    bevel.segments = 1
    bevel.limit_method = "NONE"
    common.apply_all_transforms(obj)
    mat = common.get_or_make_material(
        "M_VoxelDebris", (0.5, 0.5, 0.55), None, 0.0,
        roughness=0.5)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    common.set_vertex_colors(
        obj.data, ["Debris"] * len(obj.data.polygons),
        {"Debris": ((0.5, 0.5, 0.55), None, 0.0)})
    common.origin_to_base_center(obj)
    common.apply_all_transforms(obj)
    return common.export_fbx(obj, "SM_VoxelDebris.fbx")


def main():
    common.ensure_dirs()
    results = [
        build_enemy(grasshopper_grid, "Enemy_Grasshopper",
                      "SM_Enemy_Grasshopper.fbx",
                      PALETTE_CRIMSON),
        build_enemy(wanderer_grid, "Enemy_Wanderer",
                      "SM_Enemy_Wanderer.fbx", PALETTE_AMBER),
        (build_debris(), None),
    ]
    for fbx, js in results:
        print("WROTE", fbx)
        if js:
            print("WROTE", js)


if __name__ == "__main__":
    main()
