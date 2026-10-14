#pragma once

#include "GameFramework/Pawn.h"
#include "Poly99HeroPawn.generated.h"

class UCameraComponent;
class UChildActorComponent;
class USpringArmComponent;
class UPoly99HeroAppearanceComponent;
class UPoly99HeroLoadout;
class UBlendSpace;

/**
 * The player hero. Position comes from the poly99 core player entity; this pawn
 * only presents it: MetaHuman visual (child actor), armor/helmet, aim facing,
 * and the top-down camera.
 */
UCLASS()
class POLY99GAME_API APoly99HeroPawn : public APawn
{
	GENERATED_BODY()

public:
	APoly99HeroPawn();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	TSoftObjectPtr<UPoly99HeroLoadout> Loadout;

	/** 2D blend space: X = move direction relative to facing (deg), Y = speed (UU/s). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	TSoftObjectPtr<UBlendSpace> Locomotion = TSoftObjectPtr<UBlendSpace>(FSoftObjectPath(TEXT("/Game/Poly99/Animation/BS_Hero_Locomotion.BS_Hero_Locomotion")));

	/** Smoothing for the blend-space input (higher = snappier). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float LocomotionInterpSpeed = 10.f;

	UFUNCTION(BlueprintCallable, Category = "poly99")
	void ApplyLoadout(UPoly99HeroLoadout* NewLoadout);

	UFUNCTION(BlueprintPure, Category = "poly99")
	UPoly99HeroAppearanceComponent* GetAppearance() const { return Appearance; }

	/** Planar speed in UU/s, for animation. */
	UFUNCTION(BlueprintPure, Category = "poly99")
	float GetPlanarSpeed() const { return PlanarSpeed; }

	/** Degrees/second the visual turns toward the aim yaw. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float TurnRate = 1080.f;

	/** MetaHuman/UE skeletal meshes face +Y; rotate so the visual faces +X at yaw 0. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float VisualYawOffset = -90.f;

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "poly99")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "poly99")
	TObjectPtr<UChildActorComponent> Visual;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "poly99")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "poly99")
	TObjectPtr<UCameraComponent> Camera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "poly99")
	TObjectPtr<UPoly99HeroAppearanceComponent> Appearance;

private:
	void UpdateLocomotion(const FVector& Velocity, float DeltaSeconds);

	float PlanarSpeed = 0.f;
	FVector2D BlendInput = FVector2D::ZeroVector;
};
