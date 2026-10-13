# poly99+ hero hard-surface armour (variant A)

Reproducible headless-Blender pipeline that builds a full-body sci-fi hard-surface
armour set plus a separate helmet, skinned to the hero MetaHuman skeleton.

Everything is generated from the reference FBXs — no hand-modelled source meshes.

```
unreal/blender/armor/
├── scripts/
│   ├── armor_common.py    shared geometry / skinning / FBX-export helpers
│   ├── armor_set_a.py     the armour set  -> SKM_Armor_*.fbx
│   ├── helmet_a.py        the helmet      -> SM_Helmet_A.fbx, SKM_Helmet_A.fbx
│   ├── fbx_probe.py       raw FBX reader - what Unreal sees, no importer
│   ├── verify.py          unit check, re-import checks, pose coverage, previews
│   └── build.ps1          runs all three, stops at the first failure
├── export/                FBX outputs, verify_report.json, previews/, logs/
└── tools/                 bone-name dumps + scale_matrix.py (diagnostic)
```

## Running

```powershell
pwsh -File unreal\blender\armor\scripts\build.ps1
pwsh -File unreal\blender\armor\scripts\build.ps1 -Blender "D:\blender.exe"   # other install
pwsh -File unreal\blender\armor\scripts\build.ps1 -SkipVerify                  # geometry only
```

Blender 5.2, headless, factory startup, no running instance required:

```
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python <script>
```

`build.ps1` writes one log per stage to `export/logs/` and prints a summary table.
A stage fails the build on a non-zero exit **or** on a `Traceback` / `SystemExit`
in its output — Blender returns 0 even when a script raises, so both are checked.

Full run: ~35 s.

## Inputs

| File | Use |
|---|---|
| `../reference/SKM_MHC_Hero_BodyMesh.fbx` | body skin + `root` armature (341 deform bones), A-pose, neck-down ~1.50 m |
| `../reference/SKM_MHC_Hero_FaceMesh.fbx` | head/hair used to fit the helmet |

## Conventions

* **Units.** The reference FBXs import with Blender's stock importer: mesh *data*
  is in centimetres and the objects carry a 0.01 object scale. Generator scripts
  work in that local centimetre space (`Z` up, **`-Y` character forward**, `+X`
  character left, `0` = floor) and never touch object transforms.
* **Facing is derived, not assumed.** See below — every front/back test in the
  set is a sign flip of `Body.front`, which is measured from the toe direction
  and asserted on both feet.
* **Skeleton.** Every skinned export uses armature object `root` / data `root`,
  the same 341 deform bones as the reference, no extra or leaf bones.
* **FBX export.** `apply_scale_options='FBX_SCALE_CUSTOM'`, `global_scale=1.0`,
  `apply_unit_scale=False`, `add_leaf_bones=False`,
  `use_armature_deform_only=True`, `mesh_smooth_type='FACE'`,
  `use_space_transform=True`. Verified round-trip: rest-pose world bone deviation
  vs the reference is **< 1e-6 m** for all skinned exports.
* **Skinning.** Data Transfer is run first, then the weights are written
  explicitly by nearest-face-interpolated mapping — Blender 5.2's
  `datalayout_transfer(VGROUP_WEIGHTS)` does an *index-based* copy that silently
  produces nothing when the destination topology differs. Weights are capped at 4
  influences and renormalised; plates and trim are collapsed to their dominant
  bone (rigid), the undersuit keeps smooth blending.

## Facing — derived from the toes, asserted on both feet

The first version of this pipeline *assumed* `+Y` was character forward. It is
not, and the error was invisible in the previews because the cameras inherited
the same wrong assumption — `rest_front.png` showed the character's back.

`armor_common.Body` now measures it instead:

```python
for s in ("l", "r"):
    d = self.J[s]["toe"] - self.J[s]["ankle"]
    fs.append(1.0 if d.y > 0.0 else -1.0)
if fs[0] != fs[1]:
    raise ValueError("left and right toes disagree ... not mirrored")
self.front = fs[0]
```

The rig reads `front = -1`, i.e. **the MetaHuman faces `-Y` in the pipeline's
space** — confirmed independently by `tools/probe_facing.py` (the `ball` − `foot`
direction is y = −14.21, the lowest 400 body vertices — the feet — average
y = −14.0, and the most forward head vertex is at negative y). Both feet must
agree or the build aborts, because the front/back predicates are only safe on a
mirrored rig.

