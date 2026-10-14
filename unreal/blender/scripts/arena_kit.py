"""Modular arena kit for poly99 on a 400 cm grid.

Exports (one FBX each, < 5k tris, pivots at base center):
  SM_Floor_Tile_400  400x400x10 cm panel, seams as geometry,
                     separate emissive grid strips
  SM_Wall_400        400 long (X), 120 tall, 40 thick,
                     glowing trim line
  SM_Wall_Corner     corner joining two walls at 90 degrees
  SM_Pillar          80x80x300 cm
  SM_Edge_GlowStrip  400 long glow strip
  SM_Spawn_Gate      enemy spawn portal frame ~300 wide

Each part is a merged set of flat-shaded boxes; per-box
material roles become material slots + flat vertex colors.
"""

import bmesh
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common  # noqa: E402
from common import bpy  # noqa: E402

GRID = 400.0  # cm

# Roles: name -> (rgb, emissive_rgb, emissive_strength, roughness)
ROLES = {
    "FloorBase": ((0.30, 0.32, 0.38), None, 0.0, 0.75),
    "FloorGrid": ((0.10, 0.75, 0.85), (0.10, 0.75, 0.85), 4.0, 0.4),
    "WallTrim": ((0.10, 0.70, 0.85), (0.15, 0.80, 0.90), 3.0, 0.4),
    "WallBody": ((0.38, 0.40, 0.48), None, 0.0, 0.7),
    "WallDark": ((0.18, 0.20, 0.26), None, 0.0, 0.8),
    "Glow": ((1.0, 0.85, 0.35), (1.0, 0.75, 0.25), 8.0, 0.3),
}

# Outward-wound quad faces of a unit cube, corner index bits
# (dx, dy, dz) -> i = dx + dy * 2 + dz * 4.
CUBE_FACES = (
    (0, 2, 3, 1),   # -Z
    (4, 5, 7, 6),   # +Z
    (0, 1, 5, 4),   # -Y
    (2, 6, 7, 3),   # +Y
    (0, 4, 6, 2),   # -X
    (1, 3, 7, 5),   # +X
)


def merged(name, boxes):
    """Merge boxes into one flat-shaded mesh.

    boxes: list of dicts {s:(sx,sy,sz), c:(cx,cy,cz), role:...}
    with sizes and centers in centimeters.
    """
    verts = []
    faces = []
    roles = []
    for spec in boxes:
        sx, sy, sz = spec["s"]
        cx, cy, cz = spec["c"]
        base = len(verts)
        for dx in (-0.5, 0.5):
            for dy in (-0.5, 0.5):
                for dz in (-0.5, 0.5):
                    verts.append((
                        common.cm(cx + dx * sx),
                        common.cm(cy + dy * sy),
                        common.cm(cz + dz * sz)))
        faces.extend(tuple(base + i for i in f)
                     for f in CUBE_FACES)
        roles.extend([spec["role"]] * 6)

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

    mesh.materials.clear()
    slot = {}
    for role in roles:
        if role not in slot:
            slot[role] = len(mesh.materials)
            r = ROLES[role]
            mesh.materials.append(common.get_or_make_material(
                "M_" + role, r[0], emissive_color=r[1],
                emissive_strength=r[2], roughness=r[3]))
    for poly_idx, role in enumerate(roles):
        mesh.polygons[poly_idx].material_index = slot[role]
    common.set_vertex_colors(
        mesh, roles,
        {k: (v[0], v[1], v[2]) for k, v in ROLES.items()})
    return obj


# ------------------------------------------------------------------ parts

def floor_tile():
    """400x400x10 cm floor panel: raised inset tiles, seams
    as geometry, emissive grid strips (M_FloorGrid)."""
    boxes = [
        {"s": (400, 400, 10), "c": (0, 0, 5), "role": "FloorBase"},
    ]
    for i in range(4):
        for j in range(4):
            boxes.append({
                "s": (94, 94, 1.2),
                "c": (-150 + i * 100, -150 + j * 100, 9.4),
                "role": "FloorBase",
            })
    for i in range(5):
        pos = -200 + i * 100
        # Strips recessed into the top face; the
        # outermost pair stops 0.8 cm short of the
        # panel edge so nothing overhangs 400x400.
        edge = pos * 0.996 if pos in (-200, 200) else pos
        boxes.append({
            "s": (399.2, 1.6, 1.0),
            "c": (0, edge, 9.4), "role": "FloorGrid"})
        boxes.append({
            "s": (1.6, 399.2, 1.0),
            "c": (edge, 0, 9.4), "role": "FloorGrid"})
    return merged("SM_Floor_Tile_400", boxes)


