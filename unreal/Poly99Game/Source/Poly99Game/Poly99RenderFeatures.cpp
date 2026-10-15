#include "Poly99RenderFeatures.h"

#include "HAL/IConsoleManager.h"
#include "Misc/OutputDeviceRedirector.h"

/**
 * Why this exists (D1, 2026-10-15): a measured A/B on the RX 6700 XT showed disabling Lumen,
 * hardware RT, MegaLights and Virtual Shadow Maps changed GPU time by less than the run-to-run
 * noise floor. The settings were all present and accepted, so the only way to find out what each
 * one actually does is to switch it and look.
 *
 * Every write uses ECVF_SetByCode priority on purpose. The underlying CVars are tagged
 * ECVF_Scalability, which means a scalability change is allowed to overwrite a lower-priority
 * set. Without this, picking a sg.* level would silently switch features back on.
 */

namespace Poly99RenderFeaturesPrivate
{
	/** One CVar plus the value to use when its feature is on, and when it is off. */
	struct FCVarBinding
	{
		const TCHAR* Name;
		int32 OnValue;
		int32 OffValue;
		/** False for enum-style CVars (Lumen/None) where On/Off are not 0/1. */
		bool bBoolStyle = true;
	};

	/** CVars owned by each feature. Kept in one place so LogState can report what it touched. */
	TArray<FCVarBinding> BindingsFor(EPoly99RenderFeature Feature)
	{
		switch (Feature)
		{
		case EPoly99RenderFeature::Lumen:
			// 1 = Lumen, 0 = None (EDynamicGlobalIlluminationMethod / EReflectionMethod in EngineTypes.h).
			return {
				{ TEXT("r.DynamicGlobalIlluminationMethod"), 1, 0, false },
				{ TEXT("r.ReflectionMethod"),                    1, 0, false },
				{ TEXT("r.Lumen.DiffuseIndirect.Allow"),         1, 0 },
				{ TEXT("r.Lumen.Reflections.Allow"),             1, 0 },
			};
		case EPoly99RenderFeature::Nanite:
			return {
				{ TEXT("r.Nanite.ProjectEnabled"), 1, 0 },
				{ TEXT("r.Nanite"),                1, 0 },
			};
		case EPoly99RenderFeature::HardwareRayTracing:
			// No VSM hardware-RT switch exists in 5.8: Virtual Shadow Maps ray trace through the
			// software SMRT.* family only, so hardware RT does not reach them and VSM is its own
			// independent toggle below.
			return {
				{ TEXT("r.RayTracing"),                        1, 0 },
				{ TEXT("r.Lumen.HardwareRayTracing"),          1, 0 },
				{ TEXT("r.MegaLights.HardwareRayTracing"),      1, 0 },
			};
		case EPoly99RenderFeature::MegaLights:
			return {
				{ TEXT("r.MegaLights.EnableForProject"), 1, 0 },
			};
		case EPoly99RenderFeature::VirtualShadowMaps:
			return {
				{ TEXT("r.Shadow.Virtual.Enable"), 1, 0 },
			};
		default:
			return {};
		}
	}

	/** The CVar used to report whether a feature is currently on. */
	const TCHAR* PrimaryCVar(EPoly99RenderFeature Feature)
	{
		switch (Feature)
		{
		case EPoly99RenderFeature::Lumen:                return TEXT("r.Lumen.DiffuseIndirect.Allow");
		case EPoly99RenderFeature::Nanite:               return TEXT("r.Nanite");
		case EPoly99RenderFeature::HardwareRayTracing:   return TEXT("r.RayTracing");
		case EPoly99RenderFeature::MegaLights:           return TEXT("r.MegaLights.EnableForProject");
		case EPoly99RenderFeature::VirtualShadowMaps:    return TEXT("r.Shadow.Virtual.Enable");
		default:                                         return TEXT("");
		}
	}

	const TCHAR* FeatureName(EPoly99RenderFeature Feature)
	{
		switch (Feature)
		{
		case EPoly99RenderFeature::Lumen:                return TEXT("Lumen");
		case EPoly99RenderFeature::Nanite:               return TEXT("Nanite");
		case EPoly99RenderFeature::HardwareRayTracing:   return TEXT("HardwareRT");
		case EPoly99RenderFeature::MegaLights:           return TEXT("MegaLights");
		case EPoly99RenderFeature::VirtualShadowMaps:    return TEXT("VirtualShadowMaps");
		default:                                         return TEXT("Unknown");
		}
	}

