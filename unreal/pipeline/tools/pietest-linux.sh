# Source me. Linux port of pietest.sh: agent-driven PIE tests through Unreal MCP.
# linux: bash only; no PowerShell, no .exe paths.
TOOLS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# linux: uv tool dir Python replaced with system python3 running with -I.
PY="python3"
# linux: engine/editor paths live under /var/mnt instead of C:\Unreal.
UE_ROOT="/var/mnt/ssd2/UE_5.8"
EDITOR_BIN="$UE_ROOT/Engine/Binaries/Linux/UnrealEditor"
# linux: evidence directory on the D1 checkout (no drive letters).
EV="/var/mnt/ssd1/poly99/unreal/pipeline/evidence"

# linux: transient files use mktemp; the underlying tmp dir is not hardcoded in outputs.
mcp_reachable() {
    python3 -I -c "import sys, urllib.request, urllib.error
try:
    urllib.request.urlopen('http://localhost:8000/mcp', timeout=2)
except urllib.error.HTTPError:
    pass
except Exception:
    sys.exit(1)
" >/dev/null 2>&1
}

# linux: prefer MCP HTTP endpoint; fall back to launching UnrealEditor directly.
editor_launch_cmd() {
    echo "$EDITOR_BIN /var/mnt/ssd1/poly99/unreal/Poly99Game/Poly99Game.uproject -SharedDataCachePath=//192.168.1.2/UE-DDC"
}

ue_py() {
    local tmp
    tmp=$(mktemp)
    printf '%s\n' "$1" > "$tmp"
    timeout 120 python3 -I "$TOOLS/ue-linux.py" py @"$tmp" 2>&1 \
        | grep -v termination | grep -vE "^[[:space:]]+(\||\+)"
    local rc=$?
    rm -f "$tmp"
    return $rc
}

pie_start() {
    if mcp_reachable; then
        python3 -I "$TOOLS/ue-linux.py" call EditorToolset.EditorAppToolset StartPIE \
            "{\"options\":{\"bSimulate\":false,\"playMode\":\"PlayMode_InViewPort\",\"warmupSeconds\":${1:-3}}}" >/dev/null 2>&1
    else
        # linux: MCP gone; launch editor directly instead of going through HTTP.
        nohup "$EDITOR_BIN" /var/mnt/ssd1/poly99/unreal/Poly99Game/Poly99Game.uproject \
            -SharedDataCachePath=//192.168.1.2/UE-DDC >/dev/null 2>&1 &
    fi
}

pie_stop() {
    if mcp_reachable; then
        python3 -I "$TOOLS/ue-linux.py" call EditorToolset.EditorAppToolset StopPIE '{}' >/dev/null 2>&1
    else
        pkill -f UnrealEditor >/dev/null 2>&1 || true
    fi
}

PIE_HDR='import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
sim = unreal.Poly99Simulation.get(w)'
pie_py() { ue_py "$PIE_HDR
$1"; }

pie_input() { pie_py "sim.set_input_override(True, unreal.Vector2D($1), unreal.Vector2D($2), ${3:-False}, ${4:-False})" >/dev/null; }

pie_shot() { pie_py "unreal.SystemLibrary.execute_console_command(w, 'HighResShot 1280x720 filename=$EV/$1')" >/dev/null; sleep 3; echo "$EV/$1.png"; }