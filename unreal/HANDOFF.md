# poly99+ UE handoff (2026-10-13)

Read with `../unreal-agent-plan.md` (overall plan) and `../plan.md` (poly99 core/web plan).
Nothing in `unreal/` or the core changes is committed yet (`git status` shows them).

## Owner requirements (new, 2026-10-13)

1. **PIE input: gamepad only. Do not capture the mouse.**
   - Remove mouse-aim / LMB-fire from `APoly99PlayerController` (or put them behind an
     off-by-default flag); keep keyboard only if harmless, gamepad is the target.
   - PIE must not grab the cursor: `[/Script/UnrealEd.LevelEditorPlaySettings]`
     `GameGetsMouseControl=False` (Config/DefaultEditorPerProjectUserSettings.ini), and the
     controller must not set `bShowMouseCursor`/`FInputModeGameOnly` mouse capture.
   - Agents drive tests through `UPoly99Simulation::SetInputOverride` (no OS input needed).
2. **Performance target: 1440p @ 120 Hz** with **full hardware ray tracing**, **Nanite**,
   **MegaLights**; reaching it via **DLSS** (super resolution / frame gen as appropriate) and
   **dynamic resolution** is fine.
   - Current project settings are the opposite (my early 8 GB budget): `DefaultEngine.ini` has
     `r.DynamicGlobalIlluminationMethod=0` (Lumen off) and `r.ReflectionMethod=2`. Switch to
     Lumen with hardware RT (`r.RayTracing=True`, `r.Lumen.HardwareRayTracing=True`, GI=1,
     reflections=1), enable MegaLights (`r.MegaLights.EnableForProject=1`), Nanite on for
     environment meshes, Virtual Shadow Maps on, dynamic resolution + TSR/DLSS.
   - **DLSS plugin is not installed** (engine ships only NVIDIA Reflex + GeForce NOW plugins).
     The NVIDIA DLSS/Streamline UE 5.8 plugin must be obtained from NVIDIA (developer.nvidia.com
     or Fab) into `Poly99Game/Plugins/`; if that needs an account login, ask the owner.
   - Hardware here: RTX 3070 **Laptop**, 8 GB VRAM. 1440p120 with full HW RT + MegaLights will
     need DLSS Performance/Ultra Performance (+ frame generation is NOT available on 30-series:
     DLSS FG needs RTX 40+). Measure with `stat unit`/`stat gpu`/Insights and report honestly.
   - Other machines: see the `fleet` skill (D1 desktop may have a stronger GPU).

## Progress on owner requirements (2026-10-13, project thread)

- Gamepad-only: done + built. `APoly99PlayerController` maps only gamepad keys (L stick move,
  R stick aim + auto-fire, RT fire, LT/RB dash, Y helmet); no mouse aim/LMB; input mode
  GameAndUI with `DoNotLock`, cursor visible. `GameGetsMouseControl=False` in
  DefaultEditorPerProjectUserSettings.ini; DefaultInput.ini `bCaptureMouseOnLaunch=False`,
  `NoCapture`/`DoNotLock`. PIE-verified via `SetInputOverride` (moved +720 uu, fired +Y).
- Rendering: DefaultEngine.ini now Lumen GI+reflections with HWRT, `r.RayTracing`, MegaLights,
  Nanite, VSM, distance fields, TSR; `[SystemSettings]` dynamic res forced on (8.33 ms budget,
  50-100%). All cvars confirmed live in the editor (D3D12 SM6, RTX 3070 Laptop adapter).
- DLSS: installed. NVIDIA DLSS 4.5 UE plugin 8.8.0 (NGX 310.9.1), anonymous download from
  developer.nvidia.com (see `pipeline/research/dlss_ue58.md`); only `Plugins/DLSS` +
  `Plugins/StreamlineNGXCommon` copied (SR only, no FG/Reflex), module binaries rebuilt from source.
  `.uproject` enables DLSS; DefaultEngine.ini `r.NGX.DLSS.Enable=1`, `r.TemporalAA.Upscaler=1`,
  `r.Editor.Viewport.OverridePIEScreenPercentage=0`, `[/Script/DLSS.DLSSSettings]` PIE on.
  Verified: init supported on driver 617.42, all quality modes; DLSS-SR feature created in PIE.
  Open: whether to commit the plugin (large) or gitignore + install script — owner decision.
- Perf capture: NOT done. A standalone `-game` 1440p window pops over the owner's desktop
  (machine is in active use); run it only when the owner says the screen is free.
- Shared DDC (D1 Samba `\\192.168.1.2\UE-DDC`): verified in the editor log on 2026-10-13:
  `Shared: Using data cache path //192.168.1.2/UE-DDC: Writable`. `rebuild.sh` passes
  `-SharedDataCachePath=//192.168.1.2/UE-DDC` (forward slashes: bash double quotes had collapsed
  `\\` to `\` and UE saw `\192.168.1.2`). The machine env var is still malformed (needs admin).
- Distributed shader compiling (UBA -> Horde on D1): enabled in DefaultEngine.ini (`[Horde]
  ServerUrl` + `[UbaController] +Providers=Uba.Provider.Horde` + `[Uba.Provider.Horde]` Enabled,
  quoted ServerUrl (an unquoted `//` starts an ini comment), Pool=win-ue5-wine, AllowWine=True).
  Verified with a test material batch: 344/344 jobs completed, "only distributed compilation",
  peak 1 remote agent (D1-LINUX under Wine 8.0, 16 cores). The Windows D1 agent was offline.
  Caveats: blocking compiles (`recompileshaders global`, startup global shaders) stay local by
  engine design; the Wine agent warns `/dev/shm 64MB` -> disk-backed file mapping (slower; raise
  the agent container's shm to >= 1 GB on D1).
- DLSS + dynamic res crash (fixed): at 100% screen percentage the DLSS plugin selects DLAA, whose
  NGX feature cannot follow dynamic-res changes -> assert NGXD3D12RHI.cpp:431 kills the editor.
  `r.DynamicRes.MaxScreenPercentage=70` (50-70% = DLSS Performance..Quality). Do not raise to 100.
- DLSS standalone crash (fixed 2026-10-13): `-game` still crashed at frame 3 with the same assert.
  The dynres heuristic reports an upper bound of 1.0 until its first history resize, the plugin
  picks its mode from that upper bound -> DLAA -> next frame renders at 70% -> assert. An ini pin
  (`r.ScreenPercentage=67`) did NOT help. Fix is a 2-line patch in the project-local plugin:
  `Plugins/DLSS/Source/DLSS/Private/DLSSUpscaler.cpp` skips DLAA while `r.DynamicRes.OperationMode!=0`
  (search "poly99"). Any plugin reinstall/upgrade must re-apply it.
- Internal resolution, measured 2026-10-13 without a window (`UnrealEditor-Cmd.exe <uproject> -game
  -RenderOffscreen -windowed -ResX=2560 -ResY=1440 -csvCaptureFrames=2400 -ExitAfterCsvProfiling
  -ExecCmds="r.setres 2560x1440w,t.MaxFPS 0,r.VSync 0"`; editor closed; CSV lands in
  %LOCALAPPDATA%/UnrealEngine/5.8/Saved/Profiling/CSV): output 2560x1440, DLSS Quality preset,
  dynres pinned at its 50% floor = **1280x720 internal**, GPU 17.2 ms avg (p95 18.9) = ~56 fps vs
  the 8.33 ms budget; game thread 3.2 ms; VRAM 3.3 of 7.25 GB. Idle arena (no input). Without the
  `r.setres` exec cmd -RenderOffscreen ignores ResX/ResY and renders 888x500.
- Armor in UE: `Content/Python/poly99_pipeline/armor.py` (import with FbxFactory onto
  metahuman_base_skel, master M_HeroArmor + MI per role, DA_Hero_Default Armor/Helmet/HelmetOffset).
  Interchange bakes the helmet's head-rest node transform into the vertices, so HelmetOffset =
  inverse(head rest, component space). Helmet toggle verified in PIE (evidence/armor_helmet_on|off).
  Blocking armor issues sent back to the worker: Back piece on the front (MetaHuman faces +Y),
  undersuit gaps on upper arms, hand armor shards when fingers curl (evidence/armor_nobody.png).
  Blender FBX scale bug (100x small) fixed for armor and kit (both now verified in UE).
- Kit in UE: `poly99_pipeline/kit.py` -> /Game/Poly99/Kit (9 static meshes, Nanite on except
  debris, master M_Kit + MI per Blender slot; voxel slots use vertex colour). Re-imports reuse the
  asset's stored import data, so kit.py patches `vertex_color_import_option` before importing.
  `APoly99EntityRenderer` now draws SM_Enemy_Grasshopper / SM_Enemy_Wanderer.
- Arena: `poly99_pipeline/arena.py` dresses L_Arena (floor tiles, walls, pillars, glow strips,
  spawn gates, 20 neon point lights at 400 lm; moon 0.6 lux, sky 0.25). evidence/arena_kit_pie2.png.
  Hero-underlit fixed 2026-10-13: added 20 overhead spot "key" lights (4x5 grid on 480x640 UU,
  1500 lm, 1600 UU radius, 50/75 deg cones, colour 0.75/0.82/1.0) -> evidence/armor8_gameplay.png,
  armor9_fullbody.png. Open: MegaLights/Lumen grain; 20+20 lights may need a perf re-check.
- Armor facing FIXED and verified in UE 2026-10-13: SKM_Armor_Back bounds origin y=-17.7 (was
  +17.7). Facing proof for the whole pipeline: **the MetaHuman faces +Y in UE** - face mesh bounds
  centre y=+2.1 vs head bone socket y=+1.2, neck_01 y=-1.2. Do not re-derive; use face-vs-head.
  Hand plates no longer explode. Remaining defect sent back (round 3): **one thigh is bare skin
  hip-to-knee while the other is armored** (evidence/armor9_fullbody.png) - a left/right asymmetry,
  even though SKM_Armor_Legs bounds are symmetric, so the leg build/mirror is wrong. The worker's
  Blender coverage test (<1% gaps) does not predict UE: its poses have the legs together, UE plays
  the locomotion blend space. Its acceptance criterion is now "no visible skin in the top-down
  gameplay camera, 1280x960, spring arm 2.3-4.3 m".
- Armor thigh defect DIAGNOSIS CORRECTED 2026-10-13: it is **not a hole**. With the body hidden
  (evidence/armor12_armoronly.png) the thigh is a continuous undersuit; what looks like a bare
  thigh with the body on is SKIN-COLORED, so the MetaHuman body renders IN FRONT of the armour -
  the thigh undersuit is inside the skin. Ruled out by measurement: wrong skeleton (all 7 report
  `metahuman_base_skel`), dropped geometry (`pipeline/tools/fbx_loose_check.py`: Legs has 6278
  verts, 0 loose), inverted normals (`M_HeroArmor.two_sided=True` gives a pixel-identical render;
  flag restored to False). The worker's probe missed it because it measures DISTANCE
  (`near>3cm`) which cannot tell inside from outside; round 4 asks for SIGNED clearance.
- Live UE bone pose for the gameplay frame (deg, parent-bone space) is logged in the round-4 brief:
  thigh_r pitch +33 (the leg that shows skin), thigh_l pitch -16, clavicle_l yaw 101, upperarm_l
  yaw 64. Reproduce that pose as `ue_locomotion` in the Blender probe.
- Armor thigh PROVEN body-in-front on 2026-10-13: `armor15_nobodyonly.png` (body hidden only,
  same camera) has no skin patch - the dark undersuit is there. So the body occludes the armour;
  it is a clearance/pose problem, not a missing panel and not a material problem.
- Root cause of the worker's blind spot: it tests ONE static pose, but the hero is animated and
  the idle/locomotion blend swings thigh_r continuously. Round 5 replaces the single pose with a
  sweep (thigh pitch -20..+45 in 5 deg steps per leg, upperarm yaw 0..100, calf roll -30..30).
  Generalise this: a clearance that holds in sampled poses says nothing about the poses you did
  not sample.
- Worker fixes confirmed real bugs worth keeping: `extract_faces` clamped the 8.5 mm undersuit
  standoff to 0.3-4 mm on finely tessellated regions (`d = min(offset, offset_clamp*min_edge)`)
  - needs an `offset_floor`; 370 pelvis-owned faces were filed as "chest" so the leg shell stopped
  at z~92; `Plate_Tasset` was rigid and sank inside under pose. Also: units in that pipeline are
  CENTIMETRES, so an offset floor of 0.6 is 6 mm and 0.006 is 6 microns.
- Gotcha: runtime `SkeletalMeshComponent.set_visibility()` on the hero is unreliable for A/B
  isolation - `UPoly99HeroAppearance` re-applies visibility, so per-piece shots race with it.
  Isolate in the editor, not in PIE.
- Gotcha: `unreal.SystemLibrary.delay()` needs a `latent_info` arg; use bash `sleep` between
  `pie_py` calls and `HighResShot` instead, and expect ~4-6 s per capture.
- Python API gotchas hit on 2026-10-13: `SkeletalMeshComponent` has no `get_visible_flag` /
  `get_hidden_in_game` - read `get_editor_property("visible")` (and it DOES stick, so per-piece A/B
  isolation in PIE is reliable; the earlier failure was a different filter). `line_trace_single`
  returns None in 5.8 (out-param style) - it is unusable. Parent-bone space is
  `RelativeTransformSpace.RTS_PARENT_BONE_SPACE`; `Quat` has no `.pitch/.yaw/.roll` in Python,
  convert from x/y/z/w. `SystemLibrary.line_trace_single` arg order is
  world, start, end, trace_channel, trace_complex, actors_to_ignore, draw_debug, ignore_self.
- Tools: `pipeline/tools/fbx_loose_check.py <file.fbx>` finds vertices no polygon references
  (run with `python -I`). Writes no files.
- Blender workers re-delegated from this thread (kit: ling-3.1-flash, armor: space-bunny).

## Environment

- Engine `C:\Unreal\UE_5.8` (5.8.3), project `unreal/Poly99Game/Poly99Game.uproject` (C++,
  DX12 — the RHI once flipped itself to Vulkan after a MetaHuman restart; keep DX12).
- Blender 5.2 at `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`.
- MCP servers (Claude Code user scope; available natively in new sessions):
  - `unreal` → `http://localhost:8000/mcp` (Epic's experimental Unreal MCP; auto-starts with
    the editor; tool-search mode: `list_toolsets` / `describe_toolset` / `call_tool`).
    Project toolset `poly99_toolset.toolset.Poly99Toolset` adds `run_python` (full editor
    Python), `run_python_file`, `reload_module`.
  - `blender` → `blender-mcp` (Blender Lab v1.0.3). Headless bridge:
    `blender -b --online-mode --command blender_mcp` (port 9876).
- Scripted fallbacks in `unreal/pipeline/tools/` (Git Bash): `ue.py` (MCP client; saves
  images to `pipeline/evidence/captures/`), `pietest.sh` (`pie_start`, `pie_input`,
  `pie_shot`, `pie_py`, `pie_stop`), `rebuild.sh` (save → quit editor → UBT build → relaunch).
- MetaHuman cloud steps (auto-rig, textures) need the owner's Epic login (already done once,
  cached as user "pipyakas").

## Done

- Core (`core/`): dash, wanderer enemy, event buffer (+ tests; `cmake -S core -B build-core-only`).
- UE C++ (`Source/Poly99Game`, `Plugins/Poly99Core`): core bridge subsystem (`UPoly99Simulation`,
  `Get()`, `SetInputOverride`, events, dash), hero pawn (MetaHuman child actor, top-down camera,
  aim facing, locomotion blend space driver), appearance component (armor slots via leader pose,
  helmet socket + dissolve toggle, hides Hair/Beard/Mustache/Fuzz + Face under helmet), loadout
  data asset, Enhanced Input built in code, ISM entity renderer (placeholder meshes),
  `UPoly99EditorUtils` (`NotifyAssetChanged`, `BuildBlendSpace`).
- Content via scripts in `Content/Python/poly99_pipeline/`: `hero.py` (MetaHuman create, rig,
  textures, assemble → `/Game/Characters/Hero/Unpacked/MHC_Hero/BP_MHC_Hero`), `setup_game.py`
  (DA_Hero_Default, BP_Poly99Hero, BP_Poly99GameMode, L_Arena), `anim.py`
  (BS_Hero_Locomotion from MetaHuman UEFN locomotion anims).
- Verified in PIE (screenshots in `pipeline/evidence/`): hero spawns, runs/strafes/idles with
  animation, aims, fires; enemies chase.

## In flight (delegated from the previous thread; results land on disk)

- Blender voxel enemies + arena kit → `unreal/blender/` (scripts/, export/, README.md).
  FBXs already exported; previews/README pending.
- Armor set + helmet fitted to the hero → `unreal/blender/armor/` (scripts/, export/
  SKM_Armor_*.fbx, SM_Helmet_A.fbx, previews/, README.md with penetration table).
  Early previews show mostly undersuit with sparse plates — review critically.
- The previous thread will forward these workers' final reports here.

## Next steps

1. Apply the owner requirements above (gamepad-only PIE, rendering/perf settings, DLSS plugin).
2. Review + import Blender assets (`StaticMeshTools.import_file` / `SkeletalMeshTools.import_file`
   onto `metahuman_base_skel`), wire enemy meshes into `APoly99EntityRenderer`, build arena
   from the kit, armor + helmet into `DA_Hero_Default`, verify helmet toggle in PIE.
3. Give the hero hair (MetaHuman wardrobe) so the helmet-off state shows a full human head.
4. Voxel shatter FX (Niagara) from core `EnemyKilled` events + `*_voxels.json`.
5. HUD (UMG), dash verification test, performance capture at 1440p.

## Gotchas

- Don't `delete_asset` something referenced (e.g. BS_Hero_Locomotion) — it stalled the editor
  ~7 min; reuse/overwrite instead.
- A PostProcessVolume with manual exposure + physical camera exposure rendered everything black.
- `CaptureViewport` captures the editor world; use `HighResShot` in the PIE world for gameplay.
- Python can't reach world subsystems; use `unreal.Poly99Simulation.get(world)`.
- New UFUNCTIONs/UPROPERTYs need a full rebuild with the editor closed (`rebuild.sh`).
