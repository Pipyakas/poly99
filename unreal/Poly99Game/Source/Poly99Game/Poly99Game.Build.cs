using UnrealBuildTool;

public class Poly99Game : ModuleRules
{
	public Poly99Game(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		// UMG/Slate are for the attract screen (Poly99AttractScreen), which builds its widget
		// tree in C++ - this project has no Widget Blueprint assets.
		PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput", "Poly99Core", "DeveloperSettings", "UMG", "Slate", "SlateCore" });
	}
}