`Body.forward_y(p)` is the single signed accessor every asymmetric placement
uses, so a sign flip is a one-line change:

| Consumer | Test |
|---|---|
| sternum / chest plate | `body.forward_y(c) >= 3.0` |
| back plate | `body.forward_y(c) <= -5.0` |
| backpack (`build_backpack`) | every `y` multiplied by `F`, thruster spin by `-22.0 * F` |
| helmet visor / back plate | `FRONT_ANG = -pi/2`, `BACK_ANG = +pi/2` around the head axis |
| preview cameras (`make_views`) | every `y` multiplied by `F` |

`verify.py` re-derives the sign from the imported rig and writes it to
`verify_report.json` as `facing: {front_sign, forward_axis}`.

**Unreal-space note.** The composer's UE measurement puts the same character's
toes at `+Y` (UE feet-bounds centre y = +8.6). That is the FBX axis conversion
applied on export, not a disagreement about the character: the exports are built
and measured in one space and handed to Blender's exporter, which converts. The
previews and the armour are consistent inside the pipeline space; if a plate ever
reads mirrored in UE it is the node-level `PreRotation`/axis flag on import, not
the geometry, and the fix is an import setting.

## Units — the Unreal scale bug, and how it is guarded

**This is the one thing that cannot be checked with Blender's importer.** Blender
normalises units on the way in, so an import round trip always agrees with
itself and will happily accept a file that declares centimetres while storing
metres. Unreal reads the header and the raw arrays literally. `verify.py` step 0
therefore parses the FBX container directly (`scripts/fbx_probe.py`) and asserts
what UE will see.

The UE-authored reference, measured the same way:

| | reference `SKM_MHC_Hero_BodyMesh.fbx` |
|---|---|
| `UnitScaleFactor` | **1.0** |
| mesh node `Lcl Scaling` | *absent* (1.0) |
| raw vertex array | centimetres, z span **150.09 cm** |

What the pipeline exports now — same convention on every axis:

| file | `UnitScaleFactor` | node scale | UE size X × Y × Z (cm) |
|---|---:|---|---|
| *(reference)* `SKM_MHC_Hero_BodyMesh` | 1.0 | unit | 114.13 × 41.04 × **150.09** |
| `SKM_Armor_Chest` | 1.0 | unit | 39.51 × 31.71 × **66.49** |
| `SKM_Armor_Shoulders` | 1.0 | unit | 62.25 × 25.94 × 21.05 |
| `SKM_Armor_Arms` | 1.0 | unit | 107.23 × 29.88 × 39.98 |
| `SKM_Armor_Hands` | 1.0 | unit | 116.12 × 18.31 × 19.12 |
| `SKM_Armor_Legs` | 1.0 | unit | 43.31 × 30.05 × 95.15 |
| `SKM_Armor_Feet` | 1.0 | unit | 47.38 × 30.06 × 16.79 |
| `SKM_Armor_Back` | 1.0 | unit | 23.20 × 8.65 × 44.58 |
| `SM_Helmet_A` / `SKM_Helmet_A` | 1.0 | unit | 36.60 × 31.23 × 33.56 (head-bone local) |

The chest is **66.5 cm** tall against the 60–70 cm target, and the reference body
is 150.1 cm neck-down, so the two now sit on the same scale.

**Why the obvious fixes do not work** (measured by `tools/scale_matrix.py`):

| `apply_scale_options` | object scale | `UnitScaleFactor` | node scale | result |
|---|---:|---:|---:|---|
| `FBX_SCALE_UNITS` | 0.01 | 100 | 0.01 | **100× too small in UE** ← the bug |
| `FBX_SCALE_UNITS` | 1.00 | 100 | 1.00 | correct size, `usf` ≠ reference |
| `FBX_SCALE_CUSTOM` | 1.00 | 1.0 | 100 | 100× too large |
| `FBX_SCALE_CUSTOM` | 0.01 | 1.0 | 1.00 | **correct — used here** |

