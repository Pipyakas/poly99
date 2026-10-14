# NVIDIA DLSS for Unreal Engine 5.8 — research findings

Research date: 2026-10-13. Target: `<Project>/Plugins/`, DLSS **Super Resolution only** (no frame
generation), target GPU RTX 3070 Laptop.

**Evidence markers used below**
- **[HTTP]** — verified by an actual HTTP request from this machine (curl); status/final URL recorded.
- **[ZIP]** — read directly out of the real 8.8.0 UE 5.8 zip via HTTP range requests (no full download);
  source file / descriptor quoted verbatim.
- **[DOC]** — statement from NVIDIA's public documentation page (quoted).
- **[LOCAL]** — verified against files already on this machine (installed UE, registry).

---

## 0. Local environment (relevant context for the composer) — [LOCAL]

| Fact | Value | How verified |
|---|---|---|
| Engine installed | **UE 5.8.3** at `C:\Unreal\UE_5.8` | `C:\ProgramData\Epic\UnrealEngineLauncher\LauncherInstalled.dat` → `"AppVersion": "5.8.3-58210709+++UE5+Release-5.8-Windows"` |
| Engine ships a DLSS/Streamline plugin? | **No** | Recursive `*.uplugin` scan of `C:\Unreal\UE_5.8\Engine\Plugins` found no DLSS / Streamline / DLSSG plugin |
| Engine ships a Reflex plugin? | **Yes** — `C:\Unreal\UE_5.8\Engine\Plugins\Runtime\Nvidia\Reflex\Reflex.uplugin` | idem |
| That Reflex plugin's defaults | `"EnabledByDefault": false`, module `Reflex`, `Type: ClientOnly`, `VersionName: "1.6"`, `PlatformAllowList: [Win64]` | `Reflex.uplugin` |
| Stale registry key (ignore) | `HKLM\SOFTWARE\EpicGames\Unreal Engine\5.7` → `C:\dev\UE_5.7`, **directory does not exist** | `reg query` + directory listing |

**Consequence:** the NVIDIA plugin zip is the *only* source of DLSS/Streamline for this engine. The
built-in `Reflex` plugin is off by default, so it will not fight the NVIDIA plugins unless someone
explicitly enables it.

---

## 1. Official sources and exact download URLs

### 1.1 Canonical page — [HTTP]

`https://developer.nvidia.com/rtx/dlss/get-started` **301-redirects** to
`https://developer.nvidia.com/rtx/dlss` (final `HTTP/1.1 200 OK`, 35 976 bytes).

That page's "DLSS 4.5 Plugin for Unreal Engine" section offers **four** engine-specific builds —
**[DOC]** quoted verbatim from the page HTML:

> "DLSS 4.5 is in Unreal Engine through our official DLSS Unreal Engine plugin. The plugin provides
> access to Multi Frame Generation, Dynamic Multi Frame Generation, Ray Reconstruction, Super
> Resolution, DLAA, Reflex Low Latency, and NVIDIA Image Scaling."
>
> "*Last Updated: September 2026 (DLSS 4.5 Plugin Package contains SL 2.14.1 / NGX 310.9.1)*"

So the current branding is **DLSS 4.5** (not "DLSS 4"), plugin package version **8.8.0**, containing
**Streamline 2.14.1** and **NGX 310.9.1**.

### 1.2 Exact direct download URLs — [HTTP] (links extracted from the live page, then HEAD-tested)

| UE version | Direct URL |
|---|---|
| **5.8 (use this)** | `https://developer.nvidia.com/downloads/assets/gameworks/downloads/secure/dlss/ue-dlss-5.8/8.8.0/2026.09.15_ue5.8_dlss4.5plugin_v8.8.0.zip` |
| 5.7 | `https://developer.nvidia.com/downloads/assets/gameworks/downloads/secure/dlss/ue-dlss-5.7/8.8.0/2026.09.15_ue5.7_dlss4.5plugin_v8.8.0.zip` |
| 5.6 | `https://developer.nvidia.com/downloads/assets/gameworks/downloads/secure/dlss/ue-dlss-5.6/8.8.0/2026.09.15_ue5.6_dlss4.5plugin_v8.8.0.zip` |
| 5.5 | `https://developer.nvidia.com/downloads/assets/gameworks/downloads/secure/dlss/ue-dlss-5.5/8.8.0/2026.09.15_ue5.5_dlss4.5plugin_v8.8.0.zip` |