def wall_400():
    boxes = [
        {"s": (400, 40, 120), "c": (0, 0, 60), "role": "WallBody"},
        {"s": (380, 42, 70), "c": (0, 0, 65), "role": "WallDark"},
        {"s": (300, 43, 40), "c": (0, 0, 70), "role": "WallBody"},
        {"s": (400, 44, 12), "c": (0, 0, 6), "role": "WallDark"},
        {"s": (400, 44, 8), "c": (0, 0, 116), "role": "WallDark"},
        {"s": (400, 45, 2.4), "c": (0, 0, 96), "role": "WallTrim"},
        {"s": (6, 45, 6), "c": (-196, 0, 30), "role": "WallTrim"},
        {"s": (6, 45, 6), "c": (196, 0, 30), "role": "WallTrim"},
    ]
    return merged("SM_Wall_400", boxes)


def wall_corner():
    """Corner piece for one 400x400 cm grid cell:
    two arms run from the corner (at local origin)
    along -X and -Y, each 400 long."""
    boxes = [
        # Arm along -Y.
        {"s": (40, 400, 120), "c": (0, -200, 60),
         "role": "WallBody"},
        # Arm along -X.
        {"s": (400, 40, 120), "c": (-200, 0, 60),
         "role": "WallBody"},
        # Corner column.
        {"s": (48, 48, 124), "c": (0, 0, 62),
         "role": "WallDark"},
        # Trim lines continuing both directions.
        {"s": (40, 45, 2.4), "c": (0, -200, 96),
         "role": "WallTrim"},
        {"s": (45, 40, 2.4), "c": (-200, 0, 96),
         "role": "WallTrim"},
        {"s": (48, 49, 2.4), "c": (0, 0, 96),
         "role": "WallTrim"},
    ]
    return merged("SM_Wall_Corner", boxes)


def pillar():
    """80x80x300 cm pillar with an inset dark
    core and emissive spine faces."""
    boxes = [
        {"s": (80, 80, 300), "c": (0, 0, 150), "role": "WallBody"},
        {"s": (64, 64, 300), "c": (0, 0, 150), "role": "WallDark"},
        # Base and capital (flush 80x80, taller).
        {"s": (80, 80, 24), "c": (0, 0, 12),
         "role": "WallDark"},
        {"s": (80, 80, 24), "c": (0, 0, 288),
         "role": "WallDark"},
        # Emissive spine flush with the +X / -X
        # faces (80x80 footprint preserved).
        {"s": (1, 12, 260), "c": (39.5, 0, 150),
         "role": "WallTrim"},
        {"s": (1, 12, 260), "c": (-39.5, 0, 150),
         "role": "WallTrim"},
    ]
    return merged("SM_Pillar", boxes)


def edge_glow_strip():
    boxes = [
        {"s": (400, 4, 2), "c": (0, 0, 1), "role": "Glow"},
        {"s": (400, 6, 0.8), "c": (0, 0, 0.4), "role": "WallDark"},
    ]
    return merged("SM_Edge_GlowStrip", boxes)


def spawn_gate():
    """Enemy spawn portal frame ~300 cm wide
    (outer 300 cm including posts)."""
    boxes = [
        # Two posts (centers at +-135 -> outer 300).
        {"s": (30, 40, 260), "c": (-135, 0, 130),
         "role": "WallBody"},
        {"s": (30, 40, 260), "c": (135, 0, 130),
         "role": "WallBody"},
        # Lintel.
        {"s": (300, 40, 30), "c": (0, 0, 245),
         "role": "WallBody"},
        # Inner glow plane (the portal itself).
        {"s": (240, 2, 200), "c": (0, 0, 115),
         "role": "Glow"},
        # Trim accents.
        {"s": (30, 44, 2.4), "c": (-135, 0, 60),
         "role": "WallTrim"},
        {"s": (30, 44, 2.4), "c": (135, 0, 60),
         "role": "WallTrim"},
        {"s": (300, 44, 2.4), "c": (0, 0, 228),
         "role": "WallTrim"},
        # Base runners (keep the outer edge at 300).
        {"s": (34, 48, 8), "c": (-133, 0, 4),
         "role": "WallDark"},
        {"s": (34, 48, 8), "c": (133, 0, 4),
         "role": "WallDark"},
    ]
    return merged("SM_Spawn_Gate", boxes)


BUILDERS = [
    ("SM_Floor_Tile_400", floor_tile),
    ("SM_Wall_400", wall_400),
    ("SM_Wall_Corner", wall_corner),
    ("SM_Pillar", pillar),
    ("SM_Edge_GlowStrip", edge_glow_strip),
    ("SM_Spawn_Gate", spawn_gate),
]


def main():
    common.ensure_dirs()
    for name, builder in BUILDERS:
        common.clear_scene()
        obj = builder()
        common.origin_to_base_center(obj)
        common.apply_all_transforms(obj)
        obj.name = name
        obj.data.name = name
        path = common.export_fbx(obj, name + ".fbx")
        tris = len(obj.data.polygons)
        print("WROTE", path, "tris:", tris)
        assert tris < 5000, name + " exceeds 5k tris: " + str(tris)


if __name__ == "__main__":
    main()