	/** Console spelling -> enum. Accepts the short names used on the command line. */
	bool ParseFeature(const TCHAR* Arg, EPoly99RenderFeature& Out)
	{
		if (FCString::Stricmp(Arg, TEXT("lumen")) == 0)                          { Out = EPoly99RenderFeature::Lumen; return true; }
		if (FCString::Stricmp(Arg, TEXT("nanite")) == 0)                         { Out = EPoly99RenderFeature::Nanite; return true; }
		if (FCString::Stricmp(Arg, TEXT("hwrt")) == 0 || FCString::Stricmp(Arg, TEXT("hardware_rt")) == 0 || FCString::Stricmp(Arg, TEXT("hardware-rt")) == 0)
		                                                                             { Out = EPoly99RenderFeature::HardwareRayTracing; return true; }
		if (FCString::Stricmp(Arg, TEXT("megalights")) == 0)                     { Out = EPoly99RenderFeature::MegaLights; return true; }
		if (FCString::Stricmp(Arg, TEXT("vsm")) == 0 || FCString::Stricmp(Arg, TEXT("virtual_shadow_maps")) == 0)
		                                                                             { Out = EPoly99RenderFeature::VirtualShadowMaps; return true; }
		return false;
	}

	/** "0"/"1"/"toggle"/"on"/"off" -> value. Returns false when the argument is unusable. */
	bool ParseBool(const TCHAR* Arg, bool bCurrent, bool& Out)
	{
		if (FCString::Stricmp(Arg, TEXT("1")) == 0 || FCString::Stricmp(Arg, TEXT("on")) == 0 || FCString::Stricmp(Arg, TEXT("true")) == 0)
		{
			Out = true;
			return true;
		}
		if (FCString::Stricmp(Arg, TEXT("0")) == 0 || FCString::Stricmp(Arg, TEXT("off")) == 0 || FCString::Stricmp(Arg, TEXT("false")) == 0)
		{
			Out = false;
			return true;
		}
		if (FCString::Stricmp(Arg, TEXT("toggle")) == 0)
		{
			Out = !bCurrent;
			return true;
		}
		return false;
	}

	void ApplyFeature(EPoly99RenderFeature Feature, bool bEnabled)
	{
		const TArray<FCVarBinding> Bindings = BindingsFor(Feature);

		for (const FCVarBinding& B : Bindings)
		{
			IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(B.Name);
			if (!Var)
			{
				UE_LOG(LogTemp, Verbose, TEXT("poly99 render features: CVar %s not present in this build"), B.Name);
				continue;
			}
			const int32 Value = bEnabled ? B.OnValue : B.OffValue;
			// ECVF_SetByCode: outranks a scalability write, so "off" stays off.
			Var->Set(Value, ECVF_SetByCode);
		}

		UE_LOG(LogTemp, Log, TEXT("poly99 render features: %s = %s"), FeatureName(Feature), bEnabled ? TEXT("ON") : TEXT("off"));
	}
}

bool UPoly99RenderFeatures::HasFeatureCVars(EPoly99RenderFeature Feature)
{
	return IConsoleManager::Get().FindConsoleVariable(
		Poly99RenderFeaturesPrivate::PrimaryCVar(Feature)) != nullptr;
}

bool UPoly99RenderFeatures::SetFeature(EPoly99RenderFeature Feature, bool bEnabled)
{
	Poly99RenderFeaturesPrivate::ApplyFeature(Feature, bEnabled);

	// MegaLights traces many lights through hardware RT; with HWRT off it cannot contribute,
	// so say so rather than let the owner conclude MegaLights is broken.
	if (Feature == EPoly99RenderFeature::HardwareRayTracing && !bEnabled && IsFeatureEnabled(EPoly99RenderFeature::MegaLights))
	{
		UE_LOG(LogTemp, Warning,
			TEXT("poly99 render features: hardware RT is off but MegaLights is still enabled. "
			     "MegaLights needs hardware RT and will not contribute until it is back on."));
	}
	if (Feature == EPoly99RenderFeature::HardwareRayTracing && bEnabled && !IsFeatureEnabled(EPoly99RenderFeature::VirtualShadowMaps))
	{
		UE_LOG(LogTemp, Log,
			TEXT("poly99 render features: hardware RT is on but Virtual Shadow Maps is off; "
			     "VSM was left as the owner set it."));
	}
	return HasFeatureCVars(Feature);
}