Pattern: `.../secure/dlss/ue-dlss-<VER>/8.8.0/2026.09.15_ue<VER>_dlss4.5plugin_v8.8.0.zip`

**Past versions:** `https://forums.developer.nvidia.com/t/nvidia-dlss-unreal-engine-plugin-archive/377564`
— [DOC] linked from the page as "NVIDIA DLSS: Unreal Engine Plugin Archive".

### 1.3 Fab / Unreal Marketplace — **NOT verifiable from here**

The `.uplugin` descriptors all carry `"MarketplaceURL": "https://www.unrealengine.com/marketplace/en-US/product/nvidia-dlss"`.
Both `https://www.fab.com/search?q=NVIDIA%20DLSS` and that Marketplace URL returned
**HTTP 403 behind a Cloudflare JS challenge** from this machine — **[HTTP, failed]**. So: the Fab
listing exists but I could not confirm which engine versions Fab currently ships. **Do not use Fab as
the 5.8 source** — the direct zip above is verified and is one build per engine version, exactly what
you need.

### 1.4 Streamline SDK (separate, not needed for this task)

`https://github.com/NVIDIA-RTX/Streamline` — [HTTP] `api.github.com` reports latest release
**v2.14.1 "Streamline SDK 2.14.1"**, published **2026-09-08** — matching the SL 2.14.1 bundled in the
UE plugin. Its README [DOC]: *"As of SL 2.7.32, binary artifacts ... are not in the GitHub
repository"*, so **GitHub is not a source of the UE plugin binaries** — only the SL SDK DLLs.

---

## 2. Auth: does the download need an NVIDIA developer account?

**No login required.** **[HTTP]** — two independent anonymous requests, no cookies, no auth header:

**(a) HEAD request**

```
$ curl -sI -L "<ue-5.8 url>"
HTTP/1.1 302 Moved Temporarily
Location: https://developer.download.nvidia.com/assets/gameworks/downloads/secure/dlss/UE-DLSS-5.8/8.8.0/2026.09.15_UE5.8_DLSS4.5Plugin_v8.8.0.zip?__token__=exp=1791872186~hmac=71ebd5f8...
    ↓ follow
HTTP/1.1 200 OK
Content-Type: application/zip
Content-Length: 848527275
```

**(b) Ranged GET (first 1 KiB only — full file NOT downloaded)**

```
$ curl -sL -r 0-1023 -o head.bin -w "http=%{http_code} size=%{size_download} type=%{content_type}\n" "<ue-5.8 url>"
http=206 size=1024 type=application/zip
$ od -A d -t x1 -N 32 head.bin
0000000 50 4b 03 04 14 00 08 00 08 00 50 7b 2f 5d 00 00   <-- PK\x03\x04 = real ZIP local file header
```

**Findings:**
- `https://developer.nvidia.com/downloads/...` is a plain 302 to `developer.download.nvidia.com` with a
  short-lived HMAC `__token__` (the `exp=` value is a unix timestamp; no session cookie, no user id).
  `-L` handles the redirect, so the developer.nvidia.com URL is directly curl-able.
- **Size: 848 527 275 bytes ≈ 809 MiB.**
- Only a **license/EULA click-through**, no account: the zip ships
  `Documentation/NVIDIA RTX SDK EULA.pdf` — **[ZIP]**. Shipping a title using DLSS obliges you to ship
  that EULA/acknowledgement with your game; read it before shipping.
- Works from PowerShell the same way:
  `Invoke-WebRequest -Uri "<url>" -OutFile DLSS.zip -UseBasicParsing` (or `curl.exe -L -o DLSS.zip "<url>"`).

---

## 3. Zip layout — what goes into `<Project>/Plugins/`

Verified by parsing the zip's End-of-Central-Directory record over a 256 KiB range GET (no full
download). 1 256 entries total. **[ZIP]**

```
Documentation/            12 entries  (PDF guides + NVIDIA RTX SDK EULA.pdf)
Getting Started with NVIDIA DLSS 4 for Unreal Engine.pdf
Platforms/                15 entries  (WinGDK variants — NOT needed for desktop)
Samples/                 151 entries  (DLSS4Sample project — reference only)
ReleaseNotes_DLSS_Streamline_UE_Plugins.pdf
Plugins/               1076 entries
  Plugins/DLSS                      294
  Plugins/DLSSMoviePipelineSupport   66
  Plugins/NIS                       124
  Plugins/Streamline                  5
  Plugins/StreamlineCore            343
  Plugins/StreamlineDLSSG            66
  Plugins/StreamlineDeepDVC          66
  Plugins/StreamlineNGXCommon        45
  Plugins/StreamlineReflex           66
```

