// Independent runtime toggles for the GPU features this project enables.
// linux/D1 note: these exist because the D1 report found Lumen, hardware RT, MegaLights and
// Virtual Shadow Maps all configured on but contributing nothing measurable on the RX 6700 XT,
// so the owner needs a way to switch each one and see what it actually does.
// Each toggle owns its own CVars only; nothing here touches sg.* so the scalability levels keep
// working for the features that remain enabled.
#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "Poly99RenderFeatures.generated.h"

/** Individually switchable GPU features. Each is independent of the others. */
UENUM(BlueprintType)
enum class EPoly99RenderFeature : uint8
{
	Lumen,
	Nanite,
	HardwareRayTracing,
	MegaLights,
	VirtualShadowMaps,
};

/** Current on/off state of every toggle. */
USTRUCT(BlueprintType)
struct FPoly99RenderFeatureState
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Poly99|Render Features")
	bool bLumen = true;

	UPROPERTY(BlueprintReadOnly, Category = "Poly99|Render Features")
	bool bNanite = true;

	UPROPERTY(BlueprintReadOnly, Category = "Poly99|Render Features")
	bool bHardwareRayTracing = true;

	UPROPERTY(BlueprintReadOnly, Category = "Poly99|Render Features")
	bool bMegaLights = true;

	UPROPERTY(BlueprintReadOnly, Category = "Poly99|Render Features")
	bool bVirtualShadowMaps = true;
};

/** Named combinations, for quick A/B work from the console. */
UENUM(BlueprintType)
enum class EPoly99RenderFeaturePreset : uint8
{
	/** Everything the project config enables. */
	AllOn,
	/** Every GPU feature off; cheapest possible frame. */
	AllOff,
	/** Indirect lighting off but geometry features on - the usual "cheap but still looks modern" cut. */
	NoIndirect,
};

/**
 * Project Settings -> Game -> Poly99 Render Features.
 * Defaults come from DefaultGame.ini; editing here rewrites the CVars at next startup.
 * At runtime use UPoly99RenderFeatures::SetFeature, which wins over these defaults.
 */
UCLASS(config = Game, defaultconfig, meta = (DisplayName = "Poly99 Render Features"))
class POLY99GAME_API UPoly99RenderFeatureSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	/** Lumen global illumination and reflections. Off falls back to no dynamic GI. */
	UPROPERTY(config, EditAnywhere, Category = "Features")
	bool bEnableLumen = true;

	/** Nanite virtualised geometry. Note: existing meshes keep their built Nanite data either way. */
	UPROPERTY(config, EditAnywhere, Category = "Features")
	bool bEnableNanite = true;

	/** Hardware ray tracing. On Navi 22 there are no RT cores, so this is emulated in compute. */
	UPROPERTY(config, EditAnywhere, Category = "Features")
	bool bEnableHardwareRayTracing = true;

	/** MegaLights many-light tracing. Requires hardware RT to contribute anything. */
	UPROPERTY(config, EditAnywhere, Category = "Features")
	bool bEnableMegaLights = true;

	/** Virtual Shadow Maps. Gated on Nanite, not on ray tracing. */
	UPROPERTY(config, EditAnywhere, Category = "Features")
	bool bEnableVirtualShadowMaps = true;

	//~ Begin UDeveloperSettings interface
	virtual FName GetCategoryName() const override { return FName(TEXT("Game")); }
	//~ End UDeveloperSettings interface
};

/** Runtime control surface for the toggles. */
UCLASS()
class POLY99GAME_API UPoly99RenderFeatures : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Switch one feature on or off. Independent of the others.
	 * Uses SetByCode priority so a later scalability change cannot silently switch a
	 * feature back on; that is what keeps an owner-chosen "off" actually off across sg.* changes.
	 * Returns false only when the CVar does not exist in this build.
	 */
	UFUNCTION(BlueprintCallable, Category = "Poly99|Render Features")
	static bool SetFeature(EPoly99RenderFeature Feature, bool bEnabled);

	UFUNCTION(BlueprintPure, Category = "Poly99|Render Features")
	static bool IsFeatureEnabled(EPoly99RenderFeature Feature);

	UFUNCTION(BlueprintCallable, Category = "Poly99|Render Features")
	static void ApplyPreset(EPoly99RenderFeaturePreset Preset);

	UFUNCTION(BlueprintPure, Category = "Poly99|Render Features")
	static FPoly99RenderFeatureState GetState();

	/** Push every toggle into the CVars. Called at module startup and after a settings change. */
	UFUNCTION(BlueprintCallable, Category = "Poly99|Render Features")
	static void ApplyAll();

	/** Log the current state and the CVars that back each toggle. */
	UFUNCTION(BlueprintCallable, Category = "Poly99|Render Features")
	static void LogState();

	/** True when the CVar exists; used to report builds where a feature was compiled out. */
	static bool HasFeatureCVars(EPoly99RenderFeature Feature);
};