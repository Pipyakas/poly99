# Source me. Helpers for agent-driven PIE tests through Unreal MCP.
TOOLS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(uv tool dir)/blender-mcp/Scripts/python.exe"
EV=C:/UnrealProjects/poly99/unreal/pipeline/evidence
ue_py() { printf '%s\n' "$1" > /tmp/uepy.py; timeout 120 "$PY" -I "$TOOLS/ue.py" py @/tmp/uepy.py 2>&1 | grep -v termination | grep -vE "^\s+(\||\+)"; }
pie_start() { "$PY" -I "$TOOLS/ue.py" call EditorToolset.EditorAppToolset StartPIE "{\"options\":{\"bSimulate\":false,\"playMode\":\"PlayMode_InViewPort\",\"warmupSeconds\":${1:-3}}}" >/dev/null 2>&1; }
pie_stop() { "$PY" -I "$TOOLS/ue.py" call EditorToolset.EditorAppToolset StopPIE '{}' >/dev/null 2>&1; }
PIE_HDR='import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
sim = unreal.Poly99Simulation.get(w)'
pie_py() { ue_py "$PIE_HDR
$1"; }
pie_input() { pie_py "sim.set_input_override(True, unreal.Vector2D($1), unreal.Vector2D($2), ${3:-False}, ${4:-False})" >/dev/null; }
pie_shot() { pie_py "unreal.SystemLibrary.execute_console_command(w, 'HighResShot 1280x720 filename=$EV/$1')" >/dev/null; sleep 3; echo "$EV/$1.png"; }
