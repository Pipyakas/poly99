# -*- coding: utf-8 -*-
"""Find FBX export options giving UnitScaleFactor 1.0 AND node scale 1.0 with
centimetre coordinates - i.e. exactly the UE-authored reference convention."""
import os
import sys
import tempfile

import bpy
from mathutils import Matrix

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import armor_common as C  # noqa: E402
import fbx_probe as P  # noqa: E402

print("apply_scale_options enum:")
for it in bpy.ops.export_scene.fbx.get_rna_type().properties['apply_scale_options'].enum_items:
    print("   ", it.identifier)

BASE = dict(C.FBX_EXPORT)
out = tempfile.mkdtemp()
# (label, opts, global_scale, apply_unit_scale, units, scale_length, use_space_transform)
CASES = [
    ("custom_1_st",      'FBX_SCALE_CUSTOM', 1.0, False, 'METRIC', 1.0,   True, 1.0),
    ("custom_objscale",  'FBX_SCALE_CUSTOM', 1.0, False, 'METRIC', 1.0,   True, 0.01),
    ("units_objscale",   'FBX_SCALE_UNITS',  1.0, False, 'METRIC', 1.0,   True, 0.01),
    ("units_identity",   'FBX_SCALE_UNITS',  1.0, False, 'METRIC', 1.0,   True, 1.0),
]
print("\n%-16s %-16s %-6s %-11s %-9s %-7s %s"
      % ("case", "opts", "usf", "raw z span", "node sc", "units", "ok"))
for name, opts, gs, apply_us, usys, slen, space, oscale in CASES:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = usys
    sc.unit_settings.scale_length = slen
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.5))
    ob = bpy.context.view_layer.objects.active
    # geometry always in centimetres; only the *object* scale varies
    ob.data.transform(Matrix.Diagonal((0.01, 0.01, 0.01, 1.0)))   # 1 cm cube
    ob.location = (0.0, 0.0, 0.5)                                # at 50 cm
    ob.scale = (oscale, oscale, oscale)
    kw = dict(BASE)
    kw.update(apply_scale_options=opts, global_scale=gs,
              apply_unit_scale=apply_us, use_space_transform=space)
    p = os.path.join(out, name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=p, **kw)
    usf = P.global_settings(p).get('UnitScaleFactor')
    lo, hi, _n, _m = P.vertices(p)
    scales = [s for _nm, _c, _t, s in P.model_transforms(p) if s]
    ns = scales[0][0][1] if scales else 1.0
    ok = (abs(float(usf) - 1.0) < 1e-6 and abs(ns - 1.0) < 1e-4
          and abs((hi[2] - lo[2]) - 1.0) < 0.2)
    print("%-16s %-16s %-6s %-11.5f %-9s %-7s %s"
          % (name, opts, usf, hi[2] - lo[2],
             ("%.4f" % ns) if scales else "none", usys, "YES" if ok else ""))