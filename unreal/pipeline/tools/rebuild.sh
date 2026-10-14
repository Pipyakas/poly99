# Save, quit editor, build Poly99GameEditor, relaunch, wait for MCP.
source "$(dirname "${BASH_SOURCE[0]}")/pietest.sh"
pie_stop; sleep 1
ue_py 'import unreal
unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
unreal.SystemLibrary.quit_editor()' >/dev/null
for i in $(seq 1 60); do sleep 3; powershell -c "if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) { exit 1 }" && break; done
powershell -c "& 'C:\Unreal\UE_5.8\Engine\Build\BatchFiles\Build.bat' Poly99GameEditor Win64 Development -Project='C:\UnrealProjects\poly99\unreal\Poly99Game\Poly99Game.uproject' -WaitMutex 2>&1 | Select-String -Pattern 'Poly99.*(error|warning)|error C|error LNK|Result:' | Select -Last 15"
powershell -c "Start-Process 'C:\Unreal\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe' -ArgumentList '\"C:\UnrealProjects\poly99\unreal\Poly99Game\Poly99Game.uproject\"','-SharedDataCachePath=//192.168.1.2/UE-DDC'"
# Shared DDC = D1 HDD share (\\192.168.1.2\UE-DDC); passed explicitly because shells that
# predate the env-var fix still carry a malformed machine-level UE-SharedDataCachePath.
# Forward slashes on purpose: bash double quotes collapse "\\" to "\" (UE then saw \192.168.1.2).
for i in $(seq 1 60); do sleep 10; powershell -c "if (Test-NetConnection 127.0.0.1 -Port 8000 -InformationLevel Quiet -WarningAction SilentlyContinue) { exit 0 } else { exit 1 }" && break; done; echo editor-up
