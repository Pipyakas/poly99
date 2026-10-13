# -*- coding: utf-8 -*-
"""
poly99+ - build the full-body hard-surface armor set (variant A) and export one
FBX per equipment slot, skinned to the MetaHuman ``root`` armature.

Run headless:
    blender -b --factory-startup --python armor/scripts/armor_set_a.py

Design
------
* ``M_Undersuit``: a copy of the *entire* body skin pushed 0.4-0.9 cm out along
  the vertex normals, split by slot.  This guarantees continuous neck-down
  coverage and deforms exactly like the skin (weights are transferred from the
  body).
* Plates: body-face regions relaxed -> planar-decimated -> shrink-wrapped back
  onto the skin at a 1.0 cm stand-off -> solidified outwards to their final
  thickness, bevelled and flat shaded.  The 1.0 cm stand-off keeps every plate
  clear of the undersuit; planar decimation gives the faceted angular read.
* Trim: the boundary ring of a plate, lifted just proud of its outer surface,
  gets ``M_ArmorEmissive`` - the thin cyan light channels.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import armor_common as C  # noqa: E402

SKIN_STANDOFF = 1.0          # cm: plate inner surface distance from the skin
TRIM_CLEAR = 0.10            # cm: trim ribbon float above the plate face
TRIM_W = 0.42                # cm: trim ribbon width (a hairline light channel)
BUDGET_TRIS = 70000
SLOT_BUDGET = {"hands": 6000, "feet": 4000}

# Bones a glove or boot is allowed to be weighted to.  Anything outside these
# sets is dropped before the collapse, so a hand plate can never end up half
# driven by `hand_l` and half by `index_02_l`.
FINGER_ROOTS = ("thumb", "index", "middle", "ring", "pinky")
TOE_ROOTS = ("bigtoe", "indextoe", "middletoe", "ringtoe", "littletoe")


def _bone_filter(roots, extras):
    out = set(extras)
    for s in ("l", "r"):
        out.add("hand_%s" % s)
        out.add("wrist_%s" % s)
        out.add("foot_%s" % s)
        out.add("ankle_%s" % s)
        out.add("ball_%s" % s)
        for r in roots:
            out.add("%s_metacarpal_%s" % (r, s))
            for seg in ("_01", "_02", "_03"):
                out.add("%s%s_%s" % (r, seg, s))
    return out


HAND_BONES = _bone_filter(FINGER_ROOTS, ("hand_l", "hand_r"))
FOOT_BONES = _bone_filter(TOE_ROOTS, ("ball_l", "ball_r", "foot_l", "foot_r"))


# --------------------------------------------------------------------------- #
# slot assignment
# --------------------------------------------------------------------------- #
def assign_slots(body):
    slot = [None] * len(body.faces)
    for fi in range(len(body.faces)):
        nm = body.face_group(fi)
        c = body.fcenter[fi]
        if body.is_toe_group(nm) or nm.startswith(("foot_", "ball_", "ankle_")):
            s = "feet"
        elif nm.startswith(("thumb_", "index_", "middle_", "ring_", "pinky_", "hand_")):
            s = "hands"
        elif nm.startswith(("thigh", "calf")):
            s = "legs"
        elif nm.startswith(("upperarm", "lowerarm", "wrist_")):
            s = "arms"
        elif nm == "pelvis":
            # The inner thigh and groin are owned by the PELVIS bone, not the
            # thigh, so the bone-name test above filed them under "chest" and
            # the leg undersuit stopped at the top of the thigh (~z 92 cm).  With
            # the legs split - which is what the Unreal locomotion pose does -
            # the inner thigh then showed bare body skin, because the thigh
            # shell was not there to cover it.  These faces belong to the legs.
            # The buttocks are the posterior part of the same pelvis zone and do
            # NOT, so the split is on y relative to the hip: forward of
            # hip.y + 3 cm is groin/inner thigh, behind it is seat.
            hz, hy = body.J["l"]["hip"].z, body.J["l"]["hip"].y
            s = ("legs" if (hz - 25.0 < c.z < hz + 6.0 and abs(c.x) < 12.0
                           and c.y <= hy + 3.0) else "chest")
        else:
            s = "chest"
        if s in ("arms", "chest") and c.z > 129.0:
            for sd in ("l", "r"):
                if (c - body.J[sd]["shoulder"]).length < 12.0:
                    s = "shoulders"
                    break
        slot[fi] = s
    return slot


# --------------------------------------------------------------------------- #
# plate factory
# --------------------------------------------------------------------------- #
class Set(object):
    def __init__(self, body, slot, mats):
        self.body = body
        self.slot = slot
        self.mats = mats
        self.parts = {}
        self.tris = 0

    def _register(self, slot, obj, rigid, kind):
        self.parts.setdefault(slot, []).append((obj, rigid, kind))
        lo = [1e9] * 3
        hi = [-1e9] * 3
        for v in obj.data.vertices:
            for i in range(3):
                lo[i] = min(lo[i], v.co[i])
                hi[i] = max(hi[i], v.co[i])
        print("  [%-9s] %-26s %-6s %6d tris  x[%6.1f,%6.1f] y[%6.1f,%6.1f] z[%6.1f,%6.1f]"
              % (slot, obj.name, kind, C.tri_count(obj.data),
                 lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
        return obj

    # -- primitives -------------------------------------------------------- #
    def finish(self, obj, slot, mat, outer, relax, facet, bevel=0.30,
               rigid=False, trim=False, stand=SKIN_STANDOFF, collapse=0.0,
               trim_width=TRIM_W, tri_cap=0, hard=False, only=None):
        """relax -> planar decimate -> [triangle cap] -> project onto the skin
        at `stand` -> [trim ribbon] -> solidify outwards -> bevel -> shade."""
        obj.matrix_world = self.body.obj.matrix_world.copy()
        if relax:
            C.smooth_relax(obj, iterations=relax, factor=0.55)
        if collapse:
            C.collapse_decimate(obj, collapse)
        if facet:
            C.planar_decimate(obj, facet)
        # The cap is applied to the still-open sheet, before solidify/bevel, so
        # the decimator only ever sees clean surface topology.
        for _ in range(8):
            if not tri_cap or C.tri_count(obj.data) <= tri_cap:
                break
            C.collapse_decimate(obj, 0.78)
        C.project_to_body(obj, self.body.bvh, stand)
        thick = max(0.0, outer - stand)
        if trim and thick > 0.05:
            t = C.trim_ribbon(obj, width=trim_width, lift=thick + TRIM_CLEAR)
            if t is not None:
                C.assign_material(t, self.mats["M_ArmorEmissive"])
                C.shade_flat(t)
                C.transfer_weights(t, self.body.obj, hard=True, only=only)
                C.parent_to_armature([t], self.body.arm, like=self.body.obj)
                self._register(slot, t, True, "trim")
        if thick > 0.05:
            C.activate(obj)
            m = obj.modifiers.new("solid", 'SOLIDIFY')
            m.thickness = thick
            m.offset = 1.0
            m.use_rim = True
            bpy.ops.object.modifier_apply(modifier=m.name)
            if bevel:
                C.bevel(obj, width=bevel, segments=1, angle=34.0)
            C.shade_flat(obj)
        C.assign_material(obj, self.mats[mat])
        C.transfer_weights(obj, self.body.obj, rigid=rigid, hard=hard, only=only)
        C.parent_to_armature([obj], self.body.arm, like=self.body.obj)
        return self._register(slot, obj, rigid, "plate")

    def undersuit(self, slot, keep, name, standoff=0.85, mat="M_Undersuit",
                  relax=0, collapse=0.0, tri_cap=0, only=None, floor=0.6):
        # `floor` is the minimum standoff in CENTIMETRES (0.6 cm = 6 mm): the
        # undersuit is the coverage guarantee, and it has to sit unambiguously
        # OUTSIDE the skin or Unreal renders the body in front of it.  Without a
        # floor the clamp shrinks the push to under a millimetre wherever the
        # body mesh is finely tessellated - the inner thigh above all.
        obj = C.extract_faces(self.body, keep, name, offset=standoff,
                              offset_clamp=1.25, offset_floor=floor)
        obj.matrix_world = self.body.obj.matrix_world.copy()
        if relax:
            C.smooth_relax(obj, iterations=relax, factor=0.55)
        if collapse:
            C.collapse_decimate(obj, collapse)
        for _ in range(8):
            if not tri_cap or C.tri_count(obj.data) <= tri_cap:
                break
            C.collapse_decimate(obj, 0.78)
        for p in obj.data.polygons:
            p.use_smooth = True
        C.assign_material(obj, self.mats[mat])
        C.transfer_weights(obj, self.body.obj, rigid=False, only=only)
        C.parent_to_armature([obj], self.body.arm, like=self.body.obj)
        return self._register(slot, obj, False, "suit")

    def plate(self, slot, keep, name, mat="M_ArmorPrimary", outer=2.4,
              relax=10, facet=9.0, bevel=0.30, rigid=False, trim=False,
              stand=SKIN_STANDOFF, collapse=0.0, trim_width=TRIM_W, tri_cap=0,
              hard=False, only=None):
        obj = C.extract_faces(self.body, keep, name, offset=0.0)
        return self.finish(obj, slot, mat, outer, relax, facet, bevel, rigid,
                           trim, stand, collapse, trim_width, tri_cap, hard, only)


# --------------------------------------------------------------------------- #
# region predicates
# --------------------------------------------------------------------------- #
def make_predicates(body, slot):
    J = body.J

    def in_slot(s):
        return lambda fi: slot[fi] == s

    def limb(a, b, t0, t1, rad, zmin=None, zmax=None, excl=None):
        def p(fi):
            c = body.fcenter[fi]
            if zmin is not None and c.z < zmin:
                return False
            if zmax is not None and c.z > zmax:
                return False
            t, tc, d = C.seg_t_dist(c, a, b)
            if not (t0 <= t <= t1) or d > rad:
                return False
            return not (excl and excl(fi, c))
        return p

    def near(pt, rad, zmin=None, zmax=None):
        def p(fi):
            c = body.fcenter[fi]
            if zmin is not None and c.z < zmin:
                return False
            if zmax is not None and c.z > zmax:
                return False
            return (c - pt).length < rad
        return p

    def band(z0, z1, xmax, ymin=None, ymax=None):
        def p(fi):
            c = body.fcenter[fi]
            if not (z0 <= c.z <= z1) or abs(c.x) > xmax:
                return False
            if ymin is not None and c.y < ymin:
                return False
            if ymax is not None and c.y > ymax:
                return False
            return True
        return p

    def both_sides(fn):
        return lambda fi: fn(fi, body.fcenter[fi])

    def shoulder_excl(fi, c):
        return min((c - J[sd]["shoulder"]).length for sd in ("l", "r")) < 8.5

    def elbow_excl(fi, c):
        return min((c - J[sd]["elbow"]).length for sd in ("l", "r")) < 6.0

    def knee_excl(fi, c):
        return min((c - J[sd]["knee"]).length for sd in ("l", "r")) < 6.5

    P = {
        "slot": in_slot,
        "collar": both_sides(lambda fi, c: slot[fi] == "chest" and c.z >= 138.5
                             and abs(c.x) <= 16.5),
        "cuirass": both_sides(lambda fi, c: slot[fi] == "chest"
                              and 112.5 <= c.z <= 139.0 and abs(c.x) <= 17.5),
        "sternum": both_sides(lambda fi, c: slot[fi] == "chest"
                              and 115.0 <= c.z <= 134.0 and abs(c.x) <= 9.5
                              and body.forward_y(c) >= 3.0),
        "backplate": both_sides(lambda fi, c: slot[fi] == "chest"
                                and 113.0 <= c.z <= 136.0 and abs(c.x) <= 14.5
                                and body.forward_y(c) <= -5.0),
        "abdomen": both_sides(lambda fi, c: slot[fi] == "chest"
                              and 95.0 <= c.z <= 114.0 and abs(c.x) <= 16.0),
        # two stacked fauld plates instead of one slab: the horizontal seam
        # between them is what makes the waist read as armour rather than a tube
        "fauld_lo": both_sides(lambda fi, c: slot[fi] == "chest"
                               and 95.0 <= c.z <= 103.5 and abs(c.x) <= 16.5),
        "fauld_hi": both_sides(lambda fi, c: slot[fi] == "chest"
                               and 104.0 <= c.z <= 113.0 and abs(c.x) <= 16.5),
        "belt": both_sides(lambda fi, c: slot[fi] == "chest"
                           and 100.0 <= c.z <= 106.0 and abs(c.x) <= 17.0),
        "pauldron": both_sides(lambda fi, c: slot[fi] == "shoulders"),
        "finger": lambda fi: slot[fi] == "hands" and body.face_group(fi).startswith(
            ("thumb_", "index_", "middle_", "ring_", "pinky_")),
        "palm": lambda fi: slot[fi] == "hands" and not body.face_group(fi).startswith(
            ("thumb_", "index_", "middle_", "ring_", "pinky_")),
    }
    for sd in ("l", "r"):
        j = J[sd]
        P["pauldron_" + sd] = near(j["shoulder"], 11.8, zmin=130.0)
        # the arm is plated shoulder-to-wrist with only the elbow as the break
        P["upperarm_" + sd] = limb(j["shoulder"], j["elbow"], 0.06, 0.84, 9.2,
                                   excl=shoulder_excl)
        P["elbow_" + sd] = near(j["elbow"], 7.2, zmax=133.0)
        P["forearm_" + sd] = limb(j["elbow"], j["wrist"], 0.22, 0.94, 7.2,
                                  excl=elbow_excl)
        P["tasset_" + sd] = limb(j["hip"], j["knee"], -0.30, 0.14, 20.0,
                                 zmin=82.0, zmax=103.0)
        P["thigh_" + sd] = limb(j["hip"], j["knee"], 0.10, 0.86, 11.6,
                                zmin=48.0)
        P["knee_" + sd] = near(j["knee"], 8.2, zmin=40.0, zmax=63.0)
        P["calf_" + sd] = limb(j["knee"], j["ankle"], 0.04, 0.93, 9.4,
                               zmin=9.0, zmax=50.0)
        P["ankle_" + sd] = near(j["ankle"], 7.4, zmax=17.0)
        P["toe_" + sd] = limb(j["ankle"], j["toe"], 0.42, 1.9, 10.0, zmax=9.0)
    # The boot upper is the heel / instep / mid-foot only.  Letting it cover the
    # whole foot slot would stack a second shell on top of the toe caps and
    # ankle cuffs (duplicate geometry, z-fighting, wasted triangles).
    P["boot_upper"] = lambda fi: (slot[fi] == "feet"
                                  and not any(P["toe_" + sd](fi) for sd in ("l", "r"))
                                  and not any(P["ankle_" + sd](fi) for sd in ("l", "r")))
    return P


def enforce_slot_budget(S, slotname, cap, rounds=60):
    """Collapse the heaviest plate in `slotname` until the slot fits `cap`.

    The per-part `tri_cap` values are estimates; this is what actually makes the
    hands/feet budget a guarantee rather than an aspiration.  Trim ribbons are
    never collapsed - they are generated from a plate's boundary and would
    detach from it.
    """
    parts = S.parts.get(slotname, [])
    total = lambda: sum(C.tri_count(o.data) for o, _, _ in parts)
    for _ in range(rounds):
        if total() <= cap:
            break
        cands = [o for o, _, k in parts if k != "trim" and C.tri_count(o.data) > 24]
        if not cands:
            break
        C.collapse_decimate(max(cands, key=lambda o: C.tri_count(o.data)), 0.86)
    return total()


# --------------------------------------------------------------------------- #
# backpack / thruster unit (built free of the body, rigid to spine_03)
# --------------------------------------------------------------------------- #
def box(bm, x0, x1, y0, y1, z0, z1):
    m = (Matrix.Translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
         @ Matrix.Diagonal(((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2, 1.0)))
    bmesh.ops.create_cube(bm, size=2.0, matrix=m)


def cyl(bm, center, radius, depth, rot=None, seg=12):
    m = Matrix.Translation(center)
    if rot is not None:
        m = m @ rot
    try:
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                              radius1=radius, radius2=radius, depth=depth, matrix=m)
    except TypeError:
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                              diameter1=radius, diameter2=radius, depth=depth, matrix=m)


def build_backpack(body, mats):
    """Thruster pack on the character's BACK.

    Built in the loft's own axes and then mirrored in y by ``F`` because the
    backpack is the one part with no body surface to fit itself to, so it is
    the easiest thing in the set to put on the wrong side.
    """
    F = body.front          # +1 forward = +Y, -1 forward = -Y
    prim = bmesh.new()
    box(prim, -9.0, 9.0, -21.8 * F, -14.4 * F, 112.0, 146.0)      # main body
    box(prim, -6.6, 6.6, -20.4 * F, -15.6 * F, 146.0, 150.5)      # top cap
    box(prim, -11.6, -9.0, -20.2 * F, -15.8 * F, 119.0, 140.0)    # side fins
    box(prim, 9.0, 11.6, -20.2 * F, -15.8 * F, 119.0, 140.0)
    box(prim, -7.4, 7.4, -14.6 * F, -13.4 * F, 114.0, 117.0)      # lower flange
    body_obj = C.new_object("Plate_Pack", prim)
    C.activate(body_obj)
    C.bevel(body_obj, width=0.9, segments=2, angle=30.0)
    C.shade_flat(body_obj)
    C.assign_material(body_obj, mats["M_ArmorPrimary"])

    acc = bmesh.new()
    for sx in (-5.2, 5.2):
        rot = Matrix.Rotation(math.radians(-22.0 * F), 4, 'X')
        cyl(acc, (sx, -17.6 * F, 110.0), 2.55, 7.0, rot, seg=12)
    acc_obj = C.new_object("Plate_Thrusters", acc)
    C.activate(acc_obj)
    C.bevel(acc_obj, width=0.35, segments=1, angle=30.0)
    C.shade_flat(acc_obj)
    C.assign_material(acc_obj, mats["M_ArmorSecondary"])

    emi = bmesh.new()
    for sx in (-5.2, 5.2):
        rot = Matrix.Rotation(math.radians(-22.0 * F), 4, 'X')
        cyl(emi, (sx, -18.25 * F, 106.9), 2.05, 0.45, rot, seg=12)
    for sx in (-1, 1):
        box(emi, sx * 9.05 - 0.25, sx * 9.05 + 0.25, -19.6 * F, -16.2 * F,
            120.0, 139.0)
    box(emi, -1.6, 1.6, -22.05 * F, -21.85 * F, 128.0, 142.0)
    emi_obj = C.new_object("Plate_PackTrim", emi)
    C.assign_material(emi_obj, mats["M_ArmorEmissive"])

    spine3 = "spine_03"
    for ob in (body_obj, acc_obj, emi_obj):
        vg = ob.vertex_groups.new(name=spine3)
        vg.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
        C.parent_to_armature([ob], body.arm, like=body.obj)
    return [body_obj, acc_obj, emi_obj]


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    arm, meshes = C.import_fbx(C.REF_BODY, ["BODY"])
    body = C.Body(arm, meshes[0])
    print("body: %d verts %d faces" % (len(body.verts), len(body.faces)))
    mats = C.make_materials()
    slot = assign_slots(body)
    counts = {}
    for s in slot:
        counts[s] = counts.get(s, 0) + 1
    print("slot face counts:", counts)
    assert sum(counts.values()) == len(body.faces)

    P = make_predicates(body, slot)
    S = Set(body, slot, mats)

    # ---------------- CHEST -------------------------------------------------
    S.undersuit("chest", lambda fi: slot[fi] == "chest", "Suit_Torso")
    S.plate("chest", P["collar"], "Plate_Collar", mat="M_ArmorSecondary",
            outer=2.1, relax=12, facet=7.0, rigid=False, trim=True)
    S.plate("chest", P["cuirass"], "Plate_Cuirass", mat="M_ArmorPrimary",
            outer=2.9, relax=14, facet=11.0, trim=True)
    S.plate("chest", P["sternum"], "Plate_Sternum", mat="M_ArmorSecondary",
            outer=3.7, relax=12, facet=13.0, rigid=True, trim=True)
    S.plate("chest", P["backplate"], "Plate_Back", mat="M_ArmorSecondary",
            outer=3.3, relax=12, facet=13.0, rigid=True, trim=True)
    S.plate("chest", P["belt"], "Plate_Belt", mat="M_ArmorSecondary",
            outer=2.9, relax=10, facet=7.0, rigid=True, trim=True)
    S.plate("chest", P["fauld_hi"], "Plate_Fauld_Upper", mat="M_ArmorPrimary",
            outer=2.5, relax=12, facet=9.0, trim=True)
    S.plate("chest", P["fauld_lo"], "Plate_Fauld_Lower", mat="M_ArmorPrimary",
            outer=2.2, relax=12, facet=9.0, trim=True)

    # ---------------- SHOULDERS --------------------------------------------
    S.undersuit("shoulders", lambda fi: slot[fi] == "shoulders", "Suit_Shoulders",
                standoff=0.9)
    for sd in ("l", "r"):
        S.plate("shoulders", P["pauldron_" + sd], "Plate_Pauldron_" + sd,
                mat="M_ArmorPrimary", outer=3.8, relax=13, facet=12.0,
                rigid=True, trim=True)

    # ---------------- ARMS ---------------------------------------------------
    S.undersuit("arms", lambda fi: slot[fi] == "arms", "Suit_Arms")
    for sd in ("l", "r"):
        S.plate("arms", P["upperarm_" + sd], "Plate_UpperArm_" + sd,
                outer=2.6, relax=10, facet=8.0, trim=True)
        S.plate("arms", P["elbow_" + sd], "Plate_Elbow_" + sd,
                mat="M_ArmorSecondary", outer=2.8, relax=10, facet=9.0,
                rigid=True, trim=True)
        S.plate("arms", P["forearm_" + sd], "Plate_Vambrace_" + sd,
                mat="M_ArmorSecondary", outer=2.6, relax=11, facet=9.0,
                rigid=True, trim=True)

    # ---------------- HANDS --------------------------------------------------
    # The suit is the coverage guarantee on the digits (same topology as the
    # skin, so it can never gap); the finger plates are the visible armour.
    # Both are heavily relaxed + collapsed - hands are seen at arm's length in
    # game, so they get a much smaller budget than the torso.
    #
    # Weighting is the part that matters here.  The body skin blends each
    # knuckle across metacarpal and phalanges; copying that onto a hard plate
    # makes the plate stretch into a long shard the instant the finger curls
    # (exactly what the idle animation does).  So:
    #   * plates are `hard` - one phalanx at weight 1.0
    #   * the glove keeps smoothing but is restricted to the bones it covers,
    #     so it can never inherit a wrist or forearm influence
    S.undersuit("hands", lambda fi: slot[fi] == "hands", "Suit_Hands",
                standoff=0.7, mat="M_Undersuit", collapse=0.45, tri_cap=1700,
                only=HAND_BONES)
    # Thicker than the rest of the set on purpose: a rigid plate per phalanx
    # rotates about its own bone, so when the finger curls the segments have to
    # overlap or the skin between them shows through.  Note that raising
    # `stand` does NOT help: a standoff pushes the plate away from the skin
    # without lengthening it along the bone, so the joint gap is unchanged -
    # 0.95 cm actually measured worse (1.24% vs 0.98%) because the thicker
    # silhouette steps off the skin normal.  Closing this properly means
    # extending each plate along its own bone; until then the fist pose is
    # pitched at the deepest curl the rigid plates can cover.
    S.plate("hands", P["finger"], "Plate_Fingers", mat="M_ArmorSecondary",
            outer=1.80, relax=6, facet=26.0, bevel=0.16,
            stand=0.6, collapse=0.45, tri_cap=1800, hard=True, only=HAND_BONES)
    S.plate("hands", P["palm"], "Plate_Gauntlet", mat="M_ArmorPrimary",
            outer=2.1, relax=10, facet=20.0, trim=True,
            collapse=0.45, trim_width=0.34, tri_cap=1400,
            hard=True, only=HAND_BONES)

    # ---------------- LEGS ---------------------------------------------------
    S.undersuit("legs", lambda fi: slot[fi] == "legs", "Suit_Legs")
    for sd in ("l", "r"):
        S.plate("legs", P["tasset_" + sd], "Plate_Tasset_" + sd,
                outer=2.8, relax=12, facet=11.0, trim=True)
        S.plate("legs", P["thigh_" + sd], "Plate_Thigh_" + sd,
                outer=2.5, relax=11, facet=8.0, trim=True)
        S.plate("legs", P["knee_" + sd], "Plate_Knee_" + sd,
                mat="M_ArmorSecondary", outer=3.0, relax=10, facet=11.0,
                trim=True)
        S.plate("legs", P["calf_" + sd], "Plate_Greave_" + sd,
                mat="M_ArmorSecondary", outer=2.6, relax=11, facet=9.0,
                trim=True)

    # ---------------- FEET ---------------------------------------------------
    S.undersuit("feet", lambda fi: slot[fi] == "feet", "Suit_Feet",
                standoff=0.75, mat="M_Undersuit", collapse=0.25, tri_cap=900,
                only=FOOT_BONES)
    for sd in ("l", "r"):
        S.plate("feet", P["toe_" + sd], "Plate_ToeCap_" + sd,
                mat="M_ArmorSecondary", outer=2.5, relax=10, facet=26.0,
                trim=True, collapse=0.45, trim_width=0.32, tri_cap=550,
                hard=True, only=FOOT_BONES)
        S.plate("feet", P["ankle_" + sd], "Plate_AnkleCuff_" + sd,
                mat="M_ArmorSecondary", outer=2.4, relax=10, facet=22.0,
                trim=True, collapse=0.45, trim_width=0.32, tri_cap=300,
                hard=True, only=FOOT_BONES)
    boot = C.extract_faces(body, P["boot_upper"], "Plate_Boots", offset=0.0)
    S.finish(boot, "feet", "M_ArmorPrimary", 1.8, relax=10, facet=26.0,
            bevel=0.25, collapse=0.35, trim=True, trim_width=0.32, tri_cap=850,
            hard=True, only=FOOT_BONES)

    # hands and feet are the two slots with a hard per-slot cap; the caps above
    # are per-part estimates, this is the backstop that makes the budget exact
    for slotname, cap in SLOT_BUDGET.items():
        got = enforce_slot_budget(S, slotname, cap)
        print("  slot budget %-7s %6d / %6d  %s"
              % (slotname, got, cap, "OK" if got <= cap else "OVER"))

    # ---------------- BACK ---------------------------------------------------
    for ob in build_backpack(body, mats):
        S._register("back", ob, True, "plate")

    # ---------------- export -------------------------------------------------
    files = {
        "chest": "SKM_Armor_Chest.fbx",
        "shoulders": "SKM_Armor_Shoulders.fbx",
        "arms": "SKM_Armor_Arms.fbx",
        "hands": "SKM_Armor_Hands.fbx",
        "legs": "SKM_Armor_Legs.fbx",
        "feet": "SKM_Armor_Feet.fbx",
        "back": "SKM_Armor_Back.fbx",
    }
    total = 0
    print("\n--- per-slot ---")
    rows = []
    for slotname, fn in files.items():
        objs = [o for (o, _, _) in S.parts.get(slotname, [])]
        if not objs:
            print("  !! no parts for slot", slotname)
            continue
        joined = C.join_objects(objs, "SKM_Armor_" + slotname.capitalize())
        C.smart_uv(joined)
        tris = C.tri_count(joined.data)
        total += tris
        mats_used = [m.name for m in joined.data.materials]
        rows.append((fn, len(objs), tris, mats_used))
        C.export_fbx(arm, [joined], os.path.join(C.EXPORT_DIR, fn))
    print("\n%-28s %5s %7s  %s" % ("file", "parts", "tris", "materials"))
    for fn, n, tris, mu in rows:
        print("%-28s %5d %7d  %s" % (fn, n, tris, ",".join(mu)))
    print("TOTAL armor triangles: %d  (budget %d) %s"
          % (total, BUDGET_TRIS, "OK" if total < BUDGET_TRIS else "OVER!"))
    over = []
    for slotname, cap in SLOT_BUDGET.items():
        got = sum(t for fn, n, t, mu in rows if slotname in fn.lower())
        if got > cap:
            over.append("%s %d>%d" % (slotname, got, cap))
    if over:
        raise SystemExit("slot triangle budget exceeded: %s" % ", ".join(over))
    if total >= BUDGET_TRIS:
        raise SystemExit("total triangle budget exceeded: %d >= %d"
                         % (total, BUDGET_TRIS))
    print("weights: %d parts transferred (operator + explicit nearest-face map)"
          % len(C.TRANSFER_FALLBACKS))
    with open(os.path.join(C.EXPORT_DIR, "armor_tris.txt"), "w") as fh:
        for fn, n, tris, mu in rows:
            fh.write("%s %d %d %s\n" % (fn, n, tris, ",".join(mu)))
        fh.write("TOTAL %d\n" % total)
    print("DONE")


if __name__ == "__main__":
    main()