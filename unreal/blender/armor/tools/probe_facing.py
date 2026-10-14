# -*- coding: utf-8 -*-
"""Which way does the MetaHuman actually face in the space the pipeline works in?

Everything front/back in the armour set is a hand-tuned y threshold, so the
convention has to be *derived* and asserted, not assumed.
"""
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import armor_common as C  # noqa: E402

arm, meshes = C.import_fbx(C.REF_BODY, ["BODY"])
body = meshes[0]
b = arm.data.bones

for sd in ("l", "r"):
    f = b["foot_%s" % sd]
    ball = b["ball_%s" % sd]
    d = ball.head_local - f.head_local
    print("foot_%s head=(%.1f, %.1f, %.1f)  ball head=(%.1f, %.1f, %.1f)"
          % (sd, f.head_local.x, f.head_local.y, f.head_local.z,
             ball.head_local.x, ball.head_local.y, ball.head_local.z))
    print("    ball-foot direction = (%.2f, %.2f, %.2f)" % (d.x, d.y, d.z))

me = body.data
co = [v.co for v in me.vertices]
zs = [p.z for p in co]
zmin, zmax = min(zs), max(co and zs)
lo = sorted(co, key=lambda p: p.z)[:400]           # lowest 400 verts = feet
print("\nlowest-400 vert  y: min %.1f  max %.1f  mean %.1f"
      % (min(p.y for p in lo), max(p.y for p in lo),
         sum(p.y for p in lo) / len(lo)))
hi = sorted(co, key=lambda p: p.z)[-400:]          # highest = head
print("highest-400 vert y: min %.1f  max %.1f  mean %.1f"
      % (min(p.y for p in hi), max(p.y for p in hi),
         sum(p.y for p in hi) / len(hi)))

# the nose is the single most forward head vertex
head = [p for p in co if p.z > 160.0]
fy = max(p.y for p in head)
print("most forward head vertex y = %.1f (head y range %.1f .. %.1f)"
      % (fy, min(p.y for p in head), max(p.y for p in head)))

# buttocks vs chest at belly height: the body is not symmetric in y there
torso = [p for p in co if 108.0 < p.z < 118.0 and abs(p.x) < 12.0]
print("torso band y range %.1f .. %.1f" % (min(p.y for p in torso),
                                           max(p.y for p in torso)))
print("\n=> character faces %s  (front sign = %+d)"
      % ("+Y" if fy > 0 else "-Y", 1 if fy > 0 else -1))