### 3.1 Recommended copy set for **DLSS Super Resolution only**

Copy **only** these two folders out of `Plugins/` into `<Project>/Plugins/`:

| Copy | Why |
|---|---|
| `DLSS/` | DLSS SR / DLSS RR / DLAA (the NGX path) — this is what SR needs |
| `StreamlineNGXCommon/` | declared dependency of `DLSS` — hidden helper plugin |

**Skip entirely** for SR-only: `StreamlineCore`, `StreamlineDLSSG`, `StreamlineReflex`,
`StreamlineDeepDVC`, `Streamline`, `DLSSMoviePipelineSupport`, `NIS`, `Platforms/`, `Samples/`,
`Documentation/`.

> If you later want **DLSS Frame Generation / Multi Frame Generation**, you must additionally copy
> `StreamlineCore`, `StreamlineDLSSG` and `StreamlineReflex` (dependencies below), and then the Reflex
> caveat in §5 applies. Out of scope here.

### 3.2 `.uplugin` descriptors — verbatim from the zip **[ZIP]**

| Plugin | `EngineVersion` | `Installed` | `Hidden` | Declares plugin dependency |
|---|---|---|---|---|
| `DLSS` | **5.8.0** | `true` | – | `StreamlineNGXCommon` (Enabled) |
| `StreamlineNGXCommon` | **5.8.0** | `true` | `true` | – |
| `StreamlineCore` | 5.8.0 | `true` | `true` | `StreamlineNGXCommon` |
| `StreamlineReflex` | 5.8.0 | `true` | – | `StreamlineCore` |
| `StreamlineDLSSG` | 5.8.0 | `true` | – | `StreamlineCore`, `StreamlineReflex` |
| `StreamlineDeepDVC` | 5.8.0 | `true` | – | – |
| `Streamline` | 5.8.0 | `true` | `true` | `StreamlineCore`, `StreamlineDLSSG`, `StreamlineDeepDVC`, `StreamlineReflex` |
| `NIS` | 5.8.0 | – | – | – |
| `DLSSMoviePipelineSupport` | 5.8.0 | – | – | – |

`DLSS.uplugin` → `"FriendlyName": "NVIDIA DLSS Super Resolution/Ray Reconstruction/DLAA"`,
`"VersionName": "8.8.0-NGX310.9.1"`, `"Version": 68`.
`StreamlineCore.uplugin` → `"VersionName": "8.8.0-SL2.14.1"`, `"Version": 141`,
`"Description": "Please use the specific NVIDIA Streamline feature plugins for DLSS-FG etc"`.

`Streamline/This_plugin_has_moved_to_StreamlineCore.md` **[ZIP]**: *"This NVIDIA Streamline 1.3.3
Legacy Compatibility plugin doesn't contain any code..."* — so `Streamline/` is a legacy shim, skip it.

**Every `.uplugin` declares `"EngineVersion": "5.8.0"` and `"Installed": true`.** Because
`"Installed": true` is set, the plugin is enabled by default without needing a `.uproject` entry —
but list it explicitly anyway (see §3.3) so the setting is visible and reproducible.

### 3.3 `.uproject` — exact block for SR only

```json
"Plugins": [
  { "Name": "DLSS", "Enabled": true }
]
```

That is genuinely all that is required. Reference point: NVIDIA's own shipped sample
`Samples/DLSS4Sample/DLSS4Sample.uproject` **[ZIP]** (with `"EngineAssociation": "5.8"`) lists
`DLSS`, `DLSSMoviePipelineSupport`, `NIS`, `UIWidgetsLib`, `StreamlineDeepDVC`, `StreamlineDLSSG`,
`StreamlineReflex`, `StreamlineCore` — i.e. the full feature set, and notably it does **not** list the
two hidden plugins `Streamline` / `StreamlineNGXCommon`, confirming they self-install.

Do **not** copy the plugin into the engine's `Plugins/` folder as well as the project's — NVIDIA's
docs warn only one copy may exist (see the Frame Generation quick-start note, [DOC] via search result:
*"Only one copy of the plugin is allowed so don't copy it to both locations"*). Project-only copy.

### 3.4 Binaries are prebuilt (no compile needed for the editor) — **[ZIP]**

The zip ships compiled binaries, so the editor works straight after extraction:

```
Plugins/DLSS/Binaries/Win64/UnrealEditor-DLSS.dll        (+ .pdb, and UnrealEditor-DLSSBlueprint/-DLSSEditor/
                                                        /-DLSSUtility/-NGXRHI/-NGXD3D11RHI/-NGXD3D12RHI/
                                                        -NGXVulkanRHI/-NGXVulkanRHIPreInit .dll)
Plugins/DLSS/Binaries/ThirdParty/Win64/nvngx_dlss.dll    (+ nvngx_dlssd.dll, Development/ variants)
Plugins/DLSS/Intermediate/Build/Win64/x64/UnrealEditor/Development/*.lib
```

Totals across the zip: 46 `.dll`, 29 `.lib`. Full plugin **source** is included too
(`Plugins/DLSS/Source/DLSS/...` with `DLSS.Build.cs`, `NGXRHI`, `Source/ThirdParty/NGX/...`), so for a
C++ project UnrealBuildTool will happily compile the plugin modules against the project's target —
that is the normal path, and it works because the engine version matches exactly.

---

## 4. CVars and settings for DLSS Super Resolution in UE 5.8

All cvars below are quoted from `Plugins/DLSS/Source/DLSS/Private/DLSSUpscaler.cpp` in the actual
8.8.0 UE 5.8 zip — **[ZIP]**, so these are the authoritative UE 5.8 names, not folklore.

### 4.1 Core cvars **[ZIP]**

| CVar | Default | Notes (verbatim from the plugin's help text) |
|---|---|---|
| `r.NGX.DLSS.Enable` | `0` | "Enable/Disable DLSS SR or RR at runtime. 0: Disable DLSS-SR and DLSS-RR (default). 1: Enable DLSS-SR or DLSS-RR. Use r.NGX.DLSS.DenoiserMode to switch between DLSS-SR and DLSS-RR." `ECVF_RenderThreadSafe` |
| `r.NGX.DLSS.DenoiserMode` | `0` | "0: DLSS-SR enabled, just upscaling, no denoising (default). 1: DLSS-RR enabled, denoising and upscaling" |
| `r.NGX.DLSS.Preset` | `0` | Force DL model preset. `0`=default/ini. For **SR**: `J`(10) slightly less ghosting/more flicker, **`K`(11) = default for DLAA/Balanced/Quality** (cheaper), `L`(12) default for UltraPerformance (sharper, more ghosting-free, best on RTX 40+), `M`(13) default for Performance (best on RTX 40+), `F`(6) legacy UltraPerformance/DLAA — "Recommended not to use" |
| `r.TemporalAA.Upscaler` | `1` | **Must be non-zero** — `IsDLSSActive()` requires `CVarTemporalAAUpscaler->GetInt() != 0`. In the editor this is the *Post Process Volume* → **Temporal Upscaling** check box (or `r.TemporalAA.Upscaling=1`) |
| `r.NGX.DLSS.AutoExposure` | `1` | `1` = DLSS internal auto-exposure; `0` = engine-computed exposure ("in some cases this may reduce artifacts") |
| `r.NGX.DLSS.ExposureScale` | `1.0f` | valid range `[0.0, 1.0]` |
| `r.NGX.DLSS.EnableAlphaUpscaling` | `-1` | `-1` = follow `r.PostProcessing.PropagateAlpha` |
| `r.NGX.DLSS.BiasCurrentColorMask` | `0` | needs a non-zero custom-stencil value |
| `r.NGX.DLSS.BiasCurrentColorMaskStencilValue` | `-1` | `-1` = use project setting; must be positive, non-zero |
| `r.NGX.DLSS.ReleaseMemoryOnDelete` | `1` | |
| `r.NGX.DLSS.FeatureCreationNode` / `.FeatureVisibilityMask` | `-1` | multi-GPU node selection |
| `r.NGX.DLSSRR.Preset` | `0` | RR-only, not needed for SR |

Logging for diagnosis: `LogDLSS`, `LogDLSSNGX`. Sample ini shows `;LogDLSSNGX=VeryVerbose`
**[ZIP]**.

### 4.2 Project Settings → Plugins → NVIDIA DLSS (`UDLSSSettings`, `Config=Engine, DefaultConfig`) **[ZIP]**

| Setting (display name) | C++ field | Default in 8.8.0 |
|---|---|---|
| Allow OTA update | `bAllowOTAUpdate` | `true` |
| NVIDIA NGX Application ID | `NVIDIANGXApplicationId` | `0` |
| Bias Current Color Custom Stencil Value | `BiasCurrentColorStencilValue` | `8` |
| Enable DLSS/DLAA for the D3D12RHI | `bEnableDLSSD3D12` | `PLATFORM_WINDOWS` |
| Enable DLSS/DLAA for the D3D11RHI | `bEnableDLSSD3D11` | `PLATFORM_WINDOWS` |
| Enable DLSS/DLAA for the VulkanRHI | `bEnableDLSSVulkan` | `PLATFORM_WINDOWS` |
| **Enable DLSS/DLAA to be turned on in Editor viewports** | `bEnableDLSSInEditorViewports` | **`false`** |
| **Enable DLSS/DLAA in Play In Editor viewports** | `bEnableDLSSInPlayInEditorViewports` | **`true`** |
| Show various DLSS/DLAA on screen debug messages | `bShowDLSSSDebugOnScreenMessages` | `true` |
| DLAA Preset | `DLAAPreset` | `Default` |
| DLSS Quality / Balanced / Performance / Ultra Performance Preset | `DLSSQualityPreset` … | `Default` |

There is also a **per-user** `UDLSSOverrideSettings` (`Config=Engine, ProjectUserConfig`, written to
the *local* user config, not the project) with `EnableDLSSInEditorViewportsOverride` /
`EnableDLSSInPlayInEditorViewportsOverride` taking `Enabled` / `Disabled` / `UseProjectSettings`
(★ = local, overridable per user) **[ZIP]**. NVIDIA's sample sets
`bEnableDLSSInEditorViewports=False`, `bEnableDLSSInPlayInEditorViewports=True` in
`DefaultEngine.ini` under `[/Script/DLSS.DLSSSettings]` **[ZIP]** — i.e. PIE on, plain editor viewport
off, which is the sane default.

Minimal `DefaultEngine.ini` for a DLSS-SR project:

```ini
[/Script/DLSS.DLSSSettings]
bEnableDLSSInPlayInEditorViewports=True
bEnableDLSSInEditorViewports=False
```

### 4.3 Quality mode, screen percentage, dynamic resolution, TSR interaction **[ZIP]**

From `FDLSSUpscaler::IsDLSSActive()` — DLSS is active only when **all** hold:

```cpp
DLSSModule->QueryDLSSSRSupport() == EDLSSSupport::Supported
  && CVarTemporalAAUpscaler->GetInt() != 0        // r.TemporalAA.Upscaler (PPV "Temporal Upscaling")
  && CVarNGXDLSSEnable.GetValueOnAnyThread() != 0 // r.NGX.DLSS.Enable
```

From `FDLSSTemporalUpscalerModularFeature::SetupSceneView()`:

```cpp
// The TSR is required for the DLSS
InOutView.AntiAliasingMethod = EAntiAliasingMethod::AAM_TSR;
InOutView.PrimaryScreenPercentageMethod = EPrimaryScreenPercentageMethod::TemporalUpscale;
```

- **TSR is mandatory**, DLSS plugs into it as a *modular upscaler*. There is a hard assert:
  `checkf(bIsDLAA || (View.PrimaryScreenPercentageMethod == EPrimaryScreenPercentageMethod::TemporalUpscale),
  "DLSS-SR requires TemporalUpscale. If you hit this assert, please set r.TemporalAA.Upscale=1");`
- **Screen percentage:** DLSS does *not* use `r.ScreenPercentage` to pick its input resolution. It
  installs an `FLegacyScreenPercentageDriver` and *compensates* for the global fraction:
  `AdjustedGlobalResolutionFraction = OptimalResolutionFraction / GetGlobalScreenPercentage()`, so
  the DLSS feature receives exactly its optimal internal fraction. Practical effect: your
  `r.ScreenPercentage` (and screen-percentage AA) is folded on top of DLSS's own ratio rather than
  replacing it.
- **Dynamic resolution:** the plugin reports `MinDynamicResolutionFraction` / `MaxDynamicResolutionFraction`
  to the engine from `FDLSSOptimalSettings::Min/MaxResolutionFraction` (accumulated over all supported
  non-fixed modes, `FDLSSUpscaler.cpp` ctor), so dynamic res interacts through the standard
  min/max-fraction path rather than fighting DLSS.
- **Quality mode is per-view**, set via the View Family / PPV (`EDLSSQualityMode`: `UltraPerformance`,
  `Performance`, `Balanced`, `Quality`, `UltraQuality`, `DLAA` — note UE-side `DLAA` is its own mode
  at native res). With `Quality = Auto` the plugin picks from the view's unscaled pixel count
  (`GetAutoQualityModeFromPixels`): `>= 8 300 000` → UltraPerformance, `>= 3 690 000` → Performance,
  `>= 2 030 000` → Quality, else none.

### 4.4 Does DLSS SR work in PIE / the editor viewport? — **Yes for PIE, no for plain editor viewport by default** **[ZIP]**

`FDLSSUpscalerViewExtension::ShouldSetupDLSS()`:

```cpp
if (GIsEditor)
{
  if (Context.Viewport->IsPlayInEditorViewport()) {
     ... EnableDLSSInPlayInEditorViewportsOverride ?: bEnableDLSSInPlayInEditorViewports  // default true
     return GIsPlayInEditorWorld && bEnableDLSSInPlayInEditorViewports;
  } else {
     ... EnableDLSSInEditorViewportsOverride ?: bEnableDLSSInEditorViewports             // default FALSE
     return bEnableDLSSInEditorViewports;
  }
}
// non-editor: only the game viewport
return Context.Viewport->GetClient() == GEngine->GameViewport;
```

- **PIE:** works out of the box (`bEnableDLSSInPlayInEditorViewports = true`). One caveat NVIDIA logs:
  *"r.ScreenPercentage for DLSS quality mode will be ignored because overridden by editor settings
  (r.Editor.Viewport.OverridePIEScreenPercentage). Change this behavior in Edit → Editor Preferences →
  Performance"* — i.e. in PIE, uncheck the PIE screen-percentage override or your `r.ScreenPercentage`
  is discarded.
- **Plain editor viewport:** off by default (`bEnableDLSSInEditorViewports = false`). Turn it on in
  Project Settings → Plugins → NVIDIA DLSS, or per-user in the **(Local)** NVIDIA DLSS settings.
  This matters for this project: the DLSS4 sample ships a UI with DLSS toggles that needs this on.
- Standalone / packaged game: only `GEngine->GameViewport` is eligible (no `-game` window, no
  offscreen scene captures).

### 4.5 Hard gates that will silently disable DLSS — worth checking on the first PIE run **[ZIP]**

`FDLSSUpscalerViewExtension::BeginRenderViewFamily` early-returns unless **all** of:

1. `ViewFamily.ViewMode == EViewModeIndex::VMI_Lit` — DLSS is off in all non-Lit view modes.
2. `ViewFamily.Scene->GetShadingPath() == EShadingPath::Deferred` — **forward shading disables DLSS.**
3. `ViewFamily.bRealtimeUpdate` is true.
4. **No** `View->bIsSceneCapture` in the family — any scene capture kills DLSS for that family.
5. At least one view has `PrimaryScreenPercentageMethod == TemporalUpscale`.
6. `ViewFamily.EngineShowFlags.AntiAliasing` is on.
7. `ViewFamily.GetTemporalUpscalerInterface() == nullptr` — otherwise the plugin logs
   `"Another plugin already set FSceneViewFamily::SetTemporalUpscalerInterface()"` and bails. This
   means **any competing temporal upscaler plugin (FSR 3 / FSR 3.1 / XeSS / NIS as a *temporal*
   upscaler) must be disabled**, or they will collide. (`NIS` from this same zip is a *spatial*
   upscaler, so it is not a conflict for the temporal slot.)
8. Unscaled view rect at least 32×32.
9. Runtime: at least `Performance`, `Balanced` and `Quality` modes reported supported, otherwise the
   plugin trips `check(...)` at init. **This is the one thing to watch on a 3070 Laptop** — see §6.

---

## 5. Reflex: built-in plugin vs `StreamlineReflex`

### 5.1 The authoritative statement — **[ZIP]** `Plugins/StreamlineCore/Docs/ProgrammingGuideDLSS_G.md` §8.0:

> "**It is required** for sl.reflex to be integrated in the host application. **Any existing Reflex SDK
> integration that does not use Streamline cannot be used with DLSS-G.** Pay special attention to the
> `eReflexMarkerPresentStart` and `eReflexMarkerPresentEnd` markers, which must provide the correct
> frame index so it can be matched to the one provided in Section 7."

Corroborated by NVIDIA's DLSS Frame Generation Quick Start Guide [DOC, via search snippet]:
*"The NVIDIA DLSS Frame Generation Unreal Engine plugin contains the latest NVIDIA Reflex technology -
a newer version than the Reflex currently built into Unreal Engine."*

### 5.2 Practical rules

| Situation | Correct configuration |
|---|---|
| **DLSS SR only (this task)** | **Neither Reflex plugin is needed at all.** Enable only `DLSS`. No Reflex conflict possible. |
| SR + DLSS Frame Generation / MFG | Use `StreamlineReflex` (+ `StreamlineCore`, `StreamlineDLSSG`). **Disable the built-in `Reflex` plugin** (`Engine/Plugins/Runtime/Nvidia/Reflex`). Having both would mean two independent non-Streamline-vs-Streamline Reflex SDK integrations alive at once — explicitly unsupported per the quote above. |
| Latency with SR only, wanting Reflex | The built-in `Reflex` plugin (`EnabledByDefault: false`, module `Reflex`, ClientOnly, v1.6) is fine *on its own*; just don't also enable `StreamlineReflex`. |

Mechanics: `StreamlineReflex` exposes `UStreamlineLibraryReflex` (`IsReflexSupported`, `SetReflexMode`,
`GetReflexMode` `Off`/`Enabled`/`Boost`, `IsReflexModeSupported`, `GetSupportedReflexModes`,
`GetDefaultReflexMode`, latency getters), driven by `t.Streamline.Reflex.Mode` / `t.Streamline.Reflex.Auto`,
and gated by `r.Streamline.InitializePlugin` — **[ZIP]** `StreamlineLibraryReflex.cpp`.

The deprecated `Streamline` plugin (§3.2) auto-enables `StreamlineCore`, `StreamlineDLSSG`,
`StreamlineDeepDVC` and `StreamlineReflex` — so **do not enable the `Streamline` plugin** even for
SR-only, or you will silently pull all of Streamline (including FG and Reflex) in. **[ZIP]**

---

## 6. RTX 3070 Laptop caveats to check on first run — **[ZIP]** + reasoning

- **A 3070 Laptop supports DLSS SR/RR/DLAA in all six quality modes**, so the plugin's
  `check(IsQualityModeSupported(Performance/Balanced/Quality))` at init should pass. **DLSS Frame
  Generation / Multi Frame Generation are RTX 40-series only** and must stay off — which the SR-only
  plugin set already guarantees.
- The DLSS models in this package are current-generation transformer models; per NVIDIA's own preset
  tooltips **[ZIP]**, presets `L` (UltraPerformance default) and `M` (Performance default) are
  *"peak performant on RTX 40 series GPUs and above"* — on a 30-series card, `L`/`M` cost more for less
  benefit than on 40-series, and **`K`** is the plugin's default for Balanced/Quality/DLAA. Start with
  `r.NGX.DLSS.Preset 0` (default) and only override if quality needs a nudge.
- Laptop GPU also has to not be blocked by the driver — if `nvngx_dlss.dll` loads but
  `QueryDLSSSRSupport()` returns unsupported, the logs to read are `LogDLSS` / `LogDLSSNGX`.

---

## 7. Concrete install recipe

```powershell
$url  = "https://developer.nvidia.com/downloads/assets/gameworks/downloads/secure/dlss/ue-dlss-5.8/8.8.0/2026.09.15_ue5.8_dlss4.5plugin_v8.8.0.zip"
$dl   = "$env:TEMP\dlss"
$dst  = "C:\UnrealProjects\poly99\unreal\Poly99Game\Plugins"   # <-- confirm the real project path
New-Item -ItemType Directory -Force $dl  | Out-Null
curl.exe -L --retry 3 --retry-delay 5 -o "$dl\dlss58.zip" $url   # ~809 MiB
Expand-Archive "$dl\dlss58.zip" -DestinationPath "$dl\x" -Force
New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item "$dl\x\Plugins\DLSS"               $dst -Recurse -Force
Copy-Item "$dl\x\Plugins\StreamlineNGXCommon" $dst -Recurse -Force
```

Then add to `Poly99Game.uproject`:

```json
"Plugins": [ { "Name": "DLSS", "Enabled": true } ]
```

and to `Config/DefaultEngine.ini`:

```ini
[/Script/DLSS.DLSSSettings]
bEnableDLSSInPlayInEditorViewports=True
bEnableDLSSInEditorViewports=False
```

Then in a level: add a **Post Process Volume**, check **Temporal Upscaling** (this is
`r.TemporalAA.Upscaler=1`, mandatory) and select **DLSS** as the upscaler. Confirm with
`LogDLSS` in the output log: it prints `QualityMode <n>: bSupported = 1, ResolutionFraction = …` for
each mode at init, plus `NumRuntimeQualityModes=…`.

---

## 8. Summary table

| Question | Answer | Confidence |
|---|---|---|
| UE 5.8 build available? | Yes — plugin **8.8.0** (DLSS 4.5), zip dated 2026.09.15, SL 2.14.1 / NGX 310.9.1 | **[HTTP]** live page + zip descriptor |
| Direct URL | `https://developer.nvidia.com/downloads/assets/gameworks/downloads/secure/dlss/ue-dlss-5.8/8.8.0/2026.09.15_ue5.8_dlss4.5plugin_v8.8.0.zip` | **[HTTP]** HEAD 200, `application/zip`, 848 527 275 B |
| Login needed? | **No.** 302 → tokenised CDN URL; ranged GET returned real ZIP magic anonymously. License is a bundled EULA PDF, not a click-through gate | **[HTTP]** |
| Folders for SR only | `DLSS/` + `StreamlineNGXCommon/` → `<Project>/Plugins/` | **[ZIP]** |
| `.uproject` entry | `{ "Name": "DLSS", "Enabled": true }` — both plugins are `"Installed": true` so they self-enable | **[ZIP]** |
| Prebuilt binaries? | Yes, `Binaries/Win64/UnrealEditor-*.dll` + `nvngx_dlss.dll` shipped; full source also included | **[ZIP]** |
| Key cvar | `r.NGX.DLSS.Enable 1` + PPV **Temporal Upscaling** (`r.TemporalAA.Upscaler 1`) + `r.NGX.DLSS.DenoiserMode 0` | **[ZIP]** |
| Screen percentage / TSR | DLSS forces `AAM_TSR` + `TemporalUpscale`, asserts on anything else; installs `FLegacyScreenPercentageDriver` that divides out the global fraction so `r.ScreenPercentage` composes on top; reports min/max fractions to dynamic res | **[ZIP]** |
| PIE? | Yes by default. Plain editor viewport: no (`false`), opt in via Project Settings or the local override | **[ZIP]** |
| Reflex conflict | Real, but only for FG. Built-in `Reflex` ≠ Streamline: *"Any existing Reflex SDK integration that does not use Streamline cannot be used with DLSS-G."* For SR-only, ignore both | **[ZIP]** ProgrammingGuideDLSS_G.md §8.0 |
| Fab / Marketplace | Cloudflare 403 — could not verify engine coverage; **not recommended** as the source | **[HTTP, failed]** |

### Sources

- `https://developer.nvidia.com/rtx/dlss` (301 target of `/rtx/dlss/get-started`) — download table, version banner, plugin description
- `https://developer.nvidia.com/downloads/assets/gameworks/downloads/secure/dlss/ue-dlss-5.8/8.8.0/2026.09.15_ue5.8_dlss4.5plugin_v8.8.0.zip` — the artifact itself
- `https://developer.nvidia.com/rtx/streamline` — Streamline overview, NGX-vs-Streamline FAQ
- `https://api.github.com/repositories/460619077` (= `NVIDIA-RTX/Streamline`) and `/releases` — SL v2.14.1, 2026-09-08
- `https://raw.githubusercontent.com/NVIDIA-RTX/Streamline/main/README.md` — "binary artifacts not in the GitHub repository"
- `https://forums.developer.nvidia.com/t/nvidia-dlss-unreal-engine-plugin-archive/377564` — past plugin versions
- `https://www.unrealengine.com/marketplace/en-US/product/nvidia-dlss` — MarketplaceURL from every `.uplugin` (403 Cloudflare here)
- `https://dev.epicgames.com/documentation/en-us/unreal-engine/nvidia-dlss-in-unreal-engine?application_version=5.8` — Epic docs (JS-rendered; not machine-readable here)
- In-zip docs (all read via range-GET from the 8.8.0 artifact): `Documentation/DLSS_Super_Resolution_UE_Plugin_Guide.pdf`, `Documentation/NVIDIA RTX SDK EULA.pdf`, `Plugins/StreamlineCore/Docs/ProgrammingGuideDLSS_G.md`, `Plugins/StreamlineCore/Docs/ProgrammingGuideReflex.md`, `Plugins/Streamline/This_plugin_has_moved_to_StreamlineCore.md`, `Samples/DLSS4Sample/*`
- Local: `C:\Unreal\UE_5.8\Engine\Plugins\Runtime\Nvidia\Reflex\Reflex.uplugin`, `C:\ProgramData\Epic\UnrealEngineLauncher\LauncherInstalled.dat`