#!/usr/bin/env bash
# Rebuild Poly99GameEditor (Linux) and print the manual relaunch command.
# linux: no args, no editor relaunch (headless-friendly).
set -euo pipefail

UE_ROOT="/var/mnt/ssd2/UE_5.8"
PROJECT="/var/mnt/ssd1/poly99/unreal/Poly99Game/Poly99Game.uproject"
BUILD_SH="$UE_ROOT/Engine/Build/BatchFiles/Linux/Build.sh"

"$BUILD_SH" Poly99GameEditor Linux Development \
    -Project="$PROJECT" -WaitMutex 2>&1 \
    | grep -E 'Poly99.*(error|warning)|error C|error LNK|Result:' | tail -n 15

echo "Manual launch: $UE_ROOT/Engine/Binaries/Linux/UnrealEditor $PROJECT -SharedDataCachePath=//192.168.1.2/UE-DDC"
# linux: Shared DDC = D1 HDD share (//192.168.1.2/UE-DDC); forward slashes so UE parses it.