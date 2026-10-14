# poly99 Blender asset pipeline

Reproducible Blender Python scripts that generate the stylized game
assets for **poly99+**, a top-down twin-stick shooter inspired by
Nex Machina (voxel enemies that shatter into cubes, neon-lit sci-fi
arena). All designs are original.

## Running

```powershell
cd unreal\blender\scripts
.\build_all.ps1
```

`build_all.ps1` runs every generator headless in order and fails on
the first error:

1. `arena_kit.py` — modular arena kit
2. `enemy_voxel.py` — voxel enemies + debris
3. `preview.py` — 512x512 PNG previews + `.blend` sources

Each script is idempotent: it starts from an empty scene (deletes
default objects and orphaned datablocks), so re-running always
produces the same output. Scripts use only `bpy` / `bmesh` /
`mathutils` — no add-ons.

Blender 5.2: `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`

## Conventions

| | |
|---|---|
| Units | 1 Blender unit = 1 m; sizes authored in cm via `common.cm()` |
| Scale | FBX vertex data is written in **centimeters** (`global_scale=100`), so UE 5.8 imports the authored centimeter sizes 1:1 |
| Axes | Blender **+X = front**, +Y = left, +Z = up. FBX export: `axis_forward="X"`, `axis_up="Z"` — a model built facing Blender +X faces **UE +X**, Z stays up |
| Pivots | Object origin at the **base center** (floor contact) for all props and enemies |
| Transforms | All transforms applied before export (`rotation`/`scale` baked) |
| Naming | Exported meshes `SM_<Name>`; materials `M_<Role>` |
| Materials | One simple Principled material per color role; emissive roles use a separate material with an emission shader. Every mesh also carries a flat vertex-color attribute named `Col`. UE replaces the materials anyway |
| Shading | Flat shading everywhere (`mesh_smooth_type='FACE'`) |

FBX export settings (see `common.export_fbx`):
`use_selection=True`, `apply_scale_options='FBX_SCALE_UNITS'`,
`mesh_smooth_type='FACE'`, `use_mesh_modifiers=True`,
`add_leaf_bones=False`, `axis_forward='X'`, `axis_up='Z'`,
`global_scale=100`.

**Why `global_scale=100`:** the scene is authored in meters, but
UE's FBX importer multiplies raw vertex data by
`UnitScaleFactor / 100`. With `apply_scale_options='FBX_SCALE_UNITS'`
on a meter scene, the exporter writes `UnitScaleFactor = 100` (i.e.
"file units are centimeters") while leaving the vertex data in meters —
so a 300 cm pillar imported into UE as 3 cm (100× too small; Blender's
own importer round-trips the file consistently, so a Blender-only
re-import check cannot see this). `global_scale=100` makes the exporter
write the vertex data in centimeters, matching the declared
`UnitScaleFactor`, so UE computes `cm × (100/100)` = the authored
size. Axis mapping and pivots are unaffected.

### Voxel JSON (`*_voxels.json`)

For UE shatter FX. Fields: `voxel_size_cm` (6.0),
`grid_origin_ue_cm` (grid origin in UE centimeters relative to the
mesh origin), and the list of filled voxels with `center_ue_cm`
(centers in UE axes: X forward, Y right, Z up) and `color_role` /
`material`.

## Produced files

```
unreal/blender/
├── scripts/
│   ├── common.py        # shared helpers (units, materials, FBX, measure)
│   ├── enemy_voxel.py   # voxel enemies + debris
│   ├── arena_kit.py     # modular arena kit
│   ├── preview.py       # PNG previews + .blend sources
│   ├── build_all.ps1    # runs everything headless
│   ├── measure.py       # verification: re-import FBX, print table
│   └── measure_ue.py    # raw-FBX scan: UnitScaleFactor + vertex data -> UE cm
├── export/
│   ├── SM_Enemy_Grasshopper.fbx + SM_Enemy_Grasshopper_voxels.json
│   ├── SM_Enemy_Wanderer.fbx    + SM_Enemy_Wanderer_voxels.json
│   ├── SM_VoxelDebris.fbx
│   ├── SM_Floor_Tile_400.fbx, SM_Wall_400.fbx, SM_Wall_Corner.fbx,
│   │   SM_Pillar.fbx, SM_Edge_GlowStrip.fbx, SM_Spawn_Gate.fbx
│   └── previews/<asset>.png      # 512x512, 3/4 top-down
└── source/<asset>.blend          # generating .blend per asset
```

## Verification

Two independent measurements, both headless:

1. **`measure_ue.py`** — reads each FBX's GlobalSettings
   `UnitScaleFactor` and raw vertex coordinates **directly from the
   file bytes** (no Blender importer round-trip, which would hide a
   scale mismatch), then reports the size **UE 5.8 will see**:
   `raw_dims × UnitScaleFactor / 100`. All files declare
   `UnitScaleFactor = 100` with centimeter-valued vertex data, so
   UE computes `cm × (100/100)` = authored size.
2. **`measure.py`** — re-imports each FBX into an empty Blender
   scene for triangle counts (the raw scan does not decode index
   buffers).

Triangle counts are well under the 5k limit; dimensions are
final UE sizes in centimeters.

| Asset | Tris | USF | UE size (cm) X × Y × Z |
|---|---|---|---|
| SM_Enemy_Grasshopper | 302 | 100 | 60.0 × 54.0 × 36.0 |
| SM_Enemy_Wanderer | 1680 | 100 | 78.0 × 78.0 × 60.0 |
| SM_VoxelDebris | 26 | 100 | 6.0 × 6.0 × 6.0 |
| SM_Floor_Tile_400 | 162 | 100 | 400.0 × 400.0 × 10.0 |
| SM_Wall_400 | 48 | 100 | 400.0 × 45.0 × 120.0 |
| SM_Wall_Corner | 36 | 100 | 424.0 × 424.5 × 124.0 |
| SM_Pillar | 36 | 100 | 80.0 × 80.0 × 300.0 |
| SM_Edge_GlowStrip | 12 | 100 | 400.0 × 6.0 × 2.0 |
| SM_Spawn_Gate | 54 | 100 | 300.0 × 48.0 × 260.0 |

Re-run the measurements with:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" `
  -b --factory-startup --python scripts\measure_ue.py
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" `
  -b --factory-startup --python scripts\measure.py
```

### Design notes

- **SM_Enemy_Grasshopper** — aggressive chaser drone built from a
  10×9×6 voxel occupancy grid (6 cm voxels). Teardrop plan (wide
  rear, pointed nose at +X), twin emissive eye voxels and a brow
  slit on the front face, rear antenna spikes. Crimson palette;
  emissive voxels use `M_VoxelEmissive`.
- **SM_Enemy_Wanderer** — bulky crawler: chunky hollow cube shell
  (78 cm across) around a 3×3×4 emissive core, four diagonal claw
  legs, crown spike with emissive tip. Amber palette.
- **SM_VoxelDebris** — single 6 cm cube, 0.4 cm bevel (26 tris),
  for Niagara mesh particles.
- **SM_Floor_Tile_400** — 400×400×10 cm panel: 16 raised inset
  tiles (94×94 cm) as seam geometry plus recessed emissive grid
  strips (`M_FloorGrid`).
- **SM_Wall_400** — 400 long (X), 120 tall, 40 thick: raised
  center panel, recessed inset, plinth, cap, glowing trim line
  (`M_WallTrim`) and emissive corner bolts.
- **SM_Wall_Corner** — corner piece for one 400 cm grid cell: two
  400-long arms running along -X and -Y from the corner column,
  trim lines continuing both directions. Bbox is 424 cm because
  the corner column (48 cm) extends past the arm ends.
- **SM_Pillar** — 80×80×300 cm with an inset dark core, flush
  base/capital, and emissive spines on the ±X faces.
- **SM_Edge_GlowStrip** — 400 cm glow line (`M_Glow`) on a dark
  base, for floor edges / hazard lines.
- **SM_Spawn_Gate** — enemy spawn portal frame, 300 cm wide ×
  260 tall: two posts, lintel, emissive inner portal plane
  (`M_Glow`), trim accents, base runners.

### Preview notes

Previews are EEVEE renders (512×512) from an elevated 3/4
front-right view with a key/fill/rim sun setup and a dark world
background, so the emissive roles read against the scene. The
generating `.blend` for each asset is saved to `source/` right
after its preview render.
