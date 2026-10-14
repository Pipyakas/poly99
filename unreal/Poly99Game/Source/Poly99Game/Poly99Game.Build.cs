using UnrealBuildTool;

public class Poly99Game : ModuleRules
{
	public Poly99Game(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput", "Poly99Core" });
	}
}
