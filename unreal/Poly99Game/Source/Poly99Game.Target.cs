using UnrealBuildTool;

public class Poly99GameTarget : TargetRules
{
	public Poly99GameTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("Poly99Game");
	}
}
