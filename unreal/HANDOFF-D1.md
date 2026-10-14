# poly99+ on D1 — handoff (2026-10-14)

Authoritative history: `unreal/HANDOFF.md` (UE project + armor + DLSS findings).
This file only covers what changed when the work moved from L1 (Windows) to D1 (Linux).

## Where things are

| Thing | Path |
|---|---|
| Repo checkout | `/var/mnt/ssd1/poly99` (branch `main`, tracks `github.com/pipyakas/poly99`) |
| UE engine source | `/var/mnt/ssd2/UE_5.8` (tag `5.8.3-release`, commit `396c9f059`) |
| Blender 5.2.0 LTS | `~/bin/blender` → Flatpak `org.blender.Blender` |
| Shared DDC | `/var/mnt/hdd/UE-DDC` (locally; UE arg `-SharedDataCachePath=//192.168.1.2/UE-DDC` also works) |
| Evidence renders | `unreal/pipeline/evidence/` |

**L1 (`C:\UnrealProjects\poly99`) is retired for this project.** Everything is committed and pushed;
D1 is the working copy. Do not edit on L1.

## Repo state (committed and pushed, 2026-10-14)

- `0c53d46` core dash/wanderer events + `unreal-agent-plan.md` + `unreal/HANDOFF.md`
- `210333e` UE 5.8 project: `Poly99Game` module, `Poly99Core` plugin, Content, DLSS plugin **source**
- `c3434e4` Blender armor pipeline + Blender kit/enemy scripts + Linux pipeline tools
- 6 earlier commits (`57d8799`..`082f402`) were made by the armor worker under the owner's identity
  without being asked. Kept as-is; do not rewrite.

### LFS and gitignore (new, important)

- `*.uasset` / `*.umap` are **Git LFS** pointers (89 files, 205 MB, incl. 114 MB `MHC_Hero.uasset`).
  A plain `git clone` **without git-lfs installed** gives you pointer files, not assets.
- `git-lfs` 3.7.1 is installed at `/usr/local/bin/git-lfs` on D1. `git lfs install` already ran
  in the repo. If content looks wrong after any checkout: `git lfs pull`.
- `unreal/Poly99Game/{Intermediate,Binaries,Saved,DerivedDataCache}/` and
  `Plugins/*/{Binaries,Intermediate}/` are gitignored. The DLSS plugin **binaries are local-only**
  on L1 and were never pushed; D1 has the source only. See
  `unreal/Poly99Game/Plugins/INSTALL-DLSS.md`. **DLSS is Windows-only — do not install it on D1.**
- `__pycache__/` and `*.pyc` are gitignored.

## Toolchain already installed on D1 (all user-space, no rpm-ostree layering, no reboot)

| Tool | Version | Location |
|---|---|---|
| `gh` | 2.102.0 | `~/.local/bin/gh`, authenticated as Pipyakas with **Epic UnrealEngine repo access** |
| dotnet SDK | 8.0.426 | `~/.dotnet` (UE 5.8 UBT is pure .NET 8; mono/msbuild not needed) |
| clang/lld | 20.1.8 | `/var/mnt/ssd2/llvm-dl/LLVM-20.1.8-Linux-X64`, symlinked into `~/.local/bin` |
| cmake | 4.4.4 | `~/.local/opt/cmake` |
| UE cross-toolchain | `v26_clang-20.1.8-rockylinux8` | `Engine/Extras/ThirdPartyNotUE/SDKs/HostLinux/Linux_x64/` |
| git-lfs | 3.7.1 | `/usr/local/bin` |
| Blender | 5.2.0 LTS | Flatpak |

Engine `Setup.sh` succeeded (31.1 GB gitdeps) and `GenerateProjectFiles.sh -engine` succeeded.
Engine tree is 126 GB; ssd2 had 594 GB free after that.

## Immediate next step: build the editor

```bash
cd /var/mnt/ssd2/UE_5.8
./Engine/Build/BatchFiles/Linux/Build.sh UEEditor Linux Development -waitmutex -MaxParallelActions=10
```

`-MaxParallelActions=10` because 32 GB RAM binds before 16 threads do (~2.5–3 GB per compile action).
Expect 2–4 h on 8c/16t. `CCACHE_DIR=/var/mnt/ssd2/.ccache` if you want rebuilds cached.

Then build the project against it with `unreal/pipeline/tools/rebuild-linux.sh`
(builds `Poly99GameEditor Linux Development`, prints the manual launch command).

## Linux tooling notes

- Renderer is **Vulkan** on D1, not DX12. Keep DX12 on L1 if that checkout is ever needed again.
- NVIDIA DLSS plugin: Windows-only, absent on D1. Do not try to enable it in the Linux build.
  `r.NGX.DLSS.Enable=1` and `[/Script/DLSS.DLSSSettings]` in `DefaultEngine.ini` are inert on Linux;
  TSR is the Linux default upscaler.
- The DLAA/dynres patch (`DLSSUpscaler.cpp`, search `poly99`) is preserved in the pushed source tree
  and documented in `INSTALL-DLSS.md`, so an L1 reinstall can re-apply it.
- Horde distributed shader compile was configured for a Wine agent on D1; on D1's native Linux build
  it is unnecessary. `BuildConfiguration.xml` on L1 pointed at `http://192.168.1.2:5000`.
- Blender Flatpak gotchas: `flatpak install` as the user fails (polkit), use `sudo`.
  Config lives under `~/.var/app/org.blender.Blender/`, **not** `~/.config/blender`.
  The sandbox has full host filesystem access, so `blender-mcp` can reach `/var/mnt/ssd1/poly99`
  without `--filesystem` overrides. Bundled python is 3.13.13; user site-packages are writable via `--user`.

