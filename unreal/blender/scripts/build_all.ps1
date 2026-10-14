# poly99 Blender asset pipeline.
# Runs every generator headless in order and fails on error.
$ErrorActionPreference = "Stop"
$Blender = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
$Scripts = Split-Path -Parent $MyInvocation.MyCommand.Path

foreach ($script in @("arena_kit.py", "enemy_voxel.py", "preview.py")) {
    Write-Host "=== $script ==="
    & $Blender -b --factory-startup --python "$Scripts\$script"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "$script failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

Write-Host "All assets built."
