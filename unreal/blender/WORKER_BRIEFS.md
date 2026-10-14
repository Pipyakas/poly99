# Blender worker briefs (moved from the scratch thread, 2026-10-13)

> Restored by the composer on 2026-10-13 after the kit worker deleted it as a "stray" file.
> Not a worker deliverable: workers must not delete this file.

Both tasks were cancelled mid-run in the old thread and are to be resumed from the poly99
project thread. Re-delegate with the brief below plus a "resume" preamble: inspect what is
already on disk, keep what is good, finish the missing deliverables, do not start over.

## State at cancellation

- **Kit (ccgw/ling-3.1-flash-free, task poly99-blender-kit-r2):**
  all 9 FBXs + 2 voxel JSONs + 9 previews + source .blend files + README.md exist.
  Unverified: README measurement table, preview quality, axis/pivot correctness.
- **Armor (ccgw/space-bunny-free, task poly99-armor-r1):** 7 SKM_Armor_*.fbx, SM_Helmet_A.fbx,
  SKM_Helmet_A.fbx, previews (rest/arms_forward/deep_lunge/twist_aim + helmet on/off),
  verify_report.json (round-trip OK: 341 bones, rest deviation ~1e-6; ~58k tris so far, hands
  15k / feet 12k are heavy). Missing: armor/scripts/build.ps1, armor/README.md, penetration table.
  Early rest preview looked like mostly undersuit with sparse plates — needs a quality pass.

## Brief 1 — voxel enemies + arena kit (original text)

Work autonomously; do not ask permission questions. Only create/modify files under
C:\UnrealProjects\poly99\unreal\blender\ (excluding armor/). Do not touch anything else, do not
run git clean/reset, do not commit, and do NOT connect to any running Blender MCP server — run
Blender headless only.

Goal: reproducible Blender Python scripts that generate stylized game assets for "poly99+", a
top-down twin-stick shooter inspired by Nex Machina (voxel enemies that shatter into cubes,
neon-lit sci-fi arena). Original designs only. Assets are imported into Unreal Engine 5.8
(Z-up, centimeters, X forward).

Blender: "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe". Run scripts with
`"<blender.exe>" -b --factory-startup --python <script.py>`. Scripts idempotent, bpy/bmesh/
mathutils only.

Conventions (scripts/common.py): 1 BU = 1 m; FBX so Blender +X faces UE +X, Z up;
apply_scale_options='FBX_SCALE_UNITS', use_selection=True, mesh_smooth_type='FACE',
use_mesh_modifiers=True, add_leaf_bones=False; pivot at base center; transforms applied; SM_
prefixes; materials M_<Role> (M_VoxelBody, M_VoxelEmissive, M_FloorBase, M_FloorGrid,
M_WallTrim, M_Glow) + vertex color attribute "Col".

Assets: SM_Enemy_Grasshopper (6 cm voxels, ~60x35 cm, crimson, emissive eye voxels facing +X),
SM_Enemy_Wanderer (~80 cm, amber, emissive core), each from a code-defined occupancy grid with
only exterior faces + <name>_voxels.json (voxel size, origin, filled voxel centers in cm UE axes,
color role); SM_VoxelDebris (6 cm beveled cube < 100 tris). Arena kit on a 400 cm grid:
SM_Floor_Tile_400 (400x400x10, seams, M_FloorGrid strips), SM_Wall_400 (400x120x40, glowing
trim), SM_Wall_Corner, SM_Pillar (80x80x300), SM_Edge_GlowStrip (400), SM_Spawn_Gate (~300 wide);
each < 5k tris. scripts/preview.py renders 512x512 PNGs to export/previews/; .blend sources to
source/; scripts/build_all.ps1 runs everything and fails on error; README.md with conventions,
file list, and a re-import measurement table (tris + bbox cm per FBX). Check previews visually
and fix normals/facing/pivots.

## Brief 2 — armor + helmet fitted to the MetaHuman (original text)

Work autonomously; do not ask permission questions. Only create/modify files under
C:\UnrealProjects\poly99\unreal\blender\armor\. Headless Blender only; no git clean/reset/commit.

Goal: reproducible pipeline building a sleek sci-fi FULL-BODY hard-surface armor set and a
helmet fitted to the hero MetaHuman (clean angular plates, panel seams, thin cyan emissive trim).
Armor stops at the neck (collar ok); helmet is separate so the face shows when it is off.

Inputs: unreal/blender/reference/SKM_MHC_Hero_BodyMesh.fbx (armature "root", 341 bones, A-pose,
neck-down body ~1.50 m) and SKM_MHC_Hero_FaceMesh.fbx.

Deliverables:
1. armor/scripts/armor_set_a.py → armor/export/SKM_Armor_{Chest,Shoulders,Arms,Hands,Legs,Feet,
   Back}.fbx, skinned to the same armature (Data Transfer weights, max 4 influences, normalized,
   rigid plates dominated by their main bone), full coverage of skin neck-down (undersuit
   0.5–1 cm + plates 1.5–4 cm), total < 70k tris; exports round-trip onto the MetaHuman skeleton
   (armature "root", add_leaf_bones=False, deform bones only, FBX_SCALE_UNITS, FACE smoothing).
2. armor/scripts/helmet_a.py → SM_Helmet_A.fbx (static, origin/axes = `head` bone rest
   transform; document convention and any needed UE relative transform) + SKM_Helmet_A.fbx
   (100% `head` weights); encloses head + ~2 cm hair; opaque dark visor + emissive trim; < 8k tris.
3. Materials M_ArmorPrimary, M_ArmorSecondary, M_ArmorEmissive, M_Visor, M_Undersuit; UVs.
4. armor/scripts/verify.py: re-import check (tris, bones ⊆ reference); 4 test poses (rest, arms
   forward 90°, deep lunge, torso twist 35° + aim) with penetration metric (% of body verts
   excluding head/neck with no armor hit within 6 cm along the normal; target < 2%); Workbench
   768x768 previews per pose (front/side/3/4 top) + helmet on/off with the face mesh.
5. armor/scripts/build.ps1 (runs all, fails on error); armor/README.md (run steps, conventions,
   tri/bone table, penetration table per pose, known issues).
Iterate on previews and numbers; report honestly.

## Composer findings (2026-10-13, project thread)

- Both pipelines exported with `apply_unit_scale=False` in a metre scene: UE imports every FBX
  100x too small (SM_Pillar 0.8 x 0.8 x 3 cm; SKM_Armor_Chest extent 0.2 x 0.16 x 0.33 cm).
  Blender round-trips hide this. Sent back to both workers with a raw-FBX measurement requirement.
- Helmet v1 is a jar shape with an open crown and a wrap-around visor band: redesign requested.
