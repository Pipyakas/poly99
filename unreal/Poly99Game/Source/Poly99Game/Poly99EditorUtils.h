#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "Poly99EditorUtils.generated.h"

class UBlendSpace;
class UAnimSequence;

/** Helpers for the agent pipeline (editor Python) where the Python API falls short. */
UCLASS()
class POLY99GAME_API UPoly99EditorUtils : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Runs the asset's full PostEditChange (e.g. a BlendSpace rebuilds its sample grid)
	 * and marks its package dirty. No-op outside the editor.
	 */
	UFUNCTION(BlueprintCallable, Category = "poly99|Editor")
	static void NotifyAssetChanged(UObject* Asset);

	/**
	 * Replaces all samples of a blend space (Python cannot reach the editor sample API):
	 * clears, AddSample() for each pair, validates and resamples the grid.
	 * Returns the number of samples accepted.
	 */
	UFUNCTION(BlueprintCallable, Category = "poly99|Editor")
	static int32 BuildBlendSpace(UBlendSpace* BlendSpace, const TArray<UAnimSequence*>& Animations, const TArray<FVector>& SampleValues);
};
