#pragma once

#include "GameFramework/Actor.h"
#include "Poly99Simulation.h"
#include "Poly99EntityRenderer.generated.h"

class UInstancedStaticMeshComponent;
class UStaticMesh;
class UMaterialInterface;

USTRUCT(BlueprintType)
struct FPoly99EntityVisual
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	TSoftObjectPtr<UStaticMesh> Mesh;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	TSoftObjectPtr<UMaterialInterface> Material;

	/** Scale = Radius * ScalePerRadius (mesh assumed ~1 UU across per unit scale if 0 = use mesh bounds). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float ScalePerRadius = 0.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float ZOffset = 0.f;

	/** Added to entity yaw (e.g. -90 for meshes authored facing +Y). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float YawOffset = 0.f;
};

/** Draws all non-player core entities with one instanced mesh component per entity type. */
UCLASS()
class POLY99GAME_API APoly99EntityRenderer : public AActor
{
	GENERATED_BODY()

public:
	APoly99EntityRenderer();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	TMap<EPoly99EntityType, FPoly99EntityVisual> Visuals;

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

private:
	struct FTypeBatch
	{
		TObjectPtr<UInstancedStaticMeshComponent> ISM;
		FPoly99EntityVisual Visual;
		float UnitScale = 1.f; // scale for a radius of 1
		TArray<FTransform> Transforms;
	};

	TMap<EPoly99EntityType, FTypeBatch> Batches;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UInstancedStaticMeshComponent>> ISMs;
};