The node scale Blender writes under `FBX_SCALE_CUSTOM` is the metre→cm factor
(100) multiplied by the object's own scale, so leaving the reference import's
0.01 object scale in place cancels it exactly. Flattening the objects to identity
— the fix one would reach for first — yields node scale 100 and puts every export
100× too *large*.

`verify.py` fails the build if any export's `UnitScaleFactor` is not 1.0, if any
node carries a non-unit `Lcl Scaling`, or if the chest leaves the 60–70 cm band.

### Helmet transform convention

Two exports, deliberately:

* **`SM_Helmet_A.fbx`** — static. Mesh data is in the **`head` bone's local
  space** and the object transform is that bone's rest matrix
  (`root.matrix_world @ bones['head'].matrix_local`; origin
  `(0, -0.012, 1.6461)` m, axes = bone axes). Re-importing it into a scene
  containing the reference skeleton reproduces the authored position exactly.
  In Unreal, import it and attach it to the `head` socket with an **identity**
  relative transform — the socket already carries the bone's rest transform, so
  anything else double-transforms it.
* **`SKM_Helmet_A.fbx`** — same mesh, 100 % weighted to `head` on the `root`
  armature. Use this instead if you want the helmet to ride animation without a
  separate attach step.

### Materials

| Name | Role |
|---|---|
| `M_ArmorPrimary` | main plate faces, cool gunmetal |
| `M_ArmorSecondary` | accent plates (collar, knee, cuff, digits) |
| `M_ArmorEmissive` | thin cyan trim channels, emission 8.0 |
| `M_Visor` | opaque dark blue-black visor |
| `M_Undersuit` | matte charcoal suit, visible only at joints |

All slots are UV'd (`smart_project`). Material values exist mainly so the
Workbench previews read correctly; Unreal overrides them.

### How a plate is made

Body faces are selected by region predicate → relaxed → collapse-decimated →
planar-decimated (dissolve near-coplanar faces, which is what gives the angular
faceted read) → snapped back onto the skin with `project_to_body` at a 1.0 cm
stand-off → solidified outwards to 1.5–4 cm → bevelled → flat shaded.

`project_to_body` replaces Blender's Shrinkwrap modifier deliberately: in 5.2
Shrinkwrap's `offset` moves vertices *against* the surface normal, which silently
puts plates 1 cm *inside* the body.

The **undersuit** is a copy of the whole skin region pushed 0.7–0.9 cm out along
the vertex normals, weighted like the body. It is the coverage guarantee: it has
the skin's own topology, so it cannot gap. Plates sit on top of it.

The **trim** is a constant-width ribbon following each plate's open boundary
(`armor_common.trim_ribbon`), lifted just clear of the plate's outer face. An
earlier version duplicated the boundary-adjacent *faces*; after planar decimation
one such face is often the whole plate, so the trim rendered as a full-plate cyan
slab and hid the plate underneath. A ribbon has a fixed 3–4 mm width regardless of
face size.

## Budgets

| Slot | Triangles | Budget |
|---|---:|---:|
| `SKM_Armor_Chest.fbx` | 9 075 | — |
| `SKM_Armor_Shoulders.fbx` | 3 614 | — |
| `SKM_Armor_Arms.fbx` | 7 620 | — |
| `SKM_Armor_Hands.fbx` | 5 713 | ≤ 6 000 |
| `SKM_Armor_Legs.fbx` | 11 017 | — |
| `SKM_Armor_Feet.fbx` | 3 960 | ≤ 4 000 |
| `SKM_Armor_Back.fbx` | 896 | — |
| **armour total** | **41 895** | **< 70 000** |
| `SM_Helmet_A.fbx` / `SKM_Helmet_A.fbx` | 6 580 each | < 8 000 |

Bones: 341 in every skinned export (subset of the reference — `verify.py` fails
the status if any bone name is not in the reference skeleton).

Per-slot caps are enforced twice: per-part `tri_cap` estimates during the build,
then `enforce_slot_budget()` collapses the heaviest plate until the slot total
fits. `build.ps1` fails if a cap or the total is exceeded.

## Verification

`verify.py` first checks the raw unit declaration against the reference (step 0,
see above), then re-imports every FBX into an empty scene, then poses one rig
through nine test poses and measures coverage **per side**, then runs the
bare-skin acceptance check against the gameplay camera, then renders previews.

**Coverage.** For every body vertex below z = 1.42 m (head/neck excluded) two
independent measures are taken:

* **`gap3cm`** — *gated.* Cast along `+normal` and take the **first** hit; count
  verts whose first armour surface is further than 3 cm. This is the direction
  that matches the brief's probe.
* **`near>3cm`** — *reported.* `find_nearest` distance to any armour surface,
  thresholded at 3 cm. Direction-free, so it cannot be fooled by geometry on the
  far side of a limb.

The brief's original wording — "no armour within 3 cm along `+normal`" — counts a
*hit anywhere on the ray*, and that is a **false pass on limbs**: where the
undersuit has a gap the ray leaves the arm and strikes the plate on the other
side, so a genuinely bare upper arm still reports zero. Both are kept: `gap3cm`
gates, `near>3cm` is the independent cross-check that proves a zero in the gated
column is a zero for the right reason.

**Per-side reporting.** `gap3cm` is counted for the left and the right side
separately and **never summed or averaged into the headline number**. A side is
the body's *rest* `x` sign, so a limb that crosses the centreline in a pose keeps
its own label; `|x| < 1 cm` is the midline and counts as neither. The overall
target is < 1 % **and** each side must independently be < 1 %.

This is not ceremony. When the per-side gate was first switched on it failed
immediately: the fist pose read 0.98 % overall — a pass — while the **left side
alone was 1.02 %**. A one-sided defect is exactly what an average hides, and
0.98 % of the whole body is 0.4 % of one leg, which is the size of the bare
thigh this check exists to catch.

| Pose | gap3cm | near>3cm | poke | L | R | \|L−R\| |
|---|---:|---:|---:|---:|---:|---:|
| rest | 0.10 % | **0.00 %** | 3.62 % | 0.14 % | 0.05 % | 0.09 |
| arms forward 90° | 0.18 % | **0.00 %** | 3.79 % | 0.26 % | 0.10 % | 0.17 |
| deep lunge | 0.33 % | **0.00 %** | 3.97 % | 0.38 % | 0.29 % | 0.09 |
| torso twist 35° + aim | 0.16 % | **0.00 %** | 4.24 % | 0.24 % | 0.07 % | 0.17 |
| walk stride (L forward) | 0.25 % | **0.00 %** | 3.84 % | 0.33 % | 0.17 % | 0.16 |
| walk stride (R forward) | 0.23 % | **0.00 %** | 3.88 % | 0.21 % | 0.24 % | 0.03 |
| legs apart | 0.16 % | **0.00 %** | 3.62 % | 0.24 % | 0.07 % | 0.17 |
| relaxed hand | 0.23 % | **0.00 %** | 4.96 % | 0.21 % | 0.24 % | 0.03 |
| fist | 0.84 % | **0.00 %** | 4.59 % | 0.88 % | 0.79 % | 0.09 |

Targets: **< 1 % overall and < 1 % per side**, both enforced with `SystemExit`.
Worst cell is the fist's left side at 0.88 %; the largest L/R split is 0.17
percentage points.

`near>3cm` is **0.00 % in all nine poses** — there is no point on the body, in any
pose, that is more than 3 cm from an armour surface. Anything above target in
`gap3cm` is therefore skin *poking through* a plate seam under deformation, not a
missing undersuit, which is why the two columns are reported side by side rather
than merged.

### Leg poses

The original set never split the legs, which is the state that matters: with the
legs together an inner-thigh normal hits the *other* leg's armour within 3 cm and
reads as covered whether or not it is. Three poses now open them up:

| Pose | What it does |
|---|---|
| `walk_stride` | a walk-cycle frame — left leg forward 26°/34°, right back 22°, arms counter-swinging |
| `walk_stride_b` | the same frame with the other foot forward, so the leading leg is tested in both halves of the cycle |
| `legs_apart` | wide stance with the knees driven apart — the pose that exposes the inner thigh |

### Bare-skin acceptance check

The vertex probe answers "is there armour just outside this body vertex", which
is the right question for geometry but not the acceptance criterion, which is a
*picture*: **no visible skin in the top-down gameplay camera at 1280×960 with the
spring arm between 2.3 m and 4.3 m**.

