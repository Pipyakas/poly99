# -*- coding: utf-8 -*-
"""
poly99+ - build the rigid hard-surface helmet (variant A) for the hero
MetaHuman and export it twice.

    blender -b --factory-startup --python armor/scripts/helmet_a.py

Construction
------------
The shell is fitted to the *actual* MetaHuman face mesh rather than eyeballed.
For a stack of horizontal sections, 36 rays are fired from the head axis; the
first hit is the outer surface, which is the one that has to be measured,
because the head is a scalp shell over hair over skull and walking to the
furthest hit would report the skull and throw the hair volume away.  Rays that
leave the head entirely (below the jaw, past the crown) get no hit and are
filled from the ring median; the vertex cloud then supplies the true radius, so
ears and jaw cannot end up outside the shell.

The measured profile is reshaped into armour: blended toward a rounded-rect
cross-section so it reads hard-surface rather than egg-shaped, with a domed
crown, a pinched chin and a flared neck seal that lands on the chest collar.

Everything above the shell is derived from the same loft grid, so the parts stay
registered:

* **visor** - recessed into the front arc only (120 degrees), dark, faceted
* **visor frame** - a raised border standing proud of the recessed visor
* **cheek / jaw guards** - angular plates on the lower sides
* **back-of-skull plate** - rear panel, proud, seam-bounded
* **trim** - thin cyan channels along the panel seams

Exports
-------
``SM_Helmet_A.fbx``   static; mesh data in the ``head`` bone's local space and
                      the object transform set to that bone's rest matrix, so
                      attaching it to the skeleton's ``head`` socket with an
                      identity relative transform seats it.
``SKM_Helmet_A.fbx``  same mesh, 100 % weighted to ``head`` (fallback path).
"""
import bisect
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import armor_common as C  # noqa: E402

NSEG = 32                     # rays per ring / loft segments
Z_SEAL = 146.0                # cm - bottom of the neck seal, meets the collar
Z_BOTTOM = 150.0              # cm - jaw line, first measured ring
Z_CROWN = 177.0               # cm - last reliably measured ring
Z_STEP = 2.8
APEX_LIFT = 4.6               # cm - height of the elliptical crown cap
AXIS_Y = 0.6                  # cm - head axis offset in +Y (forward)
SHELL_THICK = 0.85
MARGIN_SCALP = 2.6            # cm - cranium / hair volume
MARGIN_FACE = 1.9             # cm - face
MARGIN_JAW = 1.5              # cm - jaw / chin

VISOR_Z = (163.5, 174.0)      # cm - eye band
VISOR_HALF = math.radians(60.0)   # 120 deg total, front only
VISOR_RECESS = 0.55           # cm the visor sits inside the shell surface
# Angle of the character's front around the head axis.  The MetaHuman faces
# -Y, so the visor must be centred on -pi/2 - not +pi/2 as the first pass had,
# which put it on the back of the head.
FRONT_ANG = -math.pi / 2.0
BACK_ANG = math.pi / 2.0
CHEEK_HALF = math.radians(52.0)
BACK_HALF = math.radians(58.0)
CHEEK_Z = (150.5, 162.0)
BACK_Z = (164.0, 174.0)
SEAL_FLARE = ((149.4, 1.05), (147.6, 1.14), (146.0, 1.22))

SQUIRCLE_N = 3.1              # cross-section exponent (2 = circle, higher = angular)
PANEL = 0.62                 # how far the cross-section is pulled toward the squircle
# Applied parts stack outward from the loft surface, which the solidified shell
# already occupies out to SHELL_THICK - anything under that is buried.
FRAME_LIFT = SHELL_THICK + 0.62    # visor bezel
VISOR_LIFT = SHELL_THICK + 0.30    # visor face, inside the bezel
GUARD_LIFT = SHELL_THICK + 0.24    # cheek / jaw guards, back plate
TRIM_W = 0.26                # cm - trim channel width
LIFT_TRIM = SHELL_THICK + 0.26
BUDGET_TRIS = 8000


# --------------------------------------------------------------------------- #
def outermost_profile(bvh, z, axis_y=AXIS_Y, max_d=34.0):
    """Outer surface radius per angle around the head axis."""
    out = []
    start = Vector((0.0, axis_y, z))
    for i in range(NSEG):
        a = 2.0 * math.pi * i / NSEG
        d = Vector((math.cos(a), math.sin(a), 0.0))
        hit, _nor, _idx, dist = bvh.ray_cast(start, d, max_d)
        out.append(dist if hit is not None else None)
    good = sorted(h for h in out if h is not None)
    med = good[len(good) // 2] if good else 8.0
    return [med if h is None else h for h in out]


def smooth_ring(ring, passes=2):
    r = list(ring)
    for _ in range(passes):
        n = len(r)
        r = [(r[(i - 1) % n] + 2.0 * r[i] + r[(i + 1) % n]) / 4.0 for i in range(n)]
    return r


def smooth_stack(rings, passes=2):
    st = [list(r) for r in rings]
    for _ in range(passes):
        prev = st
        st = []
        for i in range(len(prev)):
            a, b, c = prev[max(0, i - 1)], prev[i], prev[min(len(prev) - 1, i + 1)]
            st.append([(a[k] + 2.0 * b[k] + c[k]) / 4.0 for k in range(len(b))])
    return st


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def ring_at(zs, target):
    return min(range(len(zs)), key=lambda i: abs(zs[i] - target))


def segs_around(centre, half):
    """Segment indices whose angle lies within `half` of `centre`."""
    out = []
    for i in range(NSEG):
        a = 2.0 * math.pi * i / NSEG
        d = abs((a - centre + math.pi) % (2.0 * math.pi) - math.pi)
        if d <= half:
            out.append(i)
    return out


def rows_in(zs, z0, z1):
    return [i for i, z in enumerate(zs) if z0 <= z <= z1]


# --------------------------------------------------------------------------- #
def build():
    arm, meshes = C.import_fbx(C.REF_FACE, ["FACE"])
    mats = C.make_materials()          # after read_factory_settings wipes the file
    face = meshes[0]
    bvh = C.bvh_of(face)

    zs = []
    z = Z_BOTTOM
    while z <= Z_CROWN + 1e-6:
        zs.append(z)
        z += Z_STEP
    prof = smooth_stack([smooth_ring(outermost_profile(bvh, zz)) for zz in zs],
                        passes=2)

    band = sorted(v for zz, r in zip(zs, prof) if 160.0 <= zz <= 176.0 for v in r)
    ref = band[len(band) // 2] if band else 7.0
    r_lo, r_hi = ref * 0.55, ref * 1.95
    vrad = sorted((v.co.z, math.hypot(v.co.x, v.co.y - AXIS_Y))
                  for v in face.data.vertices)

    def vertex_radius(zz, half=1.3):
        lo = bisect.bisect_left(vrad, (zz - half, -1e9))
        hi = bisect.bisect_right(vrad, (zz + half, 1e9))
        return max((vrad[i][1] for i in range(lo, hi)), default=0.0)

    def squircle(a, n=SQUIRCLE_N):
        c, s = abs(math.cos(a)), abs(math.sin(a))
        return (c ** n + s ** n) ** (-1.0 / n)

    rings = []
    for zz, r in zip(zs, prof):
        ring = []
        r_max = max(max(min(max(v, r_lo), r_hi) for v in r), vertex_radius(zz))
        for i, raw in enumerate(r):
            rad = min(max(raw, r_lo), r_hi)
            ang = 2.0 * math.pi * i / NSEG
            front = math.cos(ang - FRONT_ANG) > 0.0
            face_w = (1.0 - smoothstep(160.0, 168.0, zz)) * (1.0 if front else 0.0)
            jaw_w = 1.0 - smoothstep(Z_BOTTOM + 1.0, Z_BOTTOM + 8.0, zz)
            margin = (MARGIN_SCALP * (1.0 - face_w - jaw_w)
                      + MARGIN_FACE * face_w + MARGIN_JAW * jaw_w)
            r = (rad + margin) * (1.0 - PANEL) + r_max * squircle(ang) * PANEL
            chin = 1.0 - 0.20 * jaw_w
            ring.append(max(r * chin, rad + 0.4))
        rings.append(ring)
    print("  head reference radius %.2f cm" % ref)

    # Elliptical crown, generated rather than measured (rays graze the skull
    # tangentially up here and report a wide flat disc).  The last ring keeps a
    # real radius: capping a near-degenerate ring leaves a pinhole after bevel.
    top_ring = rings[-1]
    for k in range(1, 5):
        t = k / 4.0
        zs.append(Z_CROWN + APEX_LIFT * math.sin(t * math.pi / 2.0))
        rings.append([max(1.45, v * math.cos(t * math.pi / 2.0)) for v in top_ring])

    # Neck seal: three flared rings below the jaw, sized from the jaw ring
    # rather than from the measured profile - down there the horizontal rays
    # leave the neck and hit the *shoulders*, which would flare the helmet into
    # a skirt the width of the upper body.
    jaw = rings[0]
    for zz, k in reversed(SEAL_FLARE):
        zs.insert(0, zz)
        rings.insert(0, [v * k for v in jaw])
    zs.sort()
    rings.sort(key=lambda _r: 0)       # stable; zs/rings are parallel lists

    pts = []
    for zz, ring in zip(zs, rings):
        for i, rad in enumerate(ring):
            a = 2.0 * math.pi * i / NSEG
            pts.append(Vector((rad * math.cos(a), AXIS_Y + rad * math.sin(a), zz)))

    def gv(ri, si):
        return pts[ri * NSEG + si % NSEG]

    def outward(v):
        r = Vector((v.x, v.y - AXIS_Y, 0.0))
        return r.normalized() if r.length > 1e-6 else Vector((0.0, 0.0, 1.0))

    def orient(bm):
        """Force every face normal to point away from the head axis.

        `outward()` is radial, so it is blind on the horizontal crown cap - its
        dot is ~0 and a downward-facing cap survives, rendering as a dark
        pinhole.  Faces above the crown are therefore oriented by +Z instead.
        """
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        for f in bm.faces:
            c = f.calc_center_median()
            ref = Vector((0.0, 0.0, 1.0)) if c.z > Z_CROWN else outward(c)
            if f.normal.dot(ref) < 0.0:
                f.normal_flip()

    def panel(name, row_ids, seg_ids, mat, lift=0.0, inward=0.0, thick=0.30,
              squeeze=None, z_centre=None, skip=None):
        """A quad patch lifted off (or sunk into) the loft surface.

        `skip` is a set of (row, seg) quads to leave out, which is what turns a
        patch into a *ring*: the visor bezel covers the same grid cells as the
        visor, and without the hole it was a solid panel sitting in front of it,
        so the visor was never visible in any preview.
        """
        bm = bmesh.new()
        made = 0
        for ri in row_ids:
            if ri + 1 >= len(rings):
                continue
            for si in seg_ids:
                if skip is not None and (ri, si) in skip:
                    continue
                vs = []
                for p in (gv(ri, si), gv(ri, si + 1),
                          gv(ri + 1, si + 1), gv(ri + 1, si)):
                    d = outward(p)
                    vs.append(bm.verts.new(p - d * inward + d * lift))
                if squeeze is not None and z_centre is not None:
                    for v in vs:
                        v.co.z = z_centre + (v.co.z - z_centre) * squeeze
                try:
                    bm.faces.new(vs)
                    made += 1
                except ValueError:
                    pass
        if not made:
            bm.free()
            return None
        orient(bm)
        bm.normal_update()
        ob = C.new_object(name, bm)
        ob.matrix_world = face.matrix_world.copy()
        if thick > 0.0:
            C.activate(ob)
            m = ob.modifiers.new("solid", 'SOLIDIFY')
            m.thickness = thick
            m.offset = 1.0
            m.use_rim = True
            bpy.ops.object.modifier_apply(modifier=m.name)
        C.shade_flat(ob)
        C.assign_material(ob, mat)
        return ob

    # ---- shell ------------------------------------------------------------ #
    sections = [pts[i * NSEG:(i + 1) * NSEG] for i in range(len(rings))]
    bm = C.loft(sections, cap_start=False, cap_end=True, close=True)
    orient(bm)
    bm.normal_update()
    shell = C.new_object("Helmet_Shell", bm)
    shell.matrix_world = face.matrix_world.copy()
    C.activate(shell)
    C.smooth_relax(shell, iterations=2, factor=0.22)
    # No planar decimate here: the crown cap and the last crown ring are nearly
    # coplanar, and DISSOLVE merges them away, leaving a hole at the apex.  The
    # quad grid plus flat shading already give the faceted read.
    C.activate(shell)
    m = shell.modifiers.new("solid", 'SOLIDIFY')
    m.thickness = SHELL_THICK
    m.offset = 1.0
    m.use_rim = True
    bpy.ops.object.modifier_apply(modifier=m.name)
    C.bevel(shell, width=0.16, segments=1, angle=38.0)
    C.shade_flat(shell)
    C.assign_material(shell, mats["M_ArmorPrimary"])
    _assert_closed(shell, "shell")
    parts = [shell]

    # ---- visor: raised bezel with the visor sitting inside it -------------- #
    # Every applied part has to clear SHELL_THICK, otherwise it sits *inside*
    # the solidified shell and is invisible - the shell's outer surface is
    # loft + SHELL_THICK, not loft.
    vis_rows = rows_in(zs, VISOR_Z[0], VISOR_Z[1])
    vis_segs = segs_around(FRONT_ANG, VISOR_HALF)
    frame_rows = rows_in(zs, VISOR_Z[0] - 2.6, VISOR_Z[1] + 2.6)
    frame_segs = segs_around(FRONT_ANG, VISOR_HALF + 13.0)
    frame = panel("Helmet_VisorFrame", frame_rows, frame_segs,
                  mats["M_ArmorSecondary"], lift=FRAME_LIFT, thick=0.40,
                  skip={(ri, si) for ri in vis_rows for si in vis_segs})
    visor = panel("Helmet_Visor", vis_rows, vis_segs, mats["M_Visor"],
                  lift=VISOR_LIFT, thick=0.30)
    if frame:
        parts.append(frame)
    if visor:
        parts.append(visor)
        print("  visor: %d tris" % C.tri_count(visor.data))

    # ---- cheek / jaw guards ------------------------------------------------ #
    for sd, centre in (("l", 0.0), ("r", math.pi)):
        g = panel("Helmet_CheekGuard_" + sd,
                  rows_in(zs, CHEEK_Z[0], CHEEK_Z[1]),
                  segs_around(centre, CHEEK_HALF), mats["M_ArmorPrimary"],
                  lift=GUARD_LIFT, thick=0.40)
        if g:
            parts.append(g)

    # ---- back-of-skull plate ----------------------------------------------- #
    back = panel("Helmet_BackPlate", rows_in(zs, BACK_Z[0], BACK_Z[1]),
                 segs_around(BACK_ANG, BACK_HALF), mats["M_ArmorSecondary"],
                 lift=GUARD_LIFT, thick=0.40)
    if back:
        parts.append(back)

    # ---- cyan trim along the panel seams ------------------------------------ #
    def trim(name, row_ids, seg_ids, z_centre):
        t = panel(name, row_ids, seg_ids, mats["M_ArmorEmissive"],
                  lift=LIFT_TRIM, thick=0.0,
                  squeeze=TRIM_W / max(1e-6, Z_STEP), z_centre=z_centre)
        if t:
            parts.append(t)

    if vis_rows:
        trim("Helmet_TrimBrow", [vis_rows[0]], vis_segs, zs[vis_rows[0]])
        trim("Helmet_TrimCrown", [ring_at(zs, Z_CROWN)], range(NSEG), Z_CROWN)
        trim("Helmet_TrimSeal", [ring_at(zs, SEAL_FLARE[-1][0])], range(NSEG),
             SEAL_FLARE[-1][0])
        for sd, centre in (("l", 0.0), ("r", math.pi)):
            trim("Helmet_TrimCheek_" + sd, [ring_at(zs, CHEEK_Z[1])],
                 segs_around(centre, CHEEK_HALF), CHEEK_Z[1])
    return arm, face, parts


def _assert_closed(ob, label):
    """A hole in the crown reads as an open jar in every preview."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    open_edges = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    bm.free()
    if open_edges:
        print("  !! %s has %d open edges (rim excluded by design? check crown)"
              % (label, open_edges))


# --------------------------------------------------------------------------- #
def main():
    arm, face, parts = build()
    tris = sum(C.tri_count(o.data) for o in parts)
    print("helmet tris: %d (budget %d) %s"
          % (tris, BUDGET_TRIS, "OK" if tris < BUDGET_TRIS else "OVER!"))
    if tris >= BUDGET_TRIS:
        raise SystemExit("helmet triangle budget exceeded: %d" % tris)

    hb = arm.matrix_world @ arm.data.bones["head"].matrix_local
    print("head bone origin (world, m): (%.4f, %.4f, %.4f)"
          % (hb[0][3], hb[1][3], hb[2][3]))

    # ---------------- SM_Helmet_A.fbx : static, seated on the head bone ----- #
    # The shell is lofted in *character* space (Z up, cm, +Y forward).  The
    # static FBX has to carry its geometry in the `head` bone's *local* space
    # with the object transform set to that bone's rest matrix, so the mesh is
    # first pushed through bone.matrix_local.inverted().  Round trip:
    #     world = hb @ (bone.matrix_local^-1 @ char) = arm.matrix_world @ char
    bone = arm.data.bones["head"]
    inv = bone.matrix_local.inverted()
    for ob in parts:
        for v in ob.data.vertices:
            v.co = inv @ v.co
        ob.data.update()
        ob.matrix_world = hb
    joined = C.join_objects(parts, "SM_Helmet_A")
    joined.matrix_world = hb
    C.smart_uv(joined)
    C.export_fbx(None, [joined], os.path.join(C.EXPORT_DIR, "SM_Helmet_A.fbx"))

    # ---------------- SKM_Helmet_A.fbx : 100 % weighted to head ----------- #
    C.fresh_scene()
    bpy.ops.import_scene.fbx(filepath=C.REF_BODY)
    arm2 = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    arm2.name = "root"
    arm2.data.name = "root"
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=os.path.join(C.EXPORT_DIR, "SM_Helmet_A.fbx"))
    new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    assert len(new) == 1, "expected exactly one static helmet mesh, got %d" % len(new)
    st = new[0]
    st.name = "SKM_Helmet_A"
    st.data.name = "SKM_Helmet_A"
    vg = st.vertex_groups.new(name="head")
    vg.add(list(range(len(st.data.vertices))), 1.0, 'REPLACE')
    # Under FBX_SCALE_CUSTOM the node scale Blender writes is
    # 100 * matrix_basis scale (the metre->cm factor), so the basis must keep
    # arm.matrix_world's 0.01 in it to land on a unit node scale - exactly the
    # shape the body armour slots already have.  Setting the parent inverse to
    # identity, or using the bare bone matrix, leaks a 100x error into the FBX.
    C.parent_to_armature([st], arm2, like=st)
    st.matrix_basis = (arm2.matrix_world
                       @ arm2.data.bones["head"].matrix_local)
    C.export_fbx(arm2, [st], os.path.join(C.EXPORT_DIR, "SKM_Helmet_A.fbx"))
    print("DONE")


if __name__ == "__main__":
    main()