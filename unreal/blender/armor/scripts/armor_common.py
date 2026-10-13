# -*- coding: utf-8 -*-
"""
poly99+ hard-surface armor pipeline - shared helpers.

Conventions
-----------
* The reference FBXs import with the stock ``bpy.ops.import_scene.fbx`` settings,
  which yields armature object ``root`` (341 deform bones) and mesh objects whose
  *data* is in centimetres with a 0.01 object scale.  We never touch object
  transforms, so everything here works in that local space:
      Z up, +X = character left, 0 = floor.
  **Forward is -Y, not +Y** (derived from the toe direction, see
  ``Body.front``).  Never test ``p.y > 0`` for "front"; use
  ``body.forward_y(p)``.
* Face / vertex coordinates below are therefore centimetres.
* Exports use ``apply_scale_options='FBX_SCALE_UNITS'``, ``add_leaf_bones=False``,
  ``use_armature_deform_only=True``, ``mesh_smooth_type='FACE'`` and the default
  axis pair (forward -Z / up Y), which is the exact inverse of the importer.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

# --------------------------------------------------------------------------- #
# paths
# --------------------------------------------------------------------------- #
ARMOR_DIR = r"C:\UnrealProjects\poly99\unreal\blender\armor"
SCRIPTS_DIR = os.path.join(ARMOR_DIR, "scripts")
EXPORT_DIR = os.path.join(ARMOR_DIR, "export")
PREVIEW_DIR = os.path.join(EXPORT_DIR, "previews")
REF_BODY = r"C:\UnrealProjects\poly99\unreal\blender\reference\SKM_MHC_Hero_BodyMesh.fbx"
REF_FACE = r"C:\UnrealProjects\poly99\unreal\blender\reference\SKM_MHC_Hero_FaceMesh.fbx"

# --------------------------------------------------------------------------- #
# material palette - names are the contract with Unreal
# --------------------------------------------------------------------------- #
MATS = {
    # name:            (base rgb,               metallic, rough, emission rgb,          strength)
    # The plates sit well clear of the undersuit in value: a hard-surface read
    # needs the plate faces to separate from the suit at a glance, and UE
    # overrides these values anyway (they only drive the Workbench previews).
    "M_ArmorPrimary": ((0.170, 0.185, 0.210), 0.85, 0.34, None, 0.0),
    "M_ArmorSecondary": ((0.320, 0.335, 0.355), 0.80, 0.44, None, 0.0),
    "M_ArmorEmissive": ((0.030, 0.520, 0.620), 0.20, 0.30, (0.05, 0.90, 1.00), 8.0),
    "M_Visor": ((0.055, 0.085, 0.125), 0.90, 0.05, None, 0.0),
    "M_Undersuit": ((0.021, 0.023, 0.029), 0.05, 0.80, None, 0.0),
}

FBX_EXPORT = dict(
    use_selection=True,
    object_types={'ARMATURE', 'MESH'},
    apply_unit_scale=False,
    global_scale=1.0,
    # FBX_SCALE_UNITS makes Blender write UnitScaleFactor = 100 (the scene is in
    # metres), i.e. "one unit is a metre".  UE-authored MetaHuman FBX declare
    # 1.0 and store centimetres, so we must too or Unreal reads every export
    # 100x too small.  FBX_SCALE_CUSTOM with global_scale 1.0 is the only
    # combination that emits UnitScaleFactor = 1.0 (measured - see
    # tools/scale_matrix.py).
    apply_scale_options='FBX_SCALE_CUSTOM',
    mesh_smooth_type='FACE',
    add_leaf_bones=False,
    use_armature_deform_only=True,
    bake_anim=False,
    use_mesh_modifiers=True,
    use_subsurf=False,
    use_mesh_edges=False,
    axis_forward='-Z',
    axis_up='Y',
    # The UE-authored reference FBX reads back with *no* axis conversion under
    # Blender's default importer.  With use_space_transform=False the exporter
    # declares Y-up/-Z-forward but leaves the node transforms alone, so Blender
    # (and UE) then apply a spurious +90 deg X rotation on the way back in.
    # Writing the conversion into the object transforms reproduces the
    # reference exactly (verified in verify.py, world bone dev < 1e-6 m).
    use_space_transform=True,
    bake_space_transform=False,
    path_mode='AUTO',
    use_tspace=False,
    use_triangles=False,
    armature_nodetype='NULL',
    use_custom_props=False,
)


# --------------------------------------------------------------------------- #
# scene helpers
# --------------------------------------------------------------------------- #
def fresh_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    return scene


def import_fbx(path, mesh_names):
    """Import an FBX with stock settings; return (armature, [mesh objects])."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    arm.name = "root"
    arm.data.name = "root"
    assert len(meshes) == len(mesh_names), (len(meshes), mesh_names)
    for ob, nm in zip(meshes, mesh_names):
        ob.name = nm
        ob.data.name = nm
    return arm, meshes


