#pragma once

#include "Engine/DataAsset.h"
#include "Poly99HeroLoadout.generated.h"

class USkeletalMesh;
class UStaticMesh;

UENUM(BlueprintType)
enum class EPoly99ArmorSlot : uint8
{
	Chest,
	Shoulders,
	Arms,
	Hands,
	Legs,
	Feet,
	Back
};

/** One customizable hero: which MetaHuman, which armor pieces, colors, helmet default. */
UCLASS(BlueprintType)
class POLY99GAME_API UPoly99HeroLoadout : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	/** Assembled MetaHuman actor Blueprint (Body/Face/groom components). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Character")
	TSoftClassPtr<AActor> MetaHumanClass;

	/** Armor pieces skinned to the MetaHuman body skeleton; follow the Body via leader pose. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor")
	TMap<EPoly99ArmorSlot, TSoftObjectPtr<USkeletalMesh>> Armor;

	/** Rigid helmet attached to HelmetSocket on the Face (or Body) mesh. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Helmet")
	TSoftObjectPtr<UStaticMesh> Helmet;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Helmet")
	FName HelmetSocket = TEXT("head");

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Helmet")
	FTransform HelmetOffset;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Helmet")
	bool bHelmetOnByDefault = true;

	/** Applied as vector params PrimaryColor / SecondaryColor / EmissiveColor on armor + helmet materials. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Colors")
	FLinearColor PrimaryColor = FLinearColor(0.08f, 0.09f, 0.11f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Colors")
	FLinearColor SecondaryColor = FLinearColor(0.55f, 0.57f, 0.6f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Colors")
	FLinearColor EmissiveColor = FLinearColor(0.f, 2.5f, 4.f);
};
