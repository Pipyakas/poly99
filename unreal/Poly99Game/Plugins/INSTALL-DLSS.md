# DLSS / StreamlineNGXCommon plugin binaries — local only

The `Plugins/DLSS` (8.8.0-NGX310.9.1, `DLSS.uplugin` Version 68) and
`Plugins/StreamlineNGXCommon` (8.8.0, Version 134) trees are the stock
NVIDIA UE 5.8 plugins plus one local patch (below). Only their **source,
shaders, config and `.uplugin` manifests** are committed. The vendored
binary payload is gitignored (`unreal/Poly99Game/Plugins/*/Binaries/`,
`*/Intermediate/`):

- `Binaries/Win64/*.pdb` — ~62 MB each, a dozen of them; far over GitHub's
  100 MB hard limit and pointless in a repo.
- `Binaries/ThirdParty/Win64/**/nvngx_dlss.dll`, `nvngx_dlssd.dll` — NVIDIA
  SDK binaries (redistributable only under the NGX license, ~59–93 MB each).
- Plugin `Intermediate/` build objects.

Total plugin tree is ~936 MB, mostly those binaries. Re-fetch: reinstall the
plugins from the Epic launcher (Engine 5.8 "NVIDIA DLSS" / "NGX Common"),
or copy them back from this machine's `C:\UnrealProjects\poly99`.

## Local patch (2026-10-13)

`Source/DLSS/Private/DLSSUpscaler.cpp` (~line 1290, search "poly99"): DLAA's
NGX feature is fixed-resolution and asserts (`NGXD3D12RHI.cpp:431`) once
dynamic resolution renders below native. The dynres heuristic reports an upper
bound of 1.0 until its first history resize, so on the first -game frames DLAA
got picked and the next frame crashed. Patch: never pick DLAA while dynamic
resolution is configured (`r.DynamicRes.OperationMode != 0`).

Reapply to any reinstall of the plugin before shipping builds that use DLAA.
