# -*- coding: utf-8 -*-
"""
poly99+ armor pipeline - verification.

    blender -b --factory-startup --python armor/scripts/verify.py

1. Re-imports every exported FBX into an empty scene: triangle count, bone count,
   bone names subset of the reference skeleton, and rest-pose round-trip
   comparison against the reference FBX.
2. Builds one scene with the reference body + all armor slots, poses the rig in
   four test poses and measures how much skin is exposed (and how much armor
   pokes through the skin).
3. Renders Workbench previews (front / side / 3-4 top-down) per pose plus
   helmet on/off renders against the MetaHuman face mesh.
"""
import json
import math
import os
import sys

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import armor_common as C  # noqa: E402
import fbx_probe as P  # noqa: E402

ARMOR_FILES = ["SKM_Armor_Chest.fbx", "SKM_Armor_Shoulders.fbx", "SKM_Armor_Arms.fbx",
               "SKM_Armor_Hands.fbx", "SKM_Armor_Legs.fbx", "SKM_Armor_Feet.fbx",
               "SKM_Armor_Back.fbx"]
HELMET_STATIC = "SM_Helmet_A.fbx"
HELMET_SKINNED = "SKM_Helmet_A.fbx"
RAY_LEN = 0.06          # metres - 6 cm coverage probe (the brief's definition)
NEAR_LIMIT = 0.03       # metres - gated coverage: first surface along the normal
COVERAGE_TARGET = 1.0   # percent - body verts allowed to be further than 3 cm
SIDE_TARGET = 1.0       # percent - same limit applied to ONE side, never averaged
SIDE_CM = 1.0           # cm - |rest x| below this is the midline, counted as neither
# SIGNED clearance gate.  The armour must sit OUTSIDE the skin: positive means
# outside, negative means inside the body and therefore rendered behind it in
# Unreal.  0.5 mm of margin absorbs float error without hiding a real defect -
# a thigh undersuit 1 cm inside scores -10 mm, which is 20x this threshold.
SIGNED_MIN = 0.0005     # metres - required signed clearance along +normal
SIGNED_TARGET = 0.0     # percent of verts allowed at or below SIGNED_MIN
# The gated quantity.  A MISS is a body vertex with NO armour surface at all
# along its outward normal: the body renders in front of nothing there.  That
# is the defect this pipeline shipped (the thigh) and it is categorically
# different from a coplanar hit, which still has armour in front and is only a
# z-fighting risk.  Gating on misses-per-side is what actually catches it.
MISS_TARGET = 1.0       # percent of one side allowed to miss entirely
# Acceptance criterion from the composer: no visible body skin in the top-down
# gameplay camera at 1280x960 with the spring arm between 2.3 m and 4.3 m.
UE_RES = (1280, 960)
UE_ARMS = (2.3, 3.3, 4.3)
UE_VIEWS = (("cam28", 28.0, 0.0), ("top", 55.0, 0.0), ("side", 22.0, 62.0))
BARE_TARGET = 0.05      # percent of body silhouette pixels allowed to be bare
NECK_CUT_Z = 1.42       # metres: body vertices above this are neck/head, excluded
HELMET_HEAD_Z = 1.52    # metres: face-FBX vertices above this count as "head"

report = {"exports": [], "poses": [], "helmet": [], "scale": [],
          "coverage_target": COVERAGE_TARGET,
          "side_target": SIDE_TARGET,
          "miss_target": MISS_TARGET,
          "signed_min_gate_mm": SIGNED_MIN * 1000.0,
          "gate": "gap3cm_pct = %% of body verts whose FIRST armour hit along "
                  "+normal is further than NEAR_LIMIT; nearest_far_pct is the "
                  "independent nearest-surface measure (holes)"}

# Unreal reads the FBX header literally: what it puts on screen is the raw
# vertex array scaled by the node transform.  Blender's importer normalises all
# of that away, so an import round trip can never catch a wrong unit
# declaration - it always agrees with itself.  These are the sizes UE will see.
SCALE_REF_Z_CM = (145.0, 155.0)     # reference body, neck-down
SCALE_CHEST_Z_CM = (60.0, 70.0)     # SKM_Armor_Chest
SCALE_HELMET_Z_CM = (20.0, 40.0)    # helmet shell, in head-bone local space
SCALE_REF_FACTOR = 1.0              # UnitScaleFactor the reference declares


def check_scale():
    """Raw-FBX unit check, measured without going through Blender's importer."""
    print("\n=== 0. UE unit convention (raw FBX, no importer) ===")
    ref = P.report(C.REF_BODY)
    print("%-28s %-9s %-11s %-9s %s"
          % ("file", "usf", "raw z cm", "node sc", "UE size (cm)"))
    rows = [{"file": "reference/" + ref["file"], "unit_scale_factor":
             ref["unit_scale_factor"], "raw_cm": ref["size"],
             "z_span_cm": ref["size"][2], "node_scale_ok": True,
             "reference": True}]
    failures = []
    if abs(float(ref["unit_scale_factor"]) - SCALE_REF_FACTOR) > 1e-6:
        failures.append("reference UnitScaleFactor %s != %s"
                        % (ref["unit_scale_factor"], SCALE_REF_FACTOR))

    limits = {"SKM_Armor_Chest.fbx": SCALE_CHEST_Z_CM,
              "SM_Helmet_A.fbx": SCALE_HELMET_Z_CM,
              "SKM_Helmet_A.fbx": SCALE_HELMET_Z_CM}
    for fn in ARMOR_FILES + [HELMET_STATIC, HELMET_SKINNED]:
        path = os.path.join(C.EXPORT_DIR, fn)
        if not os.path.exists(path):
            continue
        r = P.report(path)
        objs = P.objects(path)
        scaled = 0
        for m in objs.prefix('Model'):
            for _sub, v in P.p70_vector(P.p70_entries(m), 'Lcl Scaling'):
                if abs(v - 1.0) > 1e-4:
                    scaled += 1
        usf = r["unit_scale_factor"]
        z = r["size"][2]
        ok = (abs(float(usf) - SCALE_REF_FACTOR) < 1e-6 and scaled == 0)
        lim = limits.get(fn)
        if lim and not (lim[0] <= z <= lim[1]):
            ok = False
            failures.append("%s z span %.2f cm outside %s" % (fn, z, lim))
        print("%-28s %-9s %-11.3f %-9s %s"
              % (fn, usf, z, "unit" if scaled == 0 else "%d scaled" % scaled,
                 "%.1f x %.1f x %.1f" % (r["size"][0], r["size"][1], z)))
        if abs(float(usf) - SCALE_REF_FACTOR) >= 1e-6:
            failures.append("%s: UnitScaleFactor %s != %s" % (fn, usf, SCALE_REF_FACTOR))
        if scaled:
            failures.append("%s: %d node(s) carry a non-unit Lcl Scaling"
                            % (fn, scaled))
        rows.append({"file": fn, "unit_scale_factor": usf, "raw_cm": r["size"],
                     "z_span_cm": z, "node_scale_ok": scaled == 0,
                     "expected_z_cm": lim, "ok": ok, "reference": False})
    print("  reference body z span %.2f cm; expected %s"
          % (ref["size"][2], "%s" % (SCALE_REF_Z_CM,)))
    if not (SCALE_REF_Z_CM[0] <= ref["size"][2] <= SCALE_REF_Z_CM[1]):
        failures.append("reference z span %.2f cm outside %s"
                        % (ref["size"][2], SCALE_REF_Z_CM))
    report["scale"] = rows
    if failures:
        for f in failures:
            print("  !! SCALE: %s" % f)
        raise SystemExit("FBX unit convention check failed: %s" % "; ".join(failures))
    print("  all exports: UnitScaleFactor 1.0, unit node scales, cm coordinates")


