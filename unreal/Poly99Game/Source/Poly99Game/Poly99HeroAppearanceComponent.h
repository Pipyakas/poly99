#pragma once

#include "Components/ActorComponent.h"
#include "Poly99HeroLoadout.h"
#include "Poly99HeroAppearanceComponent.generated.h"

class USkeletalMeshComponent;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FPoly99HelmetChanged, bool, bHelmetOn);

/**
 * Applies a UPoly99HeroLoadout to a MetaHuman actor: armor pieces as leader-posed
 * followers of the Body, a rigid helmet on the head, color tints, and the helmet
 * toggle (hides hair/beard under the helmet, shows the face when it is off).
 */
UCLASS(ClassGroup = poly99, meta = (BlueprintSpawnableComponent))
class POLY99GAME_API UPoly99HeroAppearanceComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UPoly99HeroAppearanceComponent();

	/** Builds armor/helmet on TargetActor (the MetaHuman actor). */
	UFUNCTION(BlueprintCallable, Category = "poly99|Appearance")
	void ApplyLoadout(UPoly99HeroLoadout* InLoadout, AActor* TargetActor);

	UFUNCTION(BlueprintCallable, Category = "poly99|Appearance")
	void SetHelmet(bool bOn, bool bInstant = false);

	UFUNCTION(BlueprintCallable, Category = "poly99|Appearance")
	void ToggleHelmet() { SetHelmet(!bHelmetOn); }

	UFUNCTION(BlueprintPure, Category = "poly99|Appearance")
	bool IsHelmetOn() const { return bHelmetOn; }

	/** The MetaHuman Body mesh found by ApplyLoadout (armor follows it). */
	UFUNCTION(BlueprintPure, Category = "poly99|Appearance")
	USkeletalMeshComponent* GetBody() const { return Body; }

	UFUNCTION(BlueprintCallable, Category = "poly99|Appearance")
	void SetColors(FLinearColor Primary, FLinearColor Secondary, FLinearColor Emissive);

	UPROPERTY(BlueprintAssignable, Category = "poly99|Appearance")
	FPoly99HelmetChanged OnHelmetChanged;

	/** Component names on the MetaHuman actor hidden while the helmet is on. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99|Appearance")
	TArray<FName> HiddenUnderHelmet = { TEXT("Hair"), TEXT("Beard"), TEXT("Mustache"), TEXT("Fuzz") };

	/** Hide the Face mesh entirely while the helmet is on (opaque visor; saves GPU). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99|Appearance")
	bool bHideFaceUnderHelmet = true;

	/** Seconds for the helmet deploy/retract dissolve (material scalar "Dissolve", 0 = solid). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99|Appearance")
	float HelmetTransitionTime = 0.25f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99|Appearance")
	FName BodyComponentName = TEXT("Body");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99|Appearance")
	FName FaceComponentName = TEXT("Face");

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	USceneComponent* FindNamed(FName Name) const;
	void ApplyHelmetVisibility(bool bOn);
	void SetDissolve(float Value);

	UPROPERTY(Transient)
	TObjectPtr<UPoly99HeroLoadout> Loadout;

	UPROPERTY(Transient)
	TObjectPtr<AActor> Target;

	UPROPERTY(Transient)
	TObjectPtr<USkeletalMeshComponent> Body;

	UPROPERTY(Transient)
	TMap<EPoly99ArmorSlot, TObjectPtr<USkeletalMeshComponent>> ArmorComponents;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> HelmetComponent;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UMaterialInstanceDynamic>> TintMaterials;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UMaterialInstanceDynamic>> HelmetMaterials;

	bool bHelmetOn = true;
	float TransitionAlpha = 1.f; // 1 = helmet fully on
};