def activate(obj, extra=()):
    bpy.ops.object.select_all(action='DESELECT')
    for o in extra:
        o.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


def make_materials():
    out = {}
    for name, (base, metal, rough, emis, strength) in MATS.items():
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*base, 1.0)
            bsdf.inputs["Metallic"].default_value = metal
            bsdf.inputs["Roughness"].default_value = rough
            if emis is not None:
                for key in ("Emission Color", "Emission"):
                    if key in bsdf.inputs:
                        bsdf.inputs[key].default_value = (*emis, 1.0)
                        break
                if "Emission Strength" in bsdf.inputs:
                    bsdf.inputs["Emission Strength"].default_value = strength
        # Workbench previews read diffuse_color, so light the emissive trim with
        # its emission hue (Unreal overrides both anyway).
        mat.diffuse_color = (*(emis if emis is not None else base), 1.0)
        mat.use_backface_culling = False
        out[name] = mat
    return out


def tri_count(mesh):
    return sum(len(p.vertices) - 2 for p in mesh.polygons)


def smart_uv(obj, angle=66.0, margin=0.003):
    activate(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin)
    bpy.ops.object.mode_set(mode='OBJECT')


# --------------------------------------------------------------------------- #
# geometry maths
# --------------------------------------------------------------------------- #
def seg_t_dist(p, a, b):
    """Return (raw t, clamped t, distance) of point p to segment a->b."""
    ab = b - a
    ll = ab.length_squared
    t = 0.0 if ll < 1e-12 else (p - a).dot(ab) / ll
    tc = max(0.0, min(1.0, t))
    return t, tc, (p - (a + ab * tc)).length


def ring_frame(axis):
    """Two unit vectors perpendicular to `axis` (stable, no roll surprises)."""
    axis = axis.normalized()
    ref = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
    u = axis.cross(ref).normalized()
    v = axis.cross(u).normalized()
    return u, v


