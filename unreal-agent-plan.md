# poly99+ (UE 5.8) — Agent-only Blender → Unreal pipeline

Companion to `plan.md` (roadmap phases 5–6). Re-scopes the UE5 frontend as a
**Nex Machina–inspired** top-down voxel shooter with a customizable, armored
MetaHuman hero (helmet toggle shows a real human face), built end-to-end by
agents driving Blender and Unreal through MCP. Status: **plan only — nothing
installed or configured yet.**

Original names and assets only: "inspired by" Nex Machina, no ripped content,
names, or audio.

---

## 1. Verified toolchain (this machine, 2026-10-13)

| Piece | Found | Notes |
|---|---|---|
| Unreal Engine | 5.8.3 at `C:\Unreal\UE_5.8` | Launcher build |
| Unreal MCP | `Engine/Plugins/Experimental/ModelContextProtocol` | Epic's MCP server. HTTP, default `http://localhost:8000/mcp`; settings `ServerPortNumber`, `ServerUrlPath`, `bAutoStartServer` (default **false**), `bEnableToolSearch` |
| UE agent toolsets | `Experimental/Toolsets/*` | EditorToolset (BP/actors/properties), **MetaHumanGenerator**, **ChaosClothAssetToolset**, NiagaraToolsets, UMGToolSet, PCGToolset, GASToolsets, LiveCodingToolset, AutomationTestToolset, PhysicsToolsets, SlateInspectorToolset, MCPClientToolset, `AllToolsets` aggregator. Toolsets are Python (`unreal.ToolsetDefinition` + `@toolset_registry.tool_call`) → we can add our own |
| MetaHuman | `Plugins/MetaHuman/*` | MetaHumanCharacter (in-editor Creator), SDK, Crowd, Animator; `Experimental/MetaHuman/MetaHumanRuntime`, `MetaHumanCharacterUAF` |
| MetaHuman Generator tools | `metahuman_toolset/metahuman.py` | `create(asset_path)`, `begin_edit/end_edit`, `get/set_body_shape`, `get/set_skin_tone`, `get/set_eye_color` (+ C++ `ResetNeckToBody`, `IsOptionalContentInstalled`) |
| Mutable | `Plugins/Mutable` + MutableClothing/Population | Option for runtime customization (see §5) |
| Python in editor | PythonScriptPlugin | Fallback for anything no toolset covers |
| Blender | 5.2 | No MCP extension installed yet |
| Blender MCP | Official Blender Lab server v1.0.3 (extension + `uv`-launched server over TCP) | 26 tools incl. Python exec, screenshots, docs search, headless `*_for_cli` tools. Executes LLM code unguarded |
| C++ toolchain | Visual Studio Community 2026 (18.10) with VC x64 tools | Needed for C++ game module + Live Coding |
| GPU | RTX 3070 Laptop, 8 GB | Tight for editor + MetaHuman; budget below |
| uv / Python / Node | 0.12.5 / 3.14 / 24 | |

---

## 2. Architecture

```
Composer (Claude Code)
 ├── MCP: unreal  → http://localhost:8000/mcp     (running UnrealEditor, Poly99Game.uproject)
 ├── MCP: blender → uv-launched Blender Lab server → Blender 5.2 (TCP)
 ├── Shell: UnrealBuildTool / UnrealEditor-Cmd (headless builds, commandlets, automation tests)
 └── T3 delegated workers (bounded slices: Blender asset scripts, C++ classes, core tests, audits)
```

**Gameplay authority stays in `core/`.** Nex Machina is a top-down game on a
plane, so the core's 2D simulation maps directly: core `(x, y)` → UE `(X, Y)`
on the arena floor. UE renders, animates, and adds feel (camera, FX, audio).
The web/raylib build keeps working off the same core.

**Asset hand-off contract (Blender → UE):** every asset is produced by a
*checked-in Python script* (not ad-hoc MCP calls), so it is reproducible and
reviewable:

```
unreal/
  Poly99Game/                       # C++ UE project
    Poly99Game.uproject
    Config/DefaultEngine.ini        # MCP autostart, plugin settings
    Source/Poly99Game/...           # game module
    Plugins/Poly99Core/             # wraps ../../core as UE module
    Plugins/Poly99Toolset/          # our custom MCP toolset (Python)
  blender/
    scripts/<asset>.py              # generates the .blend + exports FBX
    export/<asset>.fbx              # build artifacts (gitignored or LFS)
  pipeline/
    import_assets.py                # UE-side import (Interchange) of blender/export
    verify/*.py                     # screenshot + automation checks
```

---

## 3. One-time setup (needs owner approval before running)

1. **Blender MCP:** install the Blender Lab extension from extensions.blender.org,
   enable it, start its listener; register the server in Claude Code
   (`claude mcp add blender -- uvx …` per blender.org/lab/mcp-server docs).
2. **UE project:** create `unreal/Poly99Game` as a C++ project (blank template)
   with UnrealEditor-Cmd / UBT. Enable: `ModelContextProtocol`, `AllToolsets`
   (or the specific ones above), `MetaHumanCharacter`, `MetaHumanSDK`,
   `PythonScriptPlugin`, `Niagara`, `EnhancedInput`, `ChaosClothAsset`,
   `GeometryCollectionPlugin`, `Interchange`.
3. `Config/DefaultEngine.ini` (section name taken from the settings class on
   first run): `bAutoStartServer=True`, `ServerPortNumber=8000`.
4. Register UE: `claude mcp add --transport http unreal http://localhost:8000/mcp`.
5. Smoke test: list tools from both servers; spawn a cube in each; take a
   viewport screenshot from each.
6. Check `IsOptionalContentInstalled()` and whether MetaHuman assembly /
   texture synthesis needs an Epic account login (cloud service). If it does,
   that is the **only expected human step**: log in once.

---

## 4. Vertical slice (milestone 1) — scope & acceptance

One arena, armored MetaHuman hero with helmet toggle, twin-stick move/shoot/dash,
2 enemy types, voxel death FX, HUD with score/lives/multiplier.

| # | Workstream | Agent output | Acceptance (verified by agent, evidence saved) |
|---|---|---|---|
| S0 | Setup (§3) | Project + MCP wired | Both servers answer `tools/list`; PIE launches |
| S1 | Core bridge | `Plugins/Poly99Core` compiles `core/*.cpp` as a UE module; `UPoly99Simulation` (GameInstanceSubsystem) ticks core | Core unit tests still pass in CMake; UE automation test ticks 600 frames with no crash, entity count > 0 |
| S2 | Core additions | `dash` in `Poly99Input` + i-frames; second enemy type; death **events** buffer (pos, type) for FX | New `core_tests` cases; web build still builds |
| S3 | MetaHuman hero | `/Game/Characters/Hero/MHC_Hero` via MetaHuman Generator (body shape, skin, eyes); assembled for UE with LOD budget | Asset exists; skeletal mesh renders in a screenshot; head + body share MetaHuman body skeleton |
| S4 | Armor (Blender) | `blender/scripts/armor_set_a.py`: imports MH body FBX as reference, models hard-surface pieces (cuirass, pauldrons, vambraces, gauntlets, tassets, greaves, boots, backpack), skins via Data Transfer weights from the MH body, exports FBX on the MH skeleton | Imports into UE onto the MH skeleton with no bone warnings; no visible body poke-through in 4 test poses (idle, run, aim, dash) — screenshots |
| S5 | Helmet (Blender) | `helmet_a.py`: rigid helmet + visor, single bone weight on `head` | Fits over head with hair hidden; no face clipping at max jaw-open pose |
| S6 | Appearance system (C++) | `UHeroAppearanceComponent` + `UHeroLoadout` data asset (see §5) | Toggling helmet in PIE flips helmet/hair/face state; screenshots both states |
| S7 | Pawn + controls | `APoly99HeroPawn` mirrors core player entity; Enhanced Input twin-stick (KB+M and gamepad), dash, `H` = helmet toggle; top-down camera rig | PIE automation: input sequence moves hero; aim rotates upper body |
| S8 | Enemies + voxel FX | Blender voxel-style enemy meshes (script: block-remesh + palette material); ISM rendering of core enemies; death → Niagara cube-burst (mesh particles) driven by core death events | 200 enemies on screen ≥ 60 fps at 1080p on this GPU (stat unit capture) |
| S9 | Arena | Blender modular floor/wall kit (script) + UE level assembled via Python; neon/emissive post-process | Level loads; screenshot |
| S10 | HUD | UMG via UMGToolSet: score, lives, multiplier, wave | Values match core snapshot in automation test |

Animation: start from MetaHuman/UE mannequin retargeted locomotion (Manny →
MetaHuman via IK Retargeter, scriptable), aim-offset upper body. Custom anims
are out of scope for milestone 1.

---

## 5. Customization & helmet design

- **Face/body:** several prebuilt MetaHuman presets made by agents (MetaHuman
  Generator) selectable in a loadout menu. Runtime face sculpting is not a goal
  for milestone 1. `MetaHumanRuntime` / Mutable to be evaluated later for
  runtime mixing.
- **Armor:** modular slots (`Chest`, `Shoulders`, `Arms`, `Hands`, `Legs`,
  `Feet`, `Back`, `Helmet`) as skeletal mesh components following the body
  (leader pose / `SetLeaderPoseComponent`). Variants per slot; tint via
  material instance params (primary, secondary, emissive trim, wear).
- **Under-armor body:** full armor hides almost all skin, so body sections
  under armor are masked (material opacity mask or hidden sections) to stop
  clipping and save shading cost. Only head/neck render.
- **Helmet toggle** (`UHeroAppearanceComponent::SetHelmet(bool)`):
  - On: helmet + visor visible; hair/eyebrow/beard grooms or cards hidden;
    face mesh at low LOD or hidden behind an opaque visor.
  - Off: helmet hidden; face + hair visible; optional camera "portrait" moment
    for cutscenes/menu.
  - Blend: 0.25 s visor retract / helmet dissolve (material param), not a pop.
- `UHeroLoadout` (Primary Data Asset): MetaHuman preset, armor variant per
  slot, colors, helmet default. Saved to SaveGame.

---

## 6. Performance budget (RTX 3070 Laptop, 8 GB)

- Camera is top-down and far: hero uses MetaHuman LOD 2–3 in gameplay, LOD 0
  only in loadout/portrait view. Hair cards, not strands, in gameplay.
- Enemies: Instanced Static Meshes (no actor per enemy). Voxel debris: Niagara
  mesh particles with GPU sim, capped pool.
- Environment: Nanite meshes; Lumen off or "Low" in gameplay, baked/simple
  lighting acceptable; bloom/emissive carries the look.
- Editor runs at the same time as Blender: close Blender between asset passes
  if VRAM is short.

---

## 7. Agent workflow

- **Composer** owns design, integration, the MCP-connected editor sessions and
  final verification. Only one agent drives a given running editor at a time
  (the UE and Blender MCP sessions are stateful and single-user).
- **Delegated slices** (T3 workers, file-scoped, no live MCP):
  core changes + tests (S2), C++ classes from a spec (S6, S7), Blender asset
  *scripts* run headless (`blender -b -P script.py`) (S4, S5, S8, S9), UE Python
  import/verify scripts. The composer then runs them through MCP.
- **Verification loop per step:** run → screenshot (Blender MCP screenshot /
  UE viewport capture) → automation test or log scan → artifact saved under
  `unreal/pipeline/evidence/<step>/`. A step is done only with evidence.
- **Custom toolset** `Plugins/Poly99Toolset` (Python) exposes high-level tools
  so agents don't hand-write editor Python every time:
  `import_blender_asset(fbx, target_skeleton)`, `set_loadout(...)`,
  `toggle_helmet_preview(bool)`, `capture_pose_screenshots(poses)`,
  `run_pie_for(seconds, input_script)`.

---

## 8. Risks / open questions

| Risk | Mitigation |
|---|---|
| Unreal MCP + toolsets are **Experimental** in 5.8 — tools may be incomplete or change | Fall back to PythonScriptPlugin via a custom toolset; pin engine version |
| MetaHuman assembly/texture synthesis may require Epic cloud login | One-time human login; otherwise use the presets that ship with the plugin |
| MetaHuman licensing: MetaHumans are licensed for Unreal Engine use | Fine for a UE build; don't export MetaHuman meshes to the raylib/web build |
| Armor skinning quality (shoulders/hips deform badly) | Rigid sub-pieces bone-parented where possible; weight transfer only for flexible parts; pose-screenshot checks in S4 |
| Agent-made art quality (hard-surface modeling via code) | Keep a stylized voxel/hard-surface look that procedural scripts do well; iterate with screenshots |
| 8 GB VRAM | §6 budget; LODs; close Blender during PIE |
| Core is 2D, hero is 3D (aim, upper-body twist, dash) | UE-side presentation only; core stays authoritative for positions/collisions |
| Two MCP sessions in one composer = large context | Custom high-level toolset; keep raw tool search on (`bEnableToolSearch`) |

---

## 9. Next actions (when approved)

1. Run §3 setup and smoke tests.
2. S1 + S2 (core bridge and additions) in parallel with S3 (MetaHuman hero).
3. S4/S5 armor + helmet → S6 appearance system → S7 pawn.
4. S8–S10, then performance capture and vertical-slice review.
