#pragma once

#include "GameFramework/GameModeBase.h"
#include "Poly99Simulation.h"
#include "Poly99GameMode.generated.h"

class APoly99EntityRenderer;

UCLASS()
class POLY99GAME_API APoly99GameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	APoly99GameMode();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	FPoly99CoreConfig CoreConfig;

	/** 0 = random seed per run. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	int32 Seed = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	TSubclassOf<APoly99EntityRenderer> RendererClass;

	virtual void StartPlay() override;
};