def bvh_of(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    me = obj.evaluated_get(dg).to_mesh()
    me.calc_loop_triangles()
    verts = [me.vertices[i].co.copy() for i in range(len(me.vertices))]
    tris = [[t.vertices[0], t.vertices[1], t.vertices[2]] for t in me.loop_triangles]
    bvh = BVHTree.FromPolygons(verts, tris, all_triangles=True)
    obj.evaluated_get(dg).to_mesh_clear()
    return bvh


# --------------------------------------------------------------------------- #
# source-body analysis
# --------------------------------------------------------------------------- #
class Body(object):
    """Rest-pose analysis of the MetaHuman body mesh (centimetre space)."""

    def __init__(self, arm, obj):
        self.arm = arm
        self.obj = obj
        me = obj.data
        self.me = me
        self.verts = [v.co.copy() for v in me.vertices]
        self.vnorm = [v.normal.copy() for v in me.vertices]
        self.faces = [tuple(p.vertices) for p in me.polygons]
        self.fcenter = [p.center.copy() for p in me.polygons]
        self.fnormal = [p.normal.copy() for p in me.polygons]
        # minimum incident edge length per vertex (used to clamp offsets)
        self.min_edge = [1e9] * len(self.verts)
        for e in me.edges:
            a, b = e.vertices
            ln = (self.verts[a] - self.verts[b]).length
            self.min_edge[a] = min(self.min_edge[a], ln)
            self.min_edge[b] = min(self.min_edge[b], ln)
        # dominant deform group per face, used for coarse slot assignment
        vg = obj.vertex_groups
        self.vweights = [[(g.group, g.weight) for g in v.groups if g.weight > 1e-4]
                         for v in me.vertices]
        self.vgname = {g.index: g.name for g in vg}

        b = arm.data.bones
        self.bone = lambda n: b[n]
        self.head = lambda n: Vector(b[n].head_local)
        self.tail = lambda n: Vector(b[n].tail_local)

        # joint chain anchors (bone *heads* are reliable; bone tails are not)
        self.J = {}
        for s in ("l", "r"):
            sg = 1.0 if s == "l" else -1.0
            self.J[s] = {
                "shoulder": self.head("upperarm_%s" % s),
                "elbow": self.head("lowerarm_%s" % s),
                "wrist": self.head("hand_%s" % s),
                "hip": self.head("thigh_%s" % s),
                "knee": self.head("calf_%s" % s),
                "ankle": self.head("foot_%s" % s),
                "toe": (Vector(b["ball_%s" % s].head_local)
                        if "ball_%s" % s in b else self.tail("foot_%s" % s)),
                "sign": sg,
            }
        self.mid_hip = (self.J["l"]["hip"] + self.J["r"]["hip"]) * 0.5
        self.chest_z = self.head("spine_04").z
        self.neck_base_z = max(v.z for v in self.verts)
        self.bvh = bvh_of(obj)

        # Which way does this character face?  Derived from the toe direction,
        # never assumed: the first pass of this pipeline assumed "+Y is
        # forward" and it is wrong - the MetaHuman toes point -Y, so the
        # sternum ended up on the back and the backpack on the chest.
        # `front` is +1 when forward is +Y, -1 when forward is -Y.  Use
        # `body.forward_y(v)` for every front/back test.
        fs = []
        for s in ("l", "r"):
            d = (self.J[s]["toe"] - self.J[s]["ankle"])
            if d.length < 1e-6:
                raise ValueError("degenerate toe direction on side %s" % s)
            fs.append(1.0 if d.y > 0.0 else -1.0)
        if fs[0] != fs[1]:
            raise ValueError("left and right toes disagree: %s - the rig is "
                             "not mirrored, front/back predicates are unsafe"
                             % fs)
        self.front = fs[0]

    def forward_y(self, p):
        """Signed forward depth of point `p`: positive in front of the body."""
        return p.y * self.front

    # -- classification ---------------------------------------------------- #
    def face_group(self, fi):
        """Name of the dominant deform bone of face fi."""
        acc = {}
        for vi in self.faces[fi]:
            for gi, w in self.vweights[vi]:
                acc[gi] = acc.get(gi, 0.0) + w
        if not acc:
            return ""
        return self.vgname[max(acc.items(), key=lambda kv: kv[1])[0]]

    def is_finger_group(self, nm):
        p = nm.split('_')
        return ("metacarpal" in nm or "_l" in nm or "_r" in nm) and \
            any(t in nm for t in ("_01_", "_02_", "_03_", "metacarpal")) or \
            nm.startswith(("thumb_", "index_", "middle_", "ring_", "pinky_"))

    def is_toe_group(self, nm):
        return nm.startswith(("ball_", "bigtoe_", "indextoe_", "middletoe_",
                              "ringtoe_", "littletoe_"))


# --------------------------------------------------------------------------- #
# mesh construction primitives
# --------------------------------------------------------------------------- #
def new_object(name, bm, coll=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.update()
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.collection).objects.link(ob)
    return ob


def extract_faces(body, keep, name, offset=0.0, offset_clamp=1.2,
                  offset_floor=0.0):
    """Copy the faces selected by `keep(fi)->bool` and push them out along
    vertex normals.  Returns a new object (no modifiers applied yet).

    `offset_floor` is a MINIMUM push, and it matters.  The clamp alone
    (`min(offset, offset_clamp * min_edge)`) was silently shrinking the 8.5 mm
    undersuit standoff to 0.3-4 mm wherever the body mesh is finely tessellated
    - the inner thigh, above all.  An undersuit 1 mm off the skin is inside it
    as far as Unreal's depth test is concerned, and the thigh rendered
    body-coloured over the armour.  The floor keeps the shell unambiguously
    outside the skin in dense regions; it is only needed for the undersuit, so
    it defaults to 0 and leaves every other caller alone.
    """
    sel = [fi for fi in range(len(body.faces)) if keep(fi)]
    assert sel, "region '%s' selected no faces" % name
    bm = bmesh.new()
    vmap = {}
    for fi in sel:
        fv = []
        for vi in body.faces[fi]:
            if vi not in vmap:
                d = min(offset, offset_clamp * body.min_edge[vi])
                if offset_floor > 0.0:
                    d = max(offset_floor, d)
                nv = bm.verts.new(body.verts[vi] + body.vnorm[vi] * d)
                vmap[vi] = nv
            fv.append(vmap[vi])
        try:
            bm.faces.new(fv)
        except ValueError:
            pass
    bm.normal_update()
    return new_object(name, bm)


def smooth_relax(obj, iterations=6, factor=0.55):
    """Push every vertex toward the average of its neighbours (keeps the
    silhouette, kills the skin's micro-relief so decimation yields big facets)."""
    me = obj.data
    for _ in range(iterations):
        acc = [Vector((0, 0, 0)) for _ in me.vertices]
        cnt = [0] * len(me.vertices)
        for e in me.edges:
            a, b = e.vertices
            acc[a] += me.vertices[b].co
            acc[b] += me.vertices[a].co
            cnt[a] += 1
            cnt[b] += 1
        for i, v in enumerate(me.vertices):
            if cnt[i]:
                v.co = v.co.lerp(acc[i] / cnt[i], factor)
    me.update()


def planar_decimate(obj, angle_deg):
    """Dissolve nearly-coplanar faces -> large flat facets (the 'angular' read).
    Blender 5.2 renamed Decimate's PLANAR mode to DISSOLVE + angle limit."""
    activate(obj)
    m = obj.modifiers.new("planar", 'DECIMATE')
    m.decimate_type = 'DISSOLVE'
    m.angle_limit = math.radians(angle_deg)
    m.use_dissolve_boundaries = False
    bpy.ops.object.modifier_apply(modifier=m.name)


def collapse_decimate(obj, ratio):
    activate(obj)
    m = obj.modifiers.new("collapse", 'DECIMATE')
    m.decimate_type = 'COLLAPSE'
    m.ratio = ratio
    bpy.ops.object.modifier_apply(modifier=m.name)


def solidify(obj, thickness, rim=True):
    activate(obj)
    m = obj.modifiers.new("solid", 'SOLIDIFY')
    m.thickness = thickness
    m.offset = -1.0
    m.use_rim = rim
    m.use_rim_only = False
    bpy.ops.object.modifier_apply(modifier=m.name)


def bevel(obj, width=0.32, segments=1, angle=32.0):
    activate(obj)
    m = obj.modifiers.new("bevel", 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(angle)
    m.use_clamp_overlap = True
    m.harden_normals = False
    bpy.ops.object.modifier_apply(modifier=m.name)


def shade_flat(obj):
    me = obj.data
    for p in me.polygons:
        p.use_smooth = False


def shade_auto_smooth(obj, angle=38.0):
    me = obj.data
    for p in me.polygons:
        p.use_smooth = True
    mod = obj.modifiers.new("smooth_by_angle", 'NODES')
    ng = bpy.data.node_groups.get("Smooth by Angle")
    if ng is None:
        try:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(angle))
        except Exception:
            shade_flat(obj)
        return
    mod.node_group = ng
    try:
        mod["Socket_1"] = math.radians(angle)
    except Exception:
        pass


def trim_ribbon(obj, width=0.45, lift=0.06):
    """Build a thin emissive ribbon that follows an *open* surface's boundary.

    The ribbon has a constant physical ``width`` measured along the surface, so
    it stays a hairline light channel no matter how coarse the planar-decimated
    plate faces are.  (The obvious alternative - duplicating the faces adjacent
    to the boundary - produces a full-plate slab as soon as one decimated face
    touches the rim, which is what the first pass did.)

    ``lift`` raises the ribbon off the surface along the averaged vertex normal.
    Returns a new object, or None when the surface has no boundary.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    bedges = [e for e in bm.edges if len(e.link_faces) == 1]
    if not bedges:
        bm.free()
        return None

    vn, iw, cnt = {}, {}, {}
    for e in bedges:
        f = e.link_faces[0]
        n = f.normal.copy()
        d = e.verts[1].co - e.verts[0].co
        if d.length < 1e-9:
            continue
        d.normalize()
        inward = n.cross(d)
        if inward.length < 1e-9:
            continue
        inward.normalize()
        mid = (e.verts[0].co + e.verts[1].co) * 0.5
        if inward.dot(f.calc_center_median() - mid) < 0.0:
            inward = -inward
        for v in e.verts:
            vn[v] = vn.get(v, Vector((0, 0, 0))) + n
            iw[v] = iw.get(v, Vector((0, 0, 0))) + inward
            cnt[v] = cnt.get(v, 0) + 1
    for v in vn:
        if vn[v].length > 1e-9:
            vn[v].normalize()
        if iw[v].length > 1e-9:
            iw[v].normalize()

    adj = {}
    for e in bedges:
        a, b = e.verts[0], e.verts[1]
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    bm2 = bmesh.new()
    loops = 0
    seen = set()
    for e in bedges:
        start = e.verts[0]
        if start in seen:
            continue
        loop = [start]
        seen.add(start)
        cur, prev = start, None
        while True:
            nxt = None
            for cand in adj.get(cur, ()):
                if cand != prev and cand not in seen:
                    nxt = cand
                    break
            if nxt is None:
                break
            loop.append(nxt)
            seen.add(nxt)
            prev, cur = cur, nxt
        if len(loop) < 3:
            continue
        loops += 1
        # a vertex whose only boundary edge was degenerate never collected a
        # normal/inward vector; fall back to the face normal and a zero-width
        # inset so the strip still closes.
        outer, inner = [], []
        for v in loop:
            nv = vn.get(v) or Vector((0.0, 0.0, 1.0))
            iv = iw.get(v) or Vector((0.0, 0.0, 0.0))
            outer.append(bm2.verts.new(v.co + nv * lift))
            inner.append(bm2.verts.new(v.co + nv * lift + iv * width))
        for i in range(len(loop)):
            j = (i + 1) % len(loop)
            try:
                bm2.faces.new((outer[i], outer[j], inner[j], inner[i]))
            except ValueError:
                pass
    bm.free()
    if not loops:
        bm2.free()
        return None
    bm2.normal_update()
    ob2 = new_object(obj.name + "_Trim", bm2)
    ob2.matrix_world = obj.matrix_world.copy()
    return ob2


def project_to_body(obj, bvh, stand):
    """Snap every vertex onto the nearest point of the skin plus `stand` along
    the skin's outward normal.

    This replaces the Shrinkwrap modifier: in Blender 5.2 Shrinkwrap's
    ``offset`` moves vertices *against* the surface normal (verified - a plate
    requested at +1 cm landed at -1 cm), and its direction semantics are not
    exposed in a reliable way.  Doing it explicitly keeps the sign unambiguous.
    """
    for v in obj.data.vertices:
        loc, nor, _idx, _dist = bvh.find_nearest(v.co)
        v.co = loc + nor * stand
    obj.data.update()


def loft(sections, cap_start=True, cap_end=True, close=True):
    """Build a quad loft through a list of equal-length vertex rings."""
    bm = bmesh.new()
    rings = [[bm.verts.new(p) for p in sec] for sec in sections]
    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        rng = range(n) if close else range(n - 1)
        for i in rng:
            j = (i + 1) % n
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass
    if cap_start:
        try:
            bm.faces.new(list(reversed(rings[0])))
        except ValueError:
            pass
    if cap_end:
        try:
            bm.faces.new(rings[-1])
        except ValueError:
            pass
    bm.normal_update()
    return bm


# --------------------------------------------------------------------------- #
# skinning
# --------------------------------------------------------------------------- #
def parent_to_armature(objs, arm, like=None):
    """Parent to the armature and mirror the reference mesh object's world
    transform (the reference import carries a 0.01 object scale, so the armor
    objects must too or the armature modifier would deform the wrong space)."""
    ref = like.matrix_world.copy() if like is not None else None
    for ob in objs:
        ob.parent = arm
        ob.matrix_parent_inverse = arm.matrix_world.inverted()
        if ref is not None:
            ob.matrix_basis = ref
        mod = ob.modifiers.new(arm.name, 'ARMATURE')
        mod.object = arm
        mod.use_deform_preserve_volume = False


_SRC_CACHE = {}


def _source_cache(src):
    key = src.name_full
    if key not in _SRC_CACHE:
        me = src.data
        me.calc_loop_triangles()
        tris = [tuple(t.vertices) for t in me.loop_triangles]
        verts = [v.co.copy() for v in me.vertices]
        names = {g.index: g.name for g in src.vertex_groups}
        per_vert = []
        for v in me.vertices:
            acc = {}
            for g in v.groups:
                nm = names[g.group]
                if g.weight > acc.get(nm, 0.0):
                    acc[nm] = g.weight
            per_vert.append(acc)
        _SRC_CACHE[key] = (BVHTree.FromPolygons(verts, tris, all_triangles=True),
                           tris, verts, per_vert)
    return _SRC_CACHE[key]


def _barycentric(p, a, b, c):
    """Barycentric coordinates of p inside triangle abc."""
    v0, v1, v2 = c - a, b - a, p - a
    d00 = v0.dot(v0)
    d01 = v0.dot(v1)
    d11 = v1.dot(v1)
    d20 = v2.dot(v0)
    d21 = v2.dot(v1)
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-12:
        return (1.0, 0.0, 0.0)
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    return (1.0 - v - w, v, w)


def write_weights(obj, per_vertex):
    """Replace every weight on `obj` with `per_vertex` (list of {group: weight}).

    Blender 5.2 made ``MeshVertex.groups`` read-only, so weights are written
    through ``VertexGroup.add(..., 'REPLACE')`` in weight buckets.
    """
    names = []
    seen = set()
    for acc in per_vertex:
        for nm in acc:
            if nm not in seen:
                seen.add(nm)
                names.append(nm)
    lut = {}
    for nm in names:
        vg = obj.vertex_groups.get(nm) or obj.vertex_groups.new(name=nm)
        lut[nm] = vg
    all_idx = list(range(len(obj.data.vertices)))
    for vg in obj.vertex_groups:
        vg.add(all_idx, 0.0, 'REPLACE')
    for nm, vg in lut.items():
        buckets = {}
        for i, acc in enumerate(per_vertex):
            w = acc.get(nm, 0.0)
            if w > 0.0:
                buckets.setdefault(round(w, 4), []).append(i)
        for w, idxs in buckets.items():
            vg.add(idxs, w, 'REPLACE')
    for vg in list(obj.vertex_groups):
        if vg.index not in {g.index for g in lut.values()}:
            try:
                obj.vertex_groups.remove(vg)
            except Exception:
                pass
    return len(lut)


def nearest_face_weights(dst, src):
    """Nearest-face interpolated weight transfer: for every destination vertex
    find the closest triangle of `src` and blend its three corners' weights
    barycentrically.  This is the mapping Blender's Data Transfer operator used
    to expose as ``face_map_mode='NEAREST_FACE_INTERPOLATED'``."""
    bvh, tris, verts, per_vert = _source_cache(src)
    blended = []
    for dv in dst.data.vertices:
        loc, _nor, ti, _dist = bvh.find_nearest(dv.co)
        if ti < 0:
            blended.append({})
            continue
        a, b, c = tris[ti]
        acc = {}
        for w, i in zip(_barycentric(loc, verts[a], verts[b], verts[c]), (a, b, c)):
            if w <= 1e-5:
                continue
            for nm, val in per_vert[i].items():
                acc[nm] = acc.get(nm, 0.0) + w * val
        blended.append(acc)
    return write_weights(dst, blended)


def transfer_weights(dst, src, rigid=False, max_influences=4, hard=False,
                     only=None):
    """Copy skin weights from `src` onto `dst`.

    Primary path is Blender's Data Transfer operator.  In Blender 5.2 that
    operator only performs an index-based VGROUP_WEIGHTS copy (it silently does
    nothing when the destination topology differs), so we fall back to the
    equivalent nearest-face-interpolated mapping.

    ``hard`` / ``only`` are forwarded to clean_weights.
    """
    bpy.ops.object.select_all(action='DESELECT')
    src.select_set(True)
    dst.select_set(True)
    bpy.context.view_layer.objects.active = src          # active == source
    res = bpy.ops.object.datalayout_transfer(data_type='VGROUP_WEIGHTS')
    if res != {'FINISHED'}:
        raise RuntimeError("data transfer failed on %s: %s" % (dst.name, res))
    # Blender 5.2 performs an *index based* VGROUP_WEIGHTS copy (it silently
    # produces nothing, or garbage, when the destination topology differs from
    # the source), so the result is discarded and the documented
    # nearest-face-interpolated mapping is applied explicitly instead.
    n = nearest_face_weights(dst, src)
    if n == 0:
        raise RuntimeError("no skin weights could be transferred onto %s" % dst.name)
    TRANSFER_FALLBACKS.append(dst.name)
    clean_weights(dst, rigid=rigid, max_influences=max_influences,
                  hard=hard, only=only)


TRANSFER_FALLBACKS = []


def clean_weights(obj, rigid=False, max_influences=4, floor=1e-4,
                  hard=False, only=None):
    """Optional dominant-bone collapse, cap influences, renormalise.

    ``hard=True`` keeps a single bone at weight 1.0 - the only safe weighting
    for anything riding a finger phalanx, because a plate that shares weight
    with the metacarpal stretches into a shard the moment the finger curls.

    ``only`` is a set of bone names; any influence outside it is dropped before
    the collapse, which is how the glove keeps its smoothing without inheriting
    forearm or wrist weights it should never have.
    """
    names = {g.index: g.name for g in obj.vertex_groups}
    out = []
    for v in obj.data.vertices:
        entries = [(names[g.group], g.weight) for g in v.groups
                   if g.weight > floor and (only is None or names[g.group] in only)]
        if not entries:
            out.append({})
            continue
        entries.sort(key=lambda kv: -kv[1])
        if hard:
            out.append({entries[0][0]: 1.0})
            continue
        if rigid:
            top = entries[0][1]
            entries = [e for e in entries if e[1] >= top * 0.5][:2] or [entries[0]]
        else:
            entries = entries[:max_influences]
        tot = sum(w for _, w in entries)
        out.append({nm: w / tot for nm, w in entries})
    write_weights(obj, out)


def join_objects(objs, name):
    activate(objs[0], extra=objs[1:])
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def assign_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# --------------------------------------------------------------------------- #
# export
# --------------------------------------------------------------------------- #
def export_fbx(arm, objs, path):
    """Export the armature (optional) and `objs` to `path`.

    Unit convention - the important part.  The UE-authored reference FBX stores
    centimetre coordinates, carries no scale on its mesh node, and declares
    ``UnitScaleFactor = 1.0``.  Blender's round trip is happy with almost
    anything (its importer normalises units and always agrees with itself), so
    this has to be checked against the raw file - see fbx_probe.py.

    Measured over the export-option matrix (tools/scale_matrix.py):

        FBX_SCALE_UNITS    -> UnitScaleFactor 100, node scale 1
        FBX_SCALE_CUSTOM   -> UnitScaleFactor 1,   node scale 100
        FBX_SCALE_CUSTOM + objects keeping their 0.01 import scale
                          -> UnitScaleFactor 1,   node scale 1   <- this

    The node scale Blender writes under FBX_SCALE_CUSTOM is the metre->cm
    factor (100) times the object's own scale, so leaving the reference
    import's 0.01 object scale in place cancels it exactly.  Flattening the
    objects to identity instead (the obvious fix) yields node scale 100 and
    puts every export 100x too large.
    """
    bpy.ops.object.select_all(action='DESELECT')
    if arm is not None:
        arm.select_set(True)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = arm if arm is not None else objs[0]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    kw = dict(FBX_EXPORT)
    if arm is None:
        kw['object_types'] = {'MESH'}
    bpy.ops.export_scene.fbx(filepath=path, **kw)
    tris = sum(tri_count(o.data) for o in objs)
    print("  exported %-28s %6d tris  %d parts" % (os.path.basename(path), tris, len(objs)))
    return tris