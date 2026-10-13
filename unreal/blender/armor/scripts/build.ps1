<#
    poly99+ hard-surface armour pipeline.

    Runs the whole chain headless and stops at the first failure:

        armor_set_a.py   -> export\SKM_Armor_*.fbx
        helmet_a.py      -> export\SM_Helmet_A.fbx, export\SKM_Helmet_A.fbx
        verify.py        -> export\verify_report.json, export\previews\*.png

    Usage:
        pwsh -File armor\scripts\build.ps1
        pwsh -File armor\scripts\build.ps1 -Blender "D:\blender.exe" -SkipVerify
#>
[CmdletBinding()]
param(
    [string]$Blender = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    [switch]$SkipVerify
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$armorDir  = Split-Path -Parent $scriptDir
$exportDir = Join-Path $armorDir 'export'
$logDir    = Join-Path $exportDir 'logs'

if (-not (Test-Path -LiteralPath $Blender)) {
    throw "Blender not found at '$Blender'. Pass -Blender <path to blender.exe>."
}

New-Item -ItemType Directory -Force -Path $exportDir, $logDir | Out-Null

$stages = @(
    @{ Name = 'armor'; Script = 'armor_set_a.py' }
    @{ Name = 'helmet'; Script = 'helmet_a.py' }
)
if (-not $SkipVerify) {
    $stages += @{ Name = 'verify'; Script = 'verify.py' }
}

$sw = [System.Diagnostics.Stopwatch]::StartNew()
foreach ($stage in $stages) {
    $py   = Join-Path $scriptDir $stage.Script
    $log  = Join-Path $logDir ("{0}.log" -f $stage.Name)
    Write-Host ("==> {0,-7} {1}" -f $stage.Name, $stage.Script)

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName  = $Blender
    $psi.Arguments = "-b --factory-startup --python `"$py`""
    $psi.RedirectStandardOutput  = $true
    $psi.RedirectStandardError   = $true
    $psi.UseShellExecute = $false
    $proc = [System.Diagnostics.Process]::Start($psi)

    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    $code = $proc.ExitCode

    $stdout + $stderr | Out-File -FilePath $log -Encoding utf8
    $script:LAST_STAGE_LOG = $log

    if ($code -ne 0) {
        # Blender exits 0 even when the script raises SystemExit, so the tail of
        # the log is the only reliable failure signal - surface it verbatim.
        Write-Host $stdout
        Write-Host $stderr
        throw "stage '$($stage.Name)' failed (exit $code). Full log: $log"
    }
    # Blender prints tracebacks on *stderr*, so scanning stdout alone reported a
    # crash as a green stage.  Scan the combined text that was written to $log.
    $combined = $stdout + $stderr
    if ($combined -match '(?m)^Traceback \(most recent call last\)' -or
        $combined -match 'SystemExit:') {
        Write-Host $stdout
        Write-Host $stderr
        throw "stage '$($stage.Name)' raised. Full log: $log"
    }
    Write-Host ("    ok  ({0:n1}s)  log: {1}" -f $sw.Elapsed.TotalSeconds, (Split-Path -Leaf $log))
}

# --------------------------------------------------------------------------- #
# summary from the artifacts the stages just wrote
# --------------------------------------------------------------------------- #
Write-Host ''
Write-Host '==> summary'

$tris = Join-Path $exportDir 'armor_tris.txt'
if (Test-Path -LiteralPath $tris) {
    Get-Content -LiteralPath $tris | ForEach-Object { Write-Host "    $_" }
}

$report = Join-Path $exportDir 'verify_report.json'
if (Test-Path -LiteralPath $report) {
    $r = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    Write-Host ''
    Write-Host ("    {0,-14} {1,10} {2,10} {3}" -f 'export', 'tris', 'rest_dev', 'status')
    foreach ($e in $r.exports) {
        Write-Host ("    {0,-14} {1,10} {2,10:N2} {3}" -f `
            ($e.file -replace '\.fbx$', ''), $e.tris, $e.rest_dev, $e.status)
    }
    Write-Host ''
    # Both coverage measures are printed: `gap3cm` is the gated one (first hit
    # along +normal within 3 cm), `near>3cm` is the independent nearest-surface
    # measure.  A zero in the second column means there are no holes anywhere,
    # so anything above the 1% target in the first is skin poking *through* a
    # plate seam rather than a missing undersuit.
    Write-Host ("    {0,-14} {1,10} {2,12} {3,10} {4,8}   {5}" -f `
        'pose', 'gap3cm%', 'near>3cm', 'poke%', 'verts', 'L / R (never summed)')
    foreach ($p in $r.poses) {
        $ps = $p.per_side
        Write-Host ("    {0,-14} {1,10:N2} {2,12:N2} {3,10:N2} {4,8}   L {5,6:N2}%  R {6,6:N2}%  d {7,5:N2}" -f `
            $p.pose, $p.gap3cm_pct, $p.nearest_far_pct, $p.poke_pct, $p.tested,
            $ps.L.gap3cm_pct, $ps.R.gap3cm_pct, $p.side_delta_pct)
    }
    Write-Host ("    targets: gap3cm < {0:N1}% overall AND < {1:N1}% per side" -f `
        $r.coverage_target, $r.side_target)
    if ($r.bare_skin) {
        Write-Host ("    bare-skin acceptance: worst {0:N4}% over {1} renders at {2}x{3}, spring arm {4}-{5} m (target < {6:N2}%)" -f `
            $r.bare_skin.worst_pct, $r.bare_skin.rows.Count,
            $r.bare_skin.resolution[0], $r.bare_skin.resolution[1],
            $r.bare_skin.arm_m[0], $r.bare_skin.arm_m[-1],
            $r.bare_skin.target_pct)
    }
    if ($r.helmet.Count -gt 0) {
        Write-Host ("    helmet: {0} tris, {1:N2}% of head points outside the shell envelope" -f `
            $r.helmet[0].tris, $r.helmet[0].containment_exposed_pct)
        Write-Host ("            6cm-along-normal probe: {0:N2}% (under-reports at ears/under-jaw)" -f `
            $r.helmet[0].normal_probe_exposed_pct)
    }
}

Write-Host ''
Write-Host ("DONE in {0:n1}s" -f $sw.Elapsed.TotalSeconds)