`verify.bare_skin_check` renders three passes from one perspective camera —
body only, armour only, both — with `film_transparent` so the alpha channel
carries the silhouette, then marks every pixel where the body silhouette has no
armour behind it. It needs no normals, cannot be fooled by which way a surface
faces, and writes a mask image so a failure says *where*, not just how much.

27 renders: 3 poses × 3 camera angles (`cam28` 28° front, `top` 55° down, `side`
22°/62°) × 3 spring arms (2.3 / 3.3 / 4.3 m).

**Worst result: 0.0034 %** of the body silhouette (≈ 10 pixels of 295 716, at
the most extreme close camera), against a 0.05 % target. Mask images are written
to `export/previews/uecam/*_BARE.png` for every case.

"Poke" is the complementary measure — the nearest armour surface lying *behind*
the skin along its own normal and within 5 mm, i.e. a plate sunk through the
body. It is reported, not gated.

### Hand poses

The original pose set never bent a finger, so hand skinning was only ever seen in
the rest pose. Two hand poses were added, both driving **every** finger bone:

| Pose | MCP / PIP / DIP (fingers) | MCP / PIP / DIP (thumb) |
|---|---|---|
| `relaxed_hand` | 32° / 42° / 30° | 22° / 18° / 14° |
| `fist` | 52° / 58° / 38° | 48° / 34° / 22° |

The fist is pitched at the deepest curl the rigid phalange plates can cover
without the joint gap opening: 78°/82°/58° left the left hand at 1.26 %, and
62°/68°/46° at 1.02 % per side. Closing that properly needs each plate extended
along its own bone rather than pushed further off the skin — raising the standoff
to 0.95 cm *made it worse* (1.24 %), because a standoff moves a plate away from
the skin without lengthening it, so the thicker silhouette simply steps off the
skin normal.

Fingers rotate about **their own** hinge (`rotate_hinge`, a bone-local X
rotation). `rotate_world` — one shared world axis for the whole list — is right
for limbs but wrong for a phalanx chain: every joint points a different way, so
a shared axis splayed the digits sideways instead of curling them, and the "fist"
preview showed an open hand.

### Why the hands do not shard

`SKM_Armor_Hands` exploded into long shards under the MetaHuman idle's curled
fingers. Cause: the finger plates were smooth-skinned, so a plate spanning
metacarpal + three phalanges was pulled by several bones at once and stretched.

* `Plate_Fingers` and `Plate_Gauntlet` are built with `hard=True` — **100 % weight
  on the single bone they belong to**, so a plate rotates rigidly about its own
  phalanx and cannot stretch.
* `only=HAND_BONES` filters every influence by name before collapsing, so a
  plate can only ever be influenced by the hand/finger bones it covers. No
  cross-finger blending, and no accidental grab of a wrist or forearm bone.
* The **glove undersuit** keeps smooth weights but is also restricted to
  `HAND_BONES` — it has to stay smooth, or the hand itself would break at the
  knuckles.
* Rigid segments have to overlap or the skin shows through between them, so the
  finger plate is deliberately thicker than the rest of the set (1.8 cm standoff,
  1 800-tri cap) and the glove got more budget. That is what moved the fist from
  1.30 % to 0.98 %.
* The same treatment is applied to the feet: `Plate_ToeCap`, `Plate_AnkleCuff`
  and `Plate_Boots` are `hard=True` with `only=FOOT_BONES`, since the boot is
  weighted to the toe bones and the idle also moves them.

`fist_side.png` shows the result: a compact curled hand, no shards.

Previews in `export/previews/` (Workbench, 768², material colour). **`front` is
the character's actual front** — all camera `y` offsets are multiplied by the
derived `F`, so the file names are trustworthy:

* `<pose>_front / _back / _side / _34top / _gameplay.png` for all six poses
  (`rest`, `arms_forward`, `deep_lunge`, `twist_aim`, `relaxed_hand`, `fist`);
  `gameplay` is the ~60° third-person camera.
* `helmet_on_front / _back / _side / _34top / _gameplay_head.png` and
  `helmet_off_...` — helmet against the MetaHuman face mesh, shoulder stub
  removed. The helmet uses its own `gameplay_head` angle: the body preset is
  ~60° above horizontal, which on a head crop looks down on the crown and hides
  the visor behind it.
* `uecam/<pose>_<view>_<arm>cm_{body,armor,BARE}.png` — the acceptance renders.
  `_body` and `_armor` are the two passes the bare-skin check diffs; `_BARE` is
  the mask (red = body silhouette with no armour behind it). Empty except for a
  few edge pixels.

## Helmet

Rebuilt as a panel-based hard-surface shell rather than a plain loft.

**Fit.** The shell is fitted to the actual face mesh rather than eyeballed.
Horizontal rays are fired from the head axis and the *first* hit is taken — the
head is scalp-over-hair-over-skull, so walking to the furthest hit reports the
skull and throws the hair volume away. Rays that leave the head entirely
(below the jaw, past the crown) get no hit and are filled from the ring median;
the vertex cloud then supplies the true radius per height, so the ears and jaw
cannot end up outside the shell. Clearance: 2.6 cm over the cranium, 1.9 cm over
the face, 1.5 cm at the jaw.

**Form.** The measured profile is blended toward a rounded-rectangle
cross-section (so it reads hard-surface, not egg-shaped), domed at the crown,
pinched at the chin, and finished with three flared **neck seal** rings sized
from the jaw rather than from the measured profile — down at that height the
horizontal rays hit the *shoulders*, which would flare the helmet into a skirt
the width of the upper body.

**Parts**, all derived from the same loft grid so they stay registered:

| Part | Placement |
|---|---|
| shell | loft, solidified 0.85 cm, bevelled, flat shaded, **closed at the crown** |
| visor | front arc only, ±60° (120° total), sitting inside the bezel, centred on `FRONT_ANG = -pi/2` |
| visor bezel | raised border standing proud of the visor, built as a **ring** (the visor cells are skipped) |
| cheek / jaw guards | angular plates on the lower sides |
| back-of-skull plate | rear panel |
| trim | thin cyan channels on the brow, crown, neck-seal and cheek seams |

**Three things that cost real time and are easy to repeat:**

* Every applied part must clear `SHELL_THICK`. The shell's outer surface is
  `loft + SHELL_THICK`, not `loft`, so a visor lifted 0.30 cm sits *inside* a
  0.85 cm shell and is completely invisible. All lifts are now expressed as
  `SHELL_THICK + delta`.
* The bezel has to be a **ring**. It is built from the same loft grid as the
  visor and sits further out (`FRAME_LIFT` > `VISOR_LIFT`), so drawing it as a
  filled patch put a solid panel directly in front of the visor and hid it
  completely — every preview showed a bright plate where the visor should be.
  `panel(..., skip=...)` omits the visor's grid cells.
* The shell is **not** planar-decimated. The crown cap and the last crown ring
  are nearly coplanar, and DISSOLVE merges them away — which is what left the
  open hole on the crown in the earlier build.

| Metric | Value |
|---|---:|
| Head points outside the shell's radial envelope (z > 1.52 m) | **0.00 %** of 3 939 |
| 6 cm-along-normal probe on the same points | 30.6 % |

The two numbers differ on purpose. The radial-envelope measure answers the
brief's question — does the shell enclose the head — and it is 0 %. The
along-normal probe under-reports badly on a head: the ear is a folded shell whose
vertex normals point sideways or downward, so the ray leaves the ear instead of
crossing the helmet. Both are written to `verify_report.json`.

## Known issues

* **The reported bare thigh does not reproduce in the export.** The composer's PIE
  capture shows one thigh bare hip-to-knee. Measured on these files, it is not
  present:
  * `SKM_Armor_Legs.fbx` raw bbox is x ∈ [−21.64, +21.67] cm — symmetric, 0
    unweighted vertices, both thighs present.
  * Per-side coverage in a real walk stride is **L 0.33 % / R 0.17 %**; in a wide
    stance **L 0.24 % / R 0.07 %**. The largest L/R split anywhere is 0.17 pp.
  * `near>3cm` is 0.00 % — no body point is > 3 cm from armour in any pose.
  * The bare-skin acceptance check, which renders body-only and armour-only
    passes and diffs the alpha, finds **0.0034 %** worst case over 27 renders at
    the exact stated camera and spring-arm range.

  There is no mirror or duplicate step for the second leg: both sides are built by
  the same `for sd in ("l", "r")` loop in `armor_set_a.py` from independent
  per-side predicates, so a mirroring bug is excluded by construction. If UE still
  shows it, the cause is on the import side — check that `SKM_Armor_Legs.fbx` was
  imported as **Skeletal** and bound to the *same* skeleton asset as the body
  mesh, and that no material section was dropped. A wrong skeleton assignment
  produces exactly this picture: bounds stay symmetric in rest while one limb
  fails to follow its bones.
* **Leg plates are not bone-locked.** Unlike the hands and feet, the
  thigh/tasset/knee/greave plates are smooth-weighted, so they stretch slightly
  under extreme poses. That is deliberate (a hard thigh plate would tear at the hip
  crease) but it is why `deep_lunge` reads higher than `legs_apart`.
* **Fist coverage is 0.88 % on the left side against a 1 % target.** The
  excess is skin poking between rigid phalange segments, not a hole (see the
  `near>3cm` column). Raising the finger plate's standoff does **not** close it
  and measured worse (0.95 cm → 1.24 %); closing it needs each plate extended
  along its own bone.
* **`build.ps1` scans both streams for failures.** Blender prints tracebacks on
  **stderr**, so a check that only inspected stdout reported a crashed stage as
  green — which is exactly what happened once. The combined text is scanned now,
  and both paths are covered by a standalone test (stderr-only traceback → guard
  fires; clean run → passes).
* **`POSES` entries must use a list of bone names.** A bare string
  `("thigh_l", 'X', -26)` iterates its *characters*, so `apply_pose` matches no
  bone and nothing moves — which looks exactly like "the pose applied and
  coverage is fine". Every pose silently became a rest pose this way during
  one round of diagnosis; the walk poses report their max mesh displacement
  in the log so a no-op pose is now obvious.
* **`front_sign()` only works on the body rig.** The helmet section re-imports the
  face FBX, whose armature has no `foot_*`/`ball_*` bones; re-deriving the facing
  there raised `ValueError: no foot/ball bones`. The helmet views reuse the value
  derived from the body.

* **The face FBX includes a shoulder / upper-chest stub.** It is not part of the
  helmet and, rendered, it reads as a wide flared skirt under the shell that
  makes the silhouette impossible to judge. Previews therefore render a
  head-only copy (`verify.head_only_copy`, everything below z = 1.50 m deleted),
  and the full mesh is hidden for every helmet render. Coverage is measured above
  z = 1.52 m.
* **Helmet is fitted to the bare head.** The MetaHuman hero is bald in this
  asset, so the shell hugs the skull with scalp margin rather than a hair volume.
* **Cheek guards and the back plate read subtly** in the Workbench previews —
  they are only 0.24 cm proud of the shell and the material contrast between
  `M_ArmorPrimary` and the shell is low. They are geometrically present.
* **Poke is 3.3–3.9 %** across poses. That is the underside of plates (armour
  ribs, boot soles, the pack) sitting close behind skin folds. It is reported for
  information; nothing gates on it.
* **`poke` uses `find_nearest`**, which is O(n) per query in Blender's wrapper —
  fine at this vertex count, slow if the body mesh is ever swapped for something
  denser.
* **Hands and feet are suit-dominated.** Their plates are capped hard to hit the
  slot budget, so the digits and boots read as low-detail. They are still fully
  covered; raising `SLOT_BUDGET` in `armor_set_a.py` is the only change needed.
* **Hand and foot undersuits must not be relaxed.** Laplacian relaxation on an
  open sheet contracts the boundary toward the limb axis; doing it on the suit
  pulled the coverage guarantee inward and took penetration from 0.00 % to 10.5 %.
  They are collapse-decimated only (`relax=0`).
* **`UnitScaleFactor` is only correct as a pair.** `FBX_SCALE_CUSTOM` is required
  to emit 1.0, and it only produces a unit node scale while the objects keep the
  0.01 scale the reference import gives them. Anything that normalises object
  transforms before export (or a future "clean up object scales" pass) silently
  reintroduces a 100× error. `verify.py` step 0 is the guard.
* **Materials are preview-only.** `M_*` base colours exist so the Workbench
  renders read; Unreal overrides them with its own instances.