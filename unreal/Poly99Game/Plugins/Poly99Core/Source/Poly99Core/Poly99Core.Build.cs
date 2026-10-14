using System.IO;
using UnrealBuildTool;

public class Poly99Core : ModuleRules
{
	public Poly99Core(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });

		// Shared gameplay core lives at <repo>/core and is compiled into this module (CoreAmalgam.cpp).
		string CoreDir = Path.GetFullPath(Path.Combine(ModuleDirectory, "../../../../../../core"));
		PrivateIncludePaths.Add(CoreDir);
	}
}
