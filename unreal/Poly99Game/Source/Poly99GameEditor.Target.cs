using UnrealBuildTool;

public class Poly99GameEditorTarget : TargetRules
{
	public Poly99GameEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("Poly99Game");
	}
}