# --------------------------------------------------------------------------- #
def world_bvh(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    verts, tris = [], []
    for ob in objs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        mw = ev.matrix_world
        off = len(verts)
        verts.extend([mw @ v.co for v in me.vertices])
        tris.extend([[t.vertices[0] + off, t.vertices[1] + off, t.vertices[2] + off]
                     for t in me.loop_triangles])
        ev.to_mesh_clear()
    # epsilon fattens the triangles so a ray that grazes a plate rim is not
    # lost to edge-on precision (0.4 mm, two orders below the 6 cm probe)
    return BVHTree.FromPolygons(verts, tris, all_triangles=True, epsilon=0.0004)


def deformed_body(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    mw = ev.matrix_world
    co = [mw @ v.co for v in me.vertices]
    nr = [(mw.to_3x3() @ v.normal).normalized() for v in me.vertices]
    n = len(co)
    tris = [[t.vertices[0], t.vertices[1], t.vertices[2]] for t in me.loop_triangles]
    ev.to_mesh_clear()
    return co, nr, tris


# --------------------------------------------------------------------------- #
# 1. round trip
# --------------------------------------------------------------------------- #
def check_exports():
    C.fresh_scene()
    bpy.ops.import_scene.fbx(filepath=C.REF_BODY)
    ref_arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    ref_rest = {b.name: (Vector(b.head_local), Vector(b.tail_local))
                for b in ref_arm.data.bones}
    ref_world = {b.name: (ref_arm.matrix_world @ b.head_local,
                          ref_arm.matrix_world @ b.tail_local)
                 for b in ref_arm.data.bones}
    ref_arm.name = "REF"
    ref_arm.data.name = "REF"

    print("\n=== 1. exported FBX round trip ===")
    print("%-26s %7s %6s %6s %9s %s"
          % ("file", "tris", "bones", "meshes", "rest_dev", "status"))
    for fn in ARMOR_FILES + [HELMET_STATIC, HELMET_SKINNED]:
        path = os.path.join(C.EXPORT_DIR, fn)
        if not os.path.exists(path):
            print("%-26s %s" % (fn, "MISSING"))
            report["exports"].append({"file": fn, "status": "missing"})
            continue
        for ob in list(bpy.context.scene.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.ops.import_scene.fbx(filepath=path)
        arm = next((o for o in bpy.context.scene.objects if o.type == 'ARMATURE'), None)
        meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
        tris = sum(C.tri_count(o.data) for o in meshes)
        if arm is None:                      # static helmet: no skeleton expected
            ok_bones, dev, status = True, 0.0, "static mesh (no skeleton)"
            nb = 0
        else:
            nb = len(arm.data.bones)
            extra = [b.name for b in arm.data.bones if b.name not in ref_rest]
            dev = 0.0
            wdev = 0.0
            for b in arm.data.bones:
                r = ref_rest.get(b.name)
                if r:
                    dev = max(dev, (b.head_local - r[0]).length,
                              (b.tail_local - r[1]).length)
                    rw = ref_world[b.name]
                    wdev = max(wdev, ((arm.matrix_world @ b.head_local) - rw[0]).length,
                               ((arm.matrix_world @ b.tail_local) - rw[1]).length)
            dev = wdev
            ok_bones = not extra and set(b.name for b in arm.data.bones) <= set(ref_rest)
            status = "OK" if ok_bones and dev < 1e-4 else \
                ("EXTRA BONES: %s" % extra[:4] if extra else "REST MISMATCH")
        print("%-26s %7d %6d %6d %9.5f %s"
              % (fn, tris, nb, len(meshes), dev, status))
        report["exports"].append({"file": fn, "tris": tris, "bones": nb,
                                  "meshes": len(meshes), "rest_dev": dev,
                                  "status": status})
    for ob in list(bpy.context.scene.objects):
        bpy.data.objects.remove(ob, do_unlink=True)


# --------------------------------------------------------------------------- #
# 2. poses
# --------------------------------------------------------------------------- #
def bone_chain(arm, name):
    chain, cur = [], arm.data.bones.get(name)
    while cur:
        chain.append(cur.name)
        cur = cur.parent
    return list(reversed(chain))


def rotate_world(arm, names, axis, degrees):
    R = Matrix.Rotation(math.radians(degrees), 3, axis)
    for nm in names:
        pb = arm.pose.bones.get(nm)
        if pb is None:
            continue
        M = pb.bone.matrix_local.to_3x3()
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (M.inverted() @ R @ M).to_quaternion()


def rotate_hinge(arm, names, degrees):
    """Curl a bone about *its own* hinge.

    rotate_world() applies one world-space axis to every bone in the list, which
    is right for limbs but wrong for fingers: a phalanx chain points along a
    different world direction on each side of the hand and at every joint, so a
    shared axis splayed the digits sideways instead of curling them.  A bone's
    local X is its own flexion hinge (local Y runs down the bone), so rotating
    there curls each phalanx correctly whatever the hand's orientation.
    """
    q = Matrix.Rotation(math.radians(degrees), 3, 'X').to_quaternion()
    for nm in names:
        pb = arm.pose.bones.get(nm)
        if pb is None:
            continue
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = q


BONE_SET = set()          # filled in once a rig is in the scene

# The composer logged live bone rotations out of PIE for the exact frame that
# produced the skin-coloured-thigh capture.  Unreal reports them in
# parent-bone space as (pitch, yaw, roll) in degrees; UE's FRotator composes
# those as Rz(yaw) * Ry(pitch) * Rx(roll), which is exactly Blender's XYZ euler
# order with (x, y, z) = (roll, pitch, yaw).  Applied through rotate_hinge, a
# bone-local rotation, which is what both engines mean by "relative to the
# parent bone".  The forward leg is thigh_r at +33 deg pitch.
UE_LOCOMOTION = [
    ("thigh_l", -16.0, -5.0, -18.0),
    ("calf_l", 0.0, -2.0, 16.0),
    ("foot_l", 3.0, 6.0, 2.0),
    ("thigh_r", 33.0, 13.0, -179.0),
    ("calf_r", 0.0, -1.0, 14.0),
    ("foot_r", 5.0, 10.0, -10.0),
    ("clavicle_l", -10.0, 101.0, -5.0),
    ("upperarm_l", -4.0, 64.0, -1.0),
    ("spine_05", 2.0, 0.0, 0.0),
]


POSES = {
    "rest": [],
    "arms_forward": [
        (["clavicle_l", "clavicle_r"], 'Z', 6.0),
        (["upperarm_l", "upperarm_r"], 'X', 88.0),
        (["lowerarm_l", "lowerarm_r"], 'X', 6.0),
        (["hand_l", "hand_r"], 'X', -4.0),
    ],
    "deep_lunge": [
        (["thigh_l"], 'X', 72.0),
        (["calf_l"], 'X', -86.0),
        (["ball_l", "foot_l"], 'X', -30.0),
        (["thigh_r"], 'X', -42.0),
        (["calf_r"], 'X', 16.0),
        (["ball_r", "foot_r"], 'X', 12.0),
        (["spine_01", "spine_02"], 'X', -8.0),
        (["upperarm_l", "upperarm_r"], 'X', 30.0),
    ],
    "twist_aim": [
        (["spine_01", "spine_02", "spine_03", "spine_04"], 'Z', 35.0),
        (["clavicle_l"], 'Y', -12.0),
        (["clavicle_r"], 'Y', 12.0),
        (["upperarm_l", "upperarm_r"], 'X', 84.0),
        (["lowerarm_l", "lowerarm_r"], 'X', 14.0),
    ],
    # A walk-cycle frame: the legs genuinely split, which is the one thing the
    # rest/A poses never do.  Every pose here rotates about a *world* axis, so
    # the left and right legs take opposite signs of the same angle - that is
    # what a stride is.
    "walk_stride": [
        (["thigh_l"], 'X', -26.0),
        (["calf_l"], 'X', 34.0),
        (["ball_l"], 'X', -12.0),
        (["thigh_r"], 'X', 22.0),
        (["calf_r"], 'X', -8.0),
        (["ball_r"], 'X', 16.0),
        (["upperarm_l"], 'X', -24.0),
        (["lowerarm_l"], 'X', 18.0),
        (["upperarm_r"], 'X', 20.0),
        (["lowerarm_r"], 'X', -14.0),
        (["spine_01"], 'X', 4.0),
    ],
    # The opposite foot forward, so neither the left nor the right leg is always
    # the leading one.  A per-side bug that only shows on the leading leg has to
    # be caught in both halves of the cycle.
    "walk_stride_b": [
        (["thigh_l"], 'X', 22.0),
        (["calf_l"], 'X', -8.0),
        (["ball_l"], 'X', 16.0),
        (["thigh_r"], 'X', -26.0),
        (["calf_r"], 'X', 34.0),
        (["ball_r"], 'X', -12.0),
        (["upperarm_l"], 'X', 20.0),
        (["lowerarm_l"], 'X', -14.0),
        (["upperarm_r"], 'X', -24.0),
        (["lowerarm_r"], 'X', 18.0),
        (["spine_01"], 'X', 4.0),
    ],
    # Wide stance, knees driven apart.  This is the pose that exposes the inner
    # thigh: at rest the legs touch, so an inner-thigh normal hits the *other*
    # leg's armour within 3 cm and reads as covered whether or not it is.
    "legs_apart": [
        (["thigh_l"], 'X', -14.0),
        (["thigh_r"], 'X', 14.0),
        (["calf_l"], 'X', 8.0),
        (["calf_r"], 'X', -8.0),
        (["ball_l"], 'X', -6.0),
        (["ball_r"], 'X', 6.0),
    ],
}

# ---- finger poses --------------------------------------------------------- #
# The original pose set never bent a finger, so the hand plates were only ever
# seen in the rest pose and their skinning looked fine.  The MetaHuman idle
# animation has relaxed and curled fingers, which is where a plate sharing
# weight between metacarpal and phalanges turns into a long shard.
FINGER_ROOTS = ("thumb", "index", "middle", "ring", "pinky")


def finger_bones(root, sd, segs=("_01", "_02", "_03")):
    return ["%s%s_%s" % (root, s, sd) for s in segs]


def finger_pose(mode, bone_names):
    """(bone-names, degrees) entries for a relaxed or closed hand.

    Angles are MCP / PIP / DIP.  The thumb opposes rather than curling straight
    in, so it gets a shallower curl and no spread.
    """
    kind = "fist" if mode == "fist" else "relaxed"
    out = []
    for sd in ("l", "r"):
        for root in FINGER_ROOTS:
            if root == "thumb":
                degs = {"relaxed": (22.0, 18.0, 14.0), "fist": (48.0, 34.0, 22.0)}
            else:
                degs = {"relaxed": (32.0, 42.0, 30.0), "fist": (52.0, 58.0, 38.0)}
            for seg, d in zip(("_01", "_02", "_03"), degs[kind]):
                nm = "%s%s_%s" % (root, seg, sd)
                if nm in bone_names:
                    out.append(([nm], d))
    return out


FINGER_POSES = ("relaxed_hand", "fist")


def apply_pose(arm, key):
    arm.data.pose_position = 'POSE'
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    for names, axis, deg in POSES.get(key, []):
        rotate_world(arm, names, axis, deg)
    if key == "ue_locomotion":
        # Logged straight out of Unreal's PIE frame: (pitch, yaw, roll) degrees
        # in parent-bone space, composed by UE as Rz(yaw)*Ry(pitch)*Rx(roll) -
        # i.e. Blender's XYZ euler with (x, y, z) = (roll, pitch, yaw).
        for nm, pitch, yaw, roll in UE_LOCOMOTION:
            pb = arm.pose.bones.get(nm)
            if pb is None:
                continue
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = Euler(
                (math.radians(roll), math.radians(pitch), math.radians(yaw)),
                'XYZ').to_quaternion()
    if key in FINGER_POSES:
        # built here, not at import: the bone list needs a live rig
        for names, deg in finger_pose(key, set(arm.data.bones.keys())):
            rotate_hinge(arm, names, deg)
    bpy.context.view_layer.update()


# --------------------------------------------------------------------------- #
# 3. penetration
# --------------------------------------------------------------------------- #
def inside_closed_shell(bvh, p, direction, limit=6.0):
    """Parity test: is p inside the closed armor shell?  Walks the ray, hopping
    over each hit so coincident faces do not cancel out."""
    count = 0
    org = p.copy()
    for _ in range(128):
        hit, _loc, _n, _idx = bvh.ray_cast(org, direction, limit)
        if hit is None:
            break
        count += 1
        step = (hit - org).length + 1e-4
        org = org + direction * step
    return (count % 2) == 1


def penetration(arm, body, armor_objs, mask, dg, side=None):
    """Signed coverage and interpenetration on the body.

    The defect this exists for is NOT a hole.  The thigh undersuit is complete
    and continuous; it simply sits *inside* the body there, so Unreal's depth
    test puts the MetaHuman skin in front of it.  An unsigned distance probe
    cannot see that: armour 1 cm outside the skin and armour 1 cm inside it are
    the same distance, and both scored clean.

    So the primary measure is **signed clearance along the outward body
    normal**:

        signed = (nearest armour point - body vertex) . outward normal

    positive means the armour is outside the skin (correct), zero means
    coplanar (z-fighting), negative means the armour is inside the skin and
    WILL render behind the body in Unreal.  The sign test needs no face
    orientation reasoning and no ray direction, which is why it is done with
    `find_nearest` rather than `ray_cast` - a forward ray returns a
    non-negative distance by construction, so it can never report "inside".

    Reported alongside, kept as secondary bounds:
    * `gap3cm` - first armour surface along the normal further than NEAR_LIMIT,
      or none.  Still a useful "is there armour near this vertex at all" signal
      but it cannot tell inside from outside, so it no longer gates.
    * `poke` - nearest armour within 5 mm AND behind the skin.

    `BVHTree.ray_cast` returns (location, normal, index, distance);
    `find_nearest` returns (location, normal, index, distance).  The first
    element is None when nothing was hit.
    """
    bvh = world_bvh(armor_objs)
    co, nr, _tris = deformed_body(body)
    exposed = 0
    near_gap = 0
    nearest_far = 0
    poked = 0
    tested = 0
    gaps = []
    near_gaps = []
    clearances = []
    signed_vals = []
    nearest_sgns = []
    min_signed = 1e9
    min_nearest_sgn = 1e9
    nonpos = 0
    miss = 0
    coplanar = 0
    # Per-side counters.  A single percentage hides a one-sided defect behind
    # the healthy side: 0.2% of the whole body is 0.4% of one leg, which is the
    # size of the defect this check exists to catch.  `side` is the body's
    # REST x sign, so a side never flips because the pose moved the limb across
    # the centreline.
    #   [tested, gap3cm, min_signed, nonpos_count, miss_count]
    ps = {}
    for i, keep in enumerate(mask):
        if not keep:
            continue
        tested += 1
        sd = side[i] if side else "C"
        e = ps.setdefault(sd, [0, 0, 1e9, 0, 0])
        e[0] += 1
        p, n = co[i], nr[i]
        # start slightly off the skin: rays launched exactly on a triangle miss
        # the BVH (precision), which reads as a false exposure
        hit, _loc, _nrm, dist = bvh.ray_cast(p + n * 0.0005, n, RAY_LEN)
        if hit is None:
            exposed += 1
            gaps.append((p.copy(), n.copy()))
            near_gap += 1
            e[1] += 1
            near_gaps.append((p.copy(), n.copy()))
        else:
            clearances.append(dist)
            if dist > NEAR_LIMIT:
                near_gap += 1
                e[1] += 1
                near_gaps.append((p.copy(), n.copy()))
        loc, _nor, _i2, ndist = bvh.find_nearest(p)
        if ndist > NEAR_LIMIT:
            nearest_far += 1
        # ---- SIGNED clearance: which side of the skin is the armour on? ----
        # Two signals, because they fail in opposite directions:
        #
        # `front` (GATED) is the forward ray.  Armour outside the skin is hit
        # along +n at a positive distance; armour inside the skin is *not*
        # reached, so a miss becomes negative.  This is also exactly the
        # question Unreal's depth test asks, and it has no concavity artifact.
        #
        # `nearest_sgn` (reported only) is the sign of the nearest armour point
        # relative to the skin tangent plane.  It is the textbook signed
        # distance, but at a concave region - armpit, inner thigh, crotch - the
        # nearest surface legitimately lies across the medial axis and reads
        # negative even when armour is plainly in front.  On this body that is
        # ~14% of vertices, so it cannot be the gate; it is kept to show the
        # two disagreeing, which is itself the diagnostic.
        sgn = dist if hit is not None else -ndist
        nearest_sgn = (loc - p).dot(n)
        signed_vals.append(sgn)
        nearest_sgns.append(nearest_sgn)
        min_signed = min(min_signed, sgn)
        min_nearest_sgn = min(min_nearest_sgn, nearest_sgn)
        e[2] = min(e[2], sgn)
        # Split the non-positive cases.  A MISS - nothing at all along the
        # outward normal - is the composer's defect: the body renders in front
        # of nothing.  A COPPLANAR hit (<=0.5 mm) still has armour in front of
        # the vertex, so it is a z-fighting risk, not a missing panel, and the
        # two need different thresholds and different fixes.
        if hit is None:
            miss += 1
            e[4] += 1
        elif dist <= SIGNED_MIN:
            coplanar += 1
        if sgn <= SIGNED_MIN:
            nonpos += 1
            e[3] += 1
        if ndist < 0.005 and nearest_sgn < -0.001:
            poked += 1
    bands = {}
    tot = {}
    for i, keep in enumerate(mask):
        if not keep:
            continue
        b = int(co[i].z * 10.0)
        tot[b] = tot.get(b, 0) + 1
    for p, _n in near_gaps:
        b = int(p.z * 10.0)
        bands[b] = bands.get(b, 0) + 1
    clearances.sort()
    med = clearances[len(clearances) // 2] if clearances else 0.0
    per_side = {k: {"tested": v[0],
                    "gap3cm_pct": 100.0 * v[1] / max(1, v[0]),
                    "min_signed_mm": v[2] * 1000.0,
                    "nonpos_pct": 100.0 * v[3] / max(1, v[0]),
                    "nonpos": v[3],
                    "miss_pct": 100.0 * v[4] / max(1, v[0]),
                    "miss": v[4]}
                for k, v in sorted(ps.items()) if k in ("L", "R")}
    delta = (abs(per_side["L"]["gap3cm_pct"] - per_side["R"]["gap3cm_pct"])
             if len(per_side) == 2 else 0.0)
    signed_vals.sort()
    return {"exposed_pct": 100.0 * exposed / max(1, tested),
            "near_pct": 100.0 * near_gap / max(1, tested),
            "nearest_far_pct": 100.0 * nearest_far / max(1, tested),
            # SIGNED clearance, metres: the primary measure.
            "min_signed": min_signed,
            "min_signed_mm": min_signed * 1000.0,
            "p01_signed_mm": (signed_vals[len(signed_vals) // 100] * 1000.0
                              if signed_vals else 0.0),
            "nonpos_pct": 100.0 * nonpos / max(1, tested),
            "nonpos": nonpos,
            "miss": miss,
            "miss_pct": 100.0 * miss / max(1, tested),
            "coplanar": coplanar,
            "coplanar_pct": 100.0 * coplanar / max(1, tested),
            "min_nearest_signed_mm": min_nearest_sgn * 1000.0,
            "poke_pct": 100.0 * poked / max(1, tested),
            "gaps": near_gaps, "tested": tested, "bands": bands, "tot": tot,
            "median": med,
            "per_side": per_side,
            # L/R are printed separately on purpose; a one-sided defect must
            # never be able to hide inside a combined average.
            "side_delta_pct": delta}


# --------------------------------------------------------------------------- #
# 4. rendering
# --------------------------------------------------------------------------- #
def setup_render():
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x = sc.render.resolution_y = 768
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.film_transparent = False
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.studio_light = 'Default'
    sh.color_type = 'MATERIAL'
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.show_shadows = False
    sh.show_specular_highlight = True
    sc.display.render_aa = '8'
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.type = 'ORTHO'
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sc.world = sc.world or bpy.data.worlds.new("W")
    sc.world.color = (0.055, 0.06, 0.07)
    return cam


def bbox_world(objs, zmin=None):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in objs:
        if ob.type != 'MESH' or ob.hide_render:
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        for v in me.vertices:
            p = mw @ v.co
            if zmin is not None and p.z < zmin:
                continue
            for i in range(3):
                lo[i] = min(lo[i], p[i])
                hi[i] = max(hi[i], p[i])
        ev.to_mesh_clear()
    return lo, hi


def front_sign(arm):
    """Which way the character faces, derived from the toe direction.

    The MetaHuman faces **-Y** in this space.  The first pass assumed +Y, which
    meant the preview cameras labelled "front" were filming the character's
    back and every front/back-asymmetric plate was mirrored.  Never hard-code
    this: derive it and assert both sides agree.
    """
    b = arm.data.bones
    ds = []
    for s in ("l", "r"):
        f = b.get("foot_%s" % s)
        bl = b.get("ball_%s" % s)
        if f is None or bl is None:
            continue
        d = bl.head_local - f.head_local
        if d.length > 1e-6:
            ds.append(1.0 if d.y > 0.0 else -1.0)
    if not ds:
        raise ValueError("no foot/ball bones - cannot derive facing")
    if len(set(ds)) != 1:
        raise ValueError("left and right toes disagree (%s) - rig is not "
                         "mirrored, front/back cameras would be ambiguous" % ds)
    return ds[0]


def make_views(F):
    """Camera directions, `F` = +1 if forward is +Y, -1 if forward is -Y."""
    return {
        "front": Vector((0.0, F, 0.06)),
        "back": Vector((0.0, -F, 0.06)),
        "side": Vector((1.0, 0.02 * F, 0.06)),
        "34top": Vector((0.62, 0.68 * F, 0.40)),
        # ~60 deg above horizontal: the third-person gameplay camera
        "gameplay": Vector((0.42, 0.47 * F, 0.87)),
        # Same idea, but a head crop cannot use the steep angle - pointed at a
        # helmet it looks down on the crown and hides the visor behind it.
        "gameplay_head": Vector((0.46, 0.62 * F, 0.30)),
    }


def world_points(objs, zmin=None):
    """Every evaluated world-space vertex of `objs` (one flat list)."""
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for ob in objs:
        if ob.type != 'MESH' or ob.hide_render:
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        for v in me.vertices:
            p = mw @ v.co
            if zmin is None or p.z >= zmin:
                pts.append(p)
        ev.to_mesh_clear()
    return pts


def render_views(cam, objs, tag, outdir, views=("front", "side", "back", "34top",
                                                "gameplay"),
                 pad=1.12, zmin=None, vmap=None):
    lo, hi = bbox_world(objs, zmin)
    if lo.x > hi.x:
        return []
    ctr = (lo + hi) * 0.5
    span = (hi - lo).length
    os.makedirs(outdir, exist_ok=True)
    # Framing is measured on the real vertices, not on the eight corners of the
    # world AABB: on a steep view the box corners project far outside the figure
    # and leave it marooned in the middle of the frame.
    pts = world_points(objs, zmin) or [ctr]
    written = []
    for name in views:
        d = vmap[name].normalized()
        cam.location = ctr + d * span * 2.0
        cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
        # matrix_world is cached until the depsgraph is evaluated, so without
        # this the first view of every batch is framed with the *previous*
        # camera's axes (cropped, or blown up on an unrelated axis).
        bpy.context.view_layer.update()
        rot = cam.matrix_world.to_3x3()
        right, up = rot.col[0], rot.col[1]
        rs = [p.dot(right) for p in pts]
        us = [p.dot(up) for p in pts]
        w, h = max(rs) - min(rs), max(us) - min(us)
        cam.data.ortho_scale = max(w, h) * pad
        p = os.path.join(outdir, "%s_%s.png" % (tag, name))
        bpy.context.scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        written.append(p)
    return written


# --------------------------------------------------------------------------- #
def build_posed_scene():
    """reference armature + body + every armor slot, all retargeted to one rig"""
    C.fresh_scene()
    bpy.ops.import_scene.fbx(filepath=C.REF_BODY)
    arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    arm.name = "root"
    body = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
    body.name = "SKM_Body"
    for ob in list(bpy.context.scene.objects):
        if ob.type == 'ARMATURE':
            continue
    armor = []
    for fn in ARMOR_FILES:
        path = os.path.join(C.EXPORT_DIR, fn)
        if not os.path.exists(path):
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        meshes = [o for o in new if o.type == 'MESH']
        duparm = [o for o in new if o.type == 'ARMATURE']
        for m in meshes:
            mw = m.matrix_world.copy()
            m.parent = arm
            m.matrix_parent_inverse = arm.matrix_world.inverted()
            m.matrix_basis = mw
            for mod in list(m.modifiers):
                if mod.type == 'ARMATURE':
                    mod.object = arm
            armor.append(m)
        for a in duparm:
            bpy.data.objects.remove(a, do_unlink=True)
    return arm, body, armor


# --------------------------------------------------------------------------- #
# 3b. bare-skin acceptance check (what Unreal's camera actually sees)
# --------------------------------------------------------------------------- #
def bare_skin_check(arm, body, armor, poses, outdir, pivot=(0.0, 0.0, 0.95)):
    """Is any body silhouette pixel left uncovered by armour, per camera?

    The vertex probe above asks "is there armour just outside this body vertex".
    That is the right question for geometry, but the acceptance criterion is a
    *picture*: no visible skin in the top-down gameplay camera at 1280x960 with
    the spring arm between 2.3 m and 4.3 m.  So this renders three passes from
    one camera - body only, armour only, both - and marks every pixel where the
    body silhouette has no armour behind it.  It needs no normals, cannot be
    fooled by which way a surface faces, and produces a mask image that shows
    *where* rather than just how much.
    """
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x, sc.render.resolution_y = UE_RES
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.film_transparent = True        # alpha carries the silhouette
    sh = sc.display.shading
    sh.light, sh.color_type = 'STUDIO', 'MATERIAL'
    sh.show_cavity, sh.cavity_type = True, 'BOTH'
    sh.show_shadows = False
    sc.display.render_aa = '8'

    cd = bpy.data.cameras.new("UECam")
    cd.type = 'PERSP'
    cd.lens = 50.0
    cam = bpy.data.objects.new("UECam", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    os.makedirs(outdir, exist_ok=True)

    def shoot(path, elev, azim, arm_len):
        e, a = math.radians(elev), math.radians(azim)
        d = Vector((math.cos(e) * math.sin(a),
                    -math.cos(e) * math.cos(a), math.sin(e)))
        cam.location = Vector(pivot) + d * arm_len
        cam.rotation_euler = (Vector(pivot) - cam.location).to_track_quat(
            '-Z', 'Y').to_euler()
        bpy.context.view_layer.update()
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)

    def alphas(path):
        img = bpy.data.images.load(path)
        px = list(img.pixels)
        w, h = img.size
        bpy.data.images.remove(img)
        return [px[i * 4 + 3] for i in range(w * h)], w, h

    rows = []
    worst = 0.0
    for pose in poses:
        apply_pose(arm, pose)
        for tag, elev, azim in UE_VIEWS:
            for arm_len in UE_ARMS:
                pb = os.path.join(outdir, "%s_%s_%dm_body.png"
                                  % (pose, tag, int(arm_len * 10)))
                pa = os.path.join(outdir, "%s_%s_%dm_armor.png"
                                  % (pose, tag, int(arm_len * 10)))
                for m in armor:
                    m.hide_render = True
                shoot(pb, elev, azim, arm_len)
                for m in armor:
                    m.hide_render = False
                body.hide_render = True
                shoot(pa, elev, azim, arm_len)
                body.hide_render = False
                ab, w, h = alphas(pb)
                aa, _w, _h = alphas(pa)
                nb = bare = 0
                mask = [0.0] * (w * h * 4)
                for i in range(w * h):
                    if ab[i] > 0.5:
                        nb += 1
                        if aa[i] <= 0.5:
                            bare += 1
                            j = i * 4
                            mask[j], mask[j + 1] = 1.0, 0.0
                            mask[j + 2], mask[j + 3] = 0.0, 1.0
                pct = 100.0 * bare / max(1, nb)
                worst = max(worst, pct)
                out = bpy.data.images.new("bare", w, h, alpha=True)
                out.pixels = mask
                out.filepath_raw = os.path.join(
                    outdir, "%s_%s_%dm_BARE.png" % (pose, tag, int(arm_len * 10)))
                out.file_format = 'PNG'
                out.save()
                bpy.data.images.remove(out)
                rows.append({"pose": pose, "view": tag, "arm_m": arm_len,
                             "body_px": nb, "bare_px": bare, "bare_pct": pct})
                print("    %-13s %-6s arm %.1fm  body=%7d  bare=%6d  %6.3f%%"
                      % (pose, tag, arm_len, nb, bare, pct))
    bpy.data.objects.remove(cam, do_unlink=True)
    return rows, worst


def radial_containment(head_pts, hel_pts, axis_y=0.006, zmin=HELMET_HEAD_Z):
    """Fraction of head points lying outside the shell's radial envelope.

    The 6 cm-along-the-normal probe used for the body measures "is there armour
    just outside this vertex".  On the head that under-reports badly: the ear is
    a folded shell whose vertex normals point sideways or downward, so the ray
    leaves the ear instead of crossing the helmet, even though the helmet
    cleanly encloses it.  This measures what the brief actually asks for - does
    the shell enclose the head - by comparing each head point's radius against
    the shell's radius in the same 1 cm height slab.
    """
    env = {}
    for p in hel_pts:
        b = int(p.z * 100.0)
        r = math.hypot(p.x, p.y - axis_y)
        for k in (b - 1, b, b + 1):
            if r > env.get(k, 0.0):
                env[k] = r
    out = tot = 0
    for p in head_pts:
        if p.z < zmin:
            continue
        tot += 1
        if math.hypot(p.x, p.y - axis_y) > env.get(int(p.z * 100.0), 0.0):
            out += 1
    return 100.0 * out / max(1, tot), out, tot, env


def head_only_copy(ob, zmin=1.50):
    """A copy of `ob` with everything below `zmin` deleted.

    SKM_MHC_Hero_FaceMesh.fbx also carries a shoulder / upper-chest stub.  It is
    not part of the helmet and, in a preview, it reads as a wide flared skirt
    under the shell that makes the silhouette impossible to judge.
    """
    me = ob.data.copy()
    tmp = bpy.data.objects.new(ob.name + "_HeadOnly", me)
    bpy.context.scene.collection.objects.link(tmp)
    tmp.matrix_world = ob.matrix_world.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    kill = [v for v in bm.verts if (tmp.matrix_world @ v.co).z < zmin]
    if kill:
        bmesh.ops.delete(bm, geom=kill, context='VERTS')
    bm.to_mesh(me)
    bm.free()
    me.update()
    return tmp


def main():
    check_scale()
    check_exports()

    arm, body, armor = build_posed_scene()
    if not armor:
        print("no armor FBX found - run armor_set_a.py first")
        return
    print("\nloaded %d armor meshes" % len(armor))
    lo, hi = bbox_world(armor + [body])
    print("  combined world bbox z[%.2f,%.2f] x[%.2f,%.2f] y[%.2f,%.2f]"
          % (lo.z, hi.z, lo.x, hi.x, lo.y, hi.y))
    for m in armor:
        a, b = bbox_world([m])
        print("    %-26s z[%.2f,%.2f] x[%.2f,%.2f] y[%.2f,%.2f]"
              % (m.name, a.z, b.z, a.x, b.x, a.y, b.y))
    for nm in ("upperarm_fwd_l", "upperarm_l", "lowerarm_l", "hand_l", "thigh_l",
               "calf_l", "foot_l", "spine_03"):
        print("  chain %-18s %s" % (nm, " <- ".join(bone_chain(arm, nm))))

    mask = [True] * len(body.data.vertices)
    apply_pose(arm, "rest")
    dg = bpy.context.evaluated_depsgraph_get()
    me = body.evaluated_get(dg).to_mesh()
    mw = body.matrix_world
    for i, v in enumerate(me.vertices):
        if (mw @ v.co).z > NECK_CUT_Z:
            mask[i] = False
    body.evaluated_get(dg).to_mesh_clear()

    cam = setup_render()
    os.makedirs(C.PREVIEW_DIR, exist_ok=True)
    F = front_sign(arm)
    print("\n=== facing ===")
    print("  character faces %s (derived from toe direction, front sign %+d)"
          % ("+Y" if F > 0 else "-Y", int(F)))
    # Side is taken from the body's REST x so a limb that crosses the centreline
    # in a pose keeps its own label.  |x| < SIDE_CM is the midline (crotch,
    # spine) and is reported as neither.
    rest_x = [v.co.x * 100.0 for v in body.data.vertices]
    side = ["L" if x > SIDE_CM else ("R" if x < -SIDE_CM else "C")
            for x in rest_x]
    print("  body verts by side: L=%d R=%d midline=%d"
          % (side.count("L"), side.count("R"), side.count("C")))
    vmap = make_views(F)
    print("\n=== 2/3. poses ===")
    print("%-14s %9s %8s %8s %8s   %s"
          % ("pose", "sign_min", "miss%", "gap3cm", "poke%",
             "per side: worst signed mm / miss% / coplanar%"))
    worst_pose = None
    worst_side = None
    worst_signed = None
    worst_nonpos = (None, 0, None, 0)
    worst_miss = (None, 0.0, None)
    ref_pose = None
    for key in list(POSES.keys()) + ["ue_locomotion"] + list(FINGER_POSES):
        apply_pose(arm, key)
        bpy.context.view_layer.update()
        # A pose that silently fails to apply reports coverage identical to the
        # rest pose, which reads as a pass.  POSES entries must be a *list* of
        # bone names; a bare string iterates its characters and matches nothing.
        _c, _n, _t = deformed_body(body)
        if ref_pose is None:
            ref_pose = [p.copy() for p in _c]
        moved = max((_c[i] - ref_pose[i]).length for i in range(len(_c)))
        r = penetration(arm, body, armor, mask,
                        bpy.context.evaluated_depsgraph_get(), side=side)
        ps = r["per_side"]
        print("%-14s %8.2fmm %7.2f%% %7.2f%% %7.2f%%   %s"
              % (key, r["min_signed_mm"], r["miss_pct"], r["near_pct"],
                 r["poke_pct"],
                 "  ".join("%s %+7.2fmm %5.2f%% %5.2f%%"
                           % (k, ps[k]["min_signed_mm"], ps[k]["miss_pct"],
                              ps[k]["nonpos_pct"] - ps[k]["miss_pct"])
                           for k in ("L", "R") if k in ps)))
        print("        max mesh displacement vs rest: %.1f cm%s"
              % (moved * 100.0,
                 "   !! POSE DID NOT APPLY" if (moved < 0.005 and key != "rest") else ""))
        worst = sorted(r["bands"].items(), key=lambda kv: -kv[1])[:6]
        if worst:
            print("        worst height bands (m): %s"
                  % ", ".join("%.1f-%.1fm %d/%d" % (b / 10.0, b / 10.0 + 0.1, n,
                                                    r["tot"].get(b, 1))
                              for b, n in worst))
        report["poses"].append({"pose": key, "exposed_pct": r["exposed_pct"],
                                "gap3cm_pct": r["near_pct"],
                                "signed_min_mm": r["min_signed_mm"],
                                "signed_p01_mm": r["p01_signed_mm"],
                                "signed_nonpos_pct": r["nonpos_pct"],
                                "signed_nonpos": r["nonpos"],
                                "miss_pct": r["miss_pct"],
                                "miss": r["miss"],
                                "coplanar_pct": r["coplanar_pct"],
                                "min_nearest_signed_mm": r["min_nearest_signed_mm"],
                                "nearest_far_pct": r["nearest_far_pct"],
                                "poke_pct": r["poke_pct"],
                                "median_clearance_mm": r["median"] * 1000.0,
                                "tested": r["tested"],
                                "per_side": ps,
                                "side_delta_pct": r["side_delta_pct"],
                                "bands": {str(k): [v, r["tot"].get(k, 0)]
                                          for k, v in r["bands"].items()}})
        if worst_pose is None or r["near_pct"] > worst_pose[1]:
            worst_pose = (key, r["near_pct"])
        # The SIGNED gate is the primary one: armour sitting inside the skin
        # renders behind the body in Unreal no matter how complete it is.
        if worst_signed is None or r["min_signed_mm"] < worst_signed[1]:
            worst_signed = (key, r["min_signed_mm"])
        for sd in ("L", "R"):
            if sd in ps and ps[sd]["nonpos"] > worst_nonpos[1]:
                worst_nonpos = (key, ps[sd]["nonpos"], sd, ps[sd]["tested"])
            if sd in ps and ps[sd]["miss_pct"] > worst_miss[1]:
                worst_miss = (key, ps[sd]["miss_pct"], sd)
        # The side gate is separate and stricter in intent: one side may be
        # twice as bad as the whole-body average and still pass the average.
        if len(ps) == 2:
            w = max(ps.items(), key=lambda kv: kv[1]["gap3cm_pct"])
            if worst_side is None or w[1]["gap3cm_pct"] > worst_side[1]:
                worst_side = (key, w[1]["gap3cm_pct"], w[0])
        for ob in armor:
            ob.hide_render = False
        render_views(cam, armor, key, C.PREVIEW_DIR, vmap=vmap)

    report["facing"] = {"front_sign": int(F),
                        "forward_axis": "+Y" if F > 0 else "-Y"}

    # ---- acceptance: no visible skin from the gameplay camera -------------- #
    print("\n=== 3b. bare-skin acceptance (UE camera, %dx%d, arm %.1f-%.1f m) ==="
          % (UE_RES[0], UE_RES[1], UE_ARMS[0], UE_ARMS[-1]))
    rows, worst_bare = bare_skin_check(
        arm, body, armor, ("rest", "walk_stride", "legs_apart"),
        os.path.join(C.PREVIEW_DIR, "uecam"))
    report["bare_skin"] = {"rows": rows, "worst_pct": worst_bare,
                           "target_pct": BARE_TARGET,
                           "resolution": list(UE_RES), "arm_m": list(UE_ARMS),
                           "views": [v[0] for v in UE_VIEWS]}
    if worst_bare > BARE_TARGET:
        print("\n  !! BARE SKIN: %.3f%% of the body silhouette is visible with "
              "no armour behind it (target < %.2f%%)"
              % (worst_bare, BARE_TARGET))
        raise SystemExit("bare-skin check failed (worst %.3f%%)" % worst_bare)
    print("  worst %.3f%% - no visible skin" % worst_bare)

    # ---- SIGNED CLEARANCE is the primary gate ------------------------------ #
    # Armour sitting inside the skin renders *behind* the body in Unreal
    # however complete it is, so this is checked first and hardest.  The
    # distance-based gates below are kept as secondary bounds.
    if worst_signed and worst_signed[1] < SIGNED_MIN * 1000.0:
        print("\n  !! SIGNED CLEARANCE: pose '%s' puts armour %.2f mm INSIDE the "
              "skin at its worst vertex. Unreal renders the body in front "
              "wherever this is negative."
              % (worst_signed[0], worst_signed[1]))
        raise SystemExit("signed clearance failed (worst pose %s: %.2f mm)"
                         % (worst_signed[0], worst_signed[1]))
    if worst_miss[1] > MISS_TARGET:
        print("\n  !! SIGNED CLEARANCE: pose '%s' leaves %.2f%% of the %s side "
              "with NO armour along the outward normal (target < %.2f%%). "
              "Unreal renders the body in front of these."
              % (worst_miss[0], worst_miss[1], worst_miss[2], MISS_TARGET))
        raise SystemExit("signed clearance failed (worst %s side %s: %.2f%%)"
                         % (worst_miss[0], worst_miss[2], worst_miss[1]))

    if worst_pose and worst_pose[1] > COVERAGE_TARGET:
        print("\n  !! COVERAGE: pose '%s' leaves %.2f%% of body verts with no "
              "armour within %.0f cm along the normal (target < %.1f%%)"
              % (worst_pose[0], worst_pose[1], NEAR_LIMIT * 100.0,
                 COVERAGE_TARGET))
        raise SystemExit("coverage check failed (worst pose %s: %.2f%%)"
                         % (worst_pose[0], worst_pose[1]))
    if worst_side and worst_side[1] > SIDE_TARGET:
        print("\n  !! ASYMMETRY: pose '%s' leaves %.2f%% of the %s side with no "
              "armour within %.0f cm (target < %.1f%% per side)"
              % (worst_side[0], worst_side[1], worst_side[2],
                 NEAR_LIMIT * 100.0, SIDE_TARGET))
        raise SystemExit("per-side coverage failed (worst %s side %s: %.2f%%)"
                         % (worst_side[0], worst_side[2], worst_side[1]))

    # ---- helmet on/off against the MetaHuman face mesh ---------------------- #
    print("\n=== 4. helmet ===")
    for ob in list(bpy.context.scene.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    C.fresh_scene()
    bpy.ops.import_scene.fbx(filepath=C.REF_FACE)
    arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    faces = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    assert len(faces) == 1, "expected one face mesh, got %d" % len(faces)
    faces[0].name = faces[0].data.name = "Face"
    head_mw = arm.matrix_world @ arm.data.bones["head"].matrix_local
    print("  head bone rest origin (world m): (%.4f, %.4f, %.4f)"
          % tuple(head_mw.translation))
    hel = []
    path = os.path.join(C.EXPORT_DIR, HELMET_STATIC)
    if os.path.exists(path):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=path)
        hel = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
        print("  helmet static tris: %d" % sum(C.tri_count(o.data) for o in hel))
        hlo, hhi = bbox_world(hel)
        flo, fhi = bbox_world(faces, zmin=1.40)
        print("  helmet world bbox x[%.3f,%.3f] y[%.3f,%.3f] z[%.3f,%.3f]"
              % (hlo.x, hhi.x, hlo.y, hhi.y, hlo.z, hhi.z))
        print("  head   world bbox x[%.3f,%.3f] y[%.3f,%.3f] z[%.3f,%.3f]"
              % (flo.x, fhi.x, flo.y, fhi.y, flo.z, fhi.z))
    cam = setup_render()
    os.makedirs(C.PREVIEW_DIR, exist_ok=True)
    head = head_only_copy(faces[0])
    faces[0].hide_render = True            # keep the stub out of every preview
    # Reuse the facing already derived from the *body* rig.  `arm` has been
    # re-imported as the helmet armature by now, so it has no foot/ball bones to
    # re-derive from - calling front_sign() on it raised "no foot/ball bones".
    hF = F
    hv = make_views(hF)
    render_views(cam, [head] + hel, "helmet_on", C.PREVIEW_DIR,
                 views=("front", "back", "side", "34top", "gameplay_head"),
                 zmin=HELMET_HEAD_Z, vmap=hv, pad=1.9)
    # Workbench renders the whole view layer, so the helmet has to be hidden -
    # simply not passing it to render_views would not remove it from the frame.
    for h in hel:
        h.hide_render = True
    render_views(cam, [head], "helmet_off", C.PREVIEW_DIR,
                 views=("front", "back", "34top", "gameplay_head"),
                 zmin=HELMET_HEAD_Z, vmap=hv, pad=1.9)
    for h in hel:
        h.hide_render = False
    # Coverage of the head by the helmet shell.  The face FBX also carries a
    # shoulder/neck stub, which no helmet is meant to enclose, so the metric is
    # taken over the head band only.
    if hel:
        dg = bpy.context.evaluated_depsgraph_get()
        # measured against the head-only copy: the full face mesh is hidden for
        # the renders, and world_points/deformed_body skip hidden objects
        me = head.evaluated_get(dg).to_mesh()
        mw = head.matrix_world
        mask = [(mw @ v.co).z > HELMET_HEAD_Z for v in me.vertices]
        head.evaluated_get(dg).to_mesh_clear()
        hres = penetration(arm, head, hel, mask, dg)
        nface = sum(mask)
        print("  head-band verts with no helmet within %.0f cm along the normal: "
              "%.2f%% of %d (band z > %.2f m)"
              % (RAY_LEN * 100.0, hres["exposed_pct"], nface, HELMET_HEAD_Z))
        worst = sorted(hres["bands"].items(), key=lambda kv: -kv[1])[:5]
        if worst:
            print("        uncovered by height: %s"
                  % ", ".join("%.1f-%.1fm %d/%d" % (b / 10.0, b / 10.0 + 0.1, n,
                                                    hres["tot"].get(b, 1))
                              for b, n in worst))
        pct_c, n_out, n_tot, env = radial_containment(
            world_points([head], HELMET_HEAD_Z), world_points(hel))
        print("  head points outside the shell's radial envelope: %.2f%% of %d"
              % (pct_c, n_tot))
        report["helmet"].append({"tris": sum(C.tri_count(o.data) for o in hel),
                                 "normal_probe_exposed_pct": hres["exposed_pct"],
                                 "normal_probe_verts": nface,
                                 "containment_exposed_pct": pct_c,
                                 "containment_verts": n_tot,
                                 "head_band_z": HELMET_HEAD_Z,
                                 "shell_max_radius_by_cm": {
                                     str(k): round(v, 4) for k, v in sorted(env.items())},
                                 "bands": {str(k): [v, hres["tot"].get(k, 0)]
                                           for k, v in hres["bands"].items()}})

    with open(os.path.join(C.EXPORT_DIR, "verify_report.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    print("\nwrote", os.path.join(C.EXPORT_DIR, "verify_report.json"))
    print("DONE")


if __name__ == "__main__":
    main()