## Helper scripts

Linux versions (new, committed):

- `unreal/pipeline/tools/rebuild-linux.sh` — build `Poly99GameEditor` Linux Development; prints launch command
- `unreal/pipeline/tools/pietest-linux.sh` — source it; `pie_start/pie_input/pie_py/pie_shot/pie_stop`,
  drives PIE through the Unreal MCP endpoint at `http://localhost:8000/mcp` (same as L1).
  Falls back to launching `UnrealEditor` directly if MCP is unreachable. Uses `python3 -I`.
- `unreal/pipeline/tools/ue-linux.py` — MCP client (tools/describe/call/py), saves captures to
  `unreal/pipeline/evidence/captures/`

Assumptions baked into those scripts, to correct if the engine lands elsewhere:
UE root `/var/mnt/ssd2/UE_5.8`, project `/var/mnt/ssd1/poly99/unreal/Poly99Game/Poly99Game.uproject`.

Windows originals (`rebuild.sh`, `pietest.sh`, `ue.py`) are still committed for reference.

**Security rule for agents:** `python3 -I` for any Python that reads untrusted data (downloaded files,
extracted archives). Keep scripts out of data directories; pass paths as arguments.

## T3 Code on D1

- **Project registered** on D1's t3code (`~/.local/bin/t3`, service `t3 serve` on 0.0.0.0:3773):
  `t3 project add /var/mnt/ssd1/poly99 --title poly99`
  - project id `cd59bf42-5269-418c-b69f-5c92c9f58953`, workspace `/var/mnt/ssd1/poly99`,
    verified in `~/.t3/userdata/state.sqlite` (`projection_projects`).
- **No thread on D1 yet.** Create the first one from the T3 app on D1 (open the `poly99` project).
  Do not launch it from L1: this session's `t3_thread_launch` targets **L1's** t3code instance, so a
  thread launched here would be bound to `C:\UnrealProjects\poly99`, not the D1 checkout.
- L1's `poly99` project (`mcp:ce417856-...`) is retired. Leave it; it is harmless once L1's own
  checkout is deleted.
- When D1's editor runs, add the `unreal` MCP server (Epic's experimental UE MCP, project toolset
  `poly99_toolset.toolset.Poly99Toolset`) and `blender-mcp` (port 9876) to D1's Claude Code user
  config. Neither is configured on D1 today (`claude mcp list` is empty there).
- D1's T3 API needs a Clerk DPoP session, so bearer tokens from `t3 auth session issue` are **not**
  accepted by `/mcp` or `/api/*`. Don't spend time on remote HTTP calls to D1's t3code; drive it
  through the app or the CLI instead.

## First thread brief for D1

Suggested title: `poly99 on D1 — build UE Linux editor`. Message to start it:

> Read `unreal/HANDOFF-D1.md` first, then `unreal/HANDOFF.md`. This checkout is
> `/var/mnt/ssd1/poly99` on D1 (Bazzite, AMD RX 6700 XT is the main GPU; the RTX 2060 is secondary).
> Engine source is already at `/var/mnt/ssd2/UE_5.8` (5.8.3-release, Setup.sh + project files done,
> editor NOT yet compiled). Start with:
> 1. Build the editor:
>    `cd /var/mnt/ssd2/UE_5.8 && ./Engine/Build/BatchFiles/Linux/Build.sh UEEditor Linux Development -waitmutex -MaxParallelActions=10`
> 2. Build the project: `bash /var/mnt/ssd1/poly99/unreal/pipeline/tools/rebuild-linux.sh`
> 3. Launch and verify under Vulkan on the RX 6700 XT. DLSS does not exist on Linux; TSR is the
>    upscaler. Report honestly which of Lumen, MegaLights, hardware RT, Nanite and VSM actually work.
> 4. Measure GPU time at 2560x1440 using the headless CSV method in HANDOFF.md and report real numbers.
> Owner rules: PIE is gamepad-only and must not capture the mouse; drive tests through
> `UPoly99Simulation::SetInputOverride`; no full-desktop screenshots; verify worker results yourself;
> never grade yourself; no Claude/Anthropic commit trailers; do not commit unless asked.

## Open work items carried over

1. Build the editor on D1 (command above), then build `Poly99GameEditor` and get the project to launch.
2. Verify the project opens and PIE works on Vulkan/AMD. Report honestly on Lumen, MegaLights,
   hardware ray tracing and Nanite support under Vulkan on the RX 6700 XT.
3. Consider XeSS / FSR for AMD on Linux. DLSS is unavailable. TSR is the safe default. Verify claims
   about plugin availability before enabling anything (this was never researched — the research slice
   was cancelled on owner instruction).
4. Armor: the thigh defect (body occluding armour during the locomotion blend) is still open. The
   worker's provenance-weight theory was never implemented. The provenance idea, the 64-frame sweep
   and its failure numbers are in `unreal/blender/armor/README.md` and `unreal/HANDOFF.md`.
5. Hero hair (MetaHuman wardrobe) so helmet-off shows a full head — still open from the Windows run.
6. Perf target: the owner's 1440p@120 Hz goal is unrealistic on D1's RTX 2060 (PCIe 3.0 x4) and
   questionable on the RX 6700 XT for a Lumen+MegaLights scene. Measure and report real numbers
   before promising anything.

## Perf numbers from L1 (RTX 3070 Laptop, DX12, DLSS Quality, idle arena)

- Output 2560x1440, dynamic res pinned at its 50% floor → 1280x720 internal.
- GPU 17.2 ms average (p95 18.9) ≈ 56 fps against an 8.33 ms budget. Game thread 3.2 ms.
  VRAM 3.3 of 7.25 GB. No per-pass GPU breakdown captured.