bool UPoly99RenderFeatures::IsFeatureEnabled(EPoly99RenderFeature Feature)
{
	IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(
		Poly99RenderFeaturesPrivate::PrimaryCVar(Feature));
	return Var ? (Var->GetInt() != 0) : false;
}

void UPoly99RenderFeatures::ApplyPreset(EPoly99RenderFeaturePreset Preset)
{
	switch (Preset)
	{
	case EPoly99RenderFeaturePreset::AllOff:
		// Indirect lighting off first so MegaLights is not left asking for RT that is going away.
		SetFeature(EPoly99RenderFeature::MegaLights, false);
		SetFeature(EPoly99RenderFeature::Lumen, false);
		SetFeature(EPoly99RenderFeature::HardwareRayTracing, false);
		SetFeature(EPoly99RenderFeature::VirtualShadowMaps, false);
		SetFeature(EPoly99RenderFeature::Nanite, true); // geometry only; nothing here needs RT
		break;
	case EPoly99RenderFeaturePreset::NoIndirect:
		SetFeature(EPoly99RenderFeature::MegaLights, false);
		SetFeature(EPoly99RenderFeature::Lumen, false);
		break;
	case EPoly99RenderFeaturePreset::AllOn:
	default:
		SetFeature(EPoly99RenderFeature::Nanite, true);
		SetFeature(EPoly99RenderFeature::HardwareRayTracing, true);
		SetFeature(EPoly99RenderFeature::Lumen, true);
		SetFeature(EPoly99RenderFeature::MegaLights, true);
		SetFeature(EPoly99RenderFeature::VirtualShadowMaps, true);
		break;
	}
	LogState();
}

FPoly99RenderFeatureState UPoly99RenderFeatures::GetState()
{
	FPoly99RenderFeatureState State;
	State.bLumen = IsFeatureEnabled(EPoly99RenderFeature::Lumen);
	State.bNanite = IsFeatureEnabled(EPoly99RenderFeature::Nanite);
	State.bHardwareRayTracing = IsFeatureEnabled(EPoly99RenderFeature::HardwareRayTracing);
	State.bMegaLights = IsFeatureEnabled(EPoly99RenderFeature::MegaLights);
	State.bVirtualShadowMaps = IsFeatureEnabled(EPoly99RenderFeature::VirtualShadowMaps);
	return State;
}

void UPoly99RenderFeatures::ApplyAll()
{
	const UPoly99RenderFeatureSettings* Settings = GetDefault<UPoly99RenderFeatureSettings>();

	// MegaLights before HWRT: turning HWRT on while MegaLights is off would still leave the
	// MegaLights/HWRT mismatch warning firing on the next toggle.
	SetFeature(EPoly99RenderFeature::MegaLights, Settings->bEnableMegaLights);
	SetFeature(EPoly99RenderFeature::Lumen, Settings->bEnableLumen);
	SetFeature(EPoly99RenderFeature::Nanite, Settings->bEnableNanite);
	SetFeature(EPoly99RenderFeature::HardwareRayTracing, Settings->bEnableHardwareRayTracing);
	SetFeature(EPoly99RenderFeature::VirtualShadowMaps, Settings->bEnableVirtualShadowMaps);
}

void UPoly99RenderFeatures::LogState()
{
	const FPoly99RenderFeatureState State = GetState();
	UE_LOG(LogTemp, Log, TEXT("poly99 render features: Lumen=%d Nanite=%d HardwareRT=%d MegaLights=%d VSM=%d"),
		State.bLumen, State.bNanite, State.bHardwareRayTracing, State.bMegaLights, State.bVirtualShadowMaps);
}

// ---------------------------------------------------------------------------
// Console commands. These exist so the toggles can be driven from -ExecCmds during
// headless A/B runs without a UI, and from the in-game console for live testing.
// ---------------------------------------------------------------------------
namespace
{
	/** Shared body for "poly99.<feature> [0|1|toggle]" */
	void HandleFeatureCommand(const TCHAR* FeatureArg, const TCHAR* ValueArg)
	{
		EPoly99RenderFeature Feature;
		if (!Poly99RenderFeaturesPrivate::ParseFeature(FeatureArg, Feature))
		{
			UE_LOG(LogTemp, Warning, TEXT("poly99: unknown feature '%s'. Try: lumen, nanite, hwrt, megalights, vsm"), FeatureArg);
			return;
		}

		const bool bCurrent = UPoly99RenderFeatures::IsFeatureEnabled(Feature);
		bool bDesired = bCurrent;
		if (ValueArg && !Poly99RenderFeaturesPrivate::ParseBool(ValueArg, bCurrent, bDesired))
		{
			UE_LOG(LogTemp, Warning, TEXT("poly99: expected 0, 1, on, off or toggle (got '%s')"), ValueArg);
			return;
		}
		if (!ValueArg)
		{
			bDesired = !bCurrent;
		}

		UPoly99RenderFeatures::SetFeature(Feature, bDesired);
		UPoly99RenderFeatures::LogState();
	}

	FAutoConsoleCommand CmdLumen(
		TEXT("poly99.Lumen"),
		TEXT("Lumen GI + reflections. Usage: poly99.Lumen [0|1|toggle]"),
		FConsoleCommandWithArgsDelegate::CreateStatic([](const TArray<FString>& Args)
		{
			HandleFeatureCommand(TEXT("lumen"), Args.Num() > 0 ? *Args[0] : nullptr);
		}));

	FAutoConsoleCommand CmdNanite(
		TEXT("poly99.Nanite"),
		TEXT("Nanite geometry. Usage: poly99.Nanite [0|1|toggle]"),
		FConsoleCommandWithArgsDelegate::CreateStatic([](const TArray<FString>& Args)
		{
			HandleFeatureCommand(TEXT("nanite"), Args.Num() > 0 ? *Args[0] : nullptr);
		}));

	FAutoConsoleCommand CmdHwrt(
		TEXT("poly99.HWRT"),
		TEXT("Hardware ray tracing. Usage: poly99.HWRT [0|1|toggle]"),
		FConsoleCommandWithArgsDelegate::CreateStatic([](const TArray<FString>& Args)
		{
			HandleFeatureCommand(TEXT("hwrt"), Args.Num() > 0 ? *Args[0] : nullptr);
		}));

	FAutoConsoleCommand CmdMegaLights(
		TEXT("poly99.MegaLights"),
		TEXT("MegaLights many-light tracing (needs hardware RT). Usage: poly99.MegaLights [0|1|toggle]"),
		FConsoleCommandWithArgsDelegate::CreateStatic([](const TArray<FString>& Args)
		{
			HandleFeatureCommand(TEXT("megalights"), Args.Num() > 0 ? *Args[0] : nullptr);
		}));

	FAutoConsoleCommand CmdVSM(
		TEXT("poly99.VSM"),
		TEXT("Virtual Shadow Maps (needs Nanite). Usage: poly99.VSM [0|1|toggle]"),
		FConsoleCommandWithArgsDelegate::CreateStatic([](const TArray<FString>& Args)
		{
			HandleFeatureCommand(TEXT("vsm"), Args.Num() > 0 ? *Args[0] : nullptr);
		}));

	FAutoConsoleCommand CmdPreset(
		TEXT("poly99.RenderFeatures.Preset"),
		TEXT("Apply a group: allon | alloff | noindirect"),
		FConsoleCommandWithArgsDelegate::CreateStatic([](const TArray<FString>& Args)
		{
			if (Args.Num() == 0) { UPoly99RenderFeatures::LogState(); return; }
			const FString Which = Args[0];
			if (Which.Equals(TEXT("allon"),  ESearchCase::IgnoreCase))   { UPoly99RenderFeatures::ApplyPreset(EPoly99RenderFeaturePreset::AllOn); }
			else if (Which.Equals(TEXT("alloff"), ESearchCase::IgnoreCase)) { UPoly99RenderFeatures::ApplyPreset(EPoly99RenderFeaturePreset::AllOff); }
			else if (Which.Equals(TEXT("noindirect"), ESearchCase::IgnoreCase)) { UPoly99RenderFeatures::ApplyPreset(EPoly99RenderFeaturePreset::NoIndirect); }
			else
			{
				UE_LOG(LogTemp, Warning, TEXT("poly99.RenderFeatures.Preset: expected allon, alloff or noindirect (got '%s')"), *Which);
			}
		}));

	FAutoConsoleCommand CmdPrint(
		TEXT("poly99.RenderFeatures"),
		TEXT("Print the current state of every render feature toggle."),
		FConsoleCommandDelegate::CreateStatic([]() { UPoly99RenderFeatures::LogState(); }));
}