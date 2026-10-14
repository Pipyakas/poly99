#include "Poly99HeroAppearanceComponent.h"

#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace
{
	const FName NAME_Primary(TEXT("PrimaryColor"));
	const FName NAME_Secondary(TEXT("SecondaryColor"));
	const FName NAME_Emissive(TEXT("EmissiveColor"));
	const FName NAME_Dissolve(TEXT("Dissolve"));

	void MakeDynamicMaterials(UMeshComponent* Mesh, TArray<TObjectPtr<UMaterialInstanceDynamic>>& Out)
	{
		for (int32 i = 0; i < Mesh->GetNumMaterials(); ++i)
		{
			if (UMaterialInstanceDynamic* MID = Mesh->CreateAndSetMaterialInstanceDynamic(i))
			{
				Out.Add(MID);
			}
		}
	}
}

UPoly99HeroAppearanceComponent::UPoly99HeroAppearanceComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = false;
}

USceneComponent* UPoly99HeroAppearanceComponent::FindNamed(FName Name) const
{
	if (!Target)
	{
		return nullptr;
	}
	TInlineComponentArray<USceneComponent*> Components(Target);
	for (USceneComponent* C : Components)
	{
		if (C && C->GetFName() == Name)
		{
			return C;
		}
	}
	return nullptr;
}

void UPoly99HeroAppearanceComponent::ApplyLoadout(UPoly99HeroLoadout* InLoadout, AActor* TargetActor)
{
	Loadout = InLoadout;
	Target = TargetActor;
	if (!Loadout || !Target)
	{
		return;
	}

	for (auto& Pair : ArmorComponents)
	{
		if (Pair.Value)
		{
			Pair.Value->DestroyComponent();
		}
	}
	ArmorComponents.Reset();
	if (HelmetComponent)
	{
		HelmetComponent->DestroyComponent();
		HelmetComponent = nullptr;
	}
	TintMaterials.Reset();
	HelmetMaterials.Reset();

	Body = Cast<USkeletalMeshComponent>(FindNamed(BodyComponentName));
	if (!Body)
	{
		Body = Target->FindComponentByClass<USkeletalMeshComponent>();
	}
	if (!Body)
	{
		UE_LOG(LogTemp, Warning, TEXT("poly99: %s has no skeletal Body component; loadout not applied"), *Target->GetName());
		return;
	}

	for (const auto& Pair : Loadout->Armor)
	{
		USkeletalMesh* Mesh = Pair.Value.LoadSynchronous();
		if (!Mesh)
		{
			continue;
		}
		const FName CompName = *FString::Printf(TEXT("Armor_%s"), *StaticEnum<EPoly99ArmorSlot>()->GetNameStringByValue(static_cast<int64>(Pair.Key)));
		USkeletalMeshComponent* Piece = NewObject<USkeletalMeshComponent>(Target, CompName);
		Piece->SetSkeletalMesh(Mesh);
		Piece->SetupAttachment(Body);
		Piece->RegisterComponent();
		Piece->SetLeaderPoseComponent(Body);
		MakeDynamicMaterials(Piece, TintMaterials);
		ArmorComponents.Add(Pair.Key, Piece);
	}

	if (UStaticMesh* HelmetMesh = Loadout->Helmet.LoadSynchronous())
	{
		USceneComponent* HeadParent = FindNamed(FaceComponentName);
		USkeletalMeshComponent* HeadSkel = Cast<USkeletalMeshComponent>(HeadParent);
		if (!HeadSkel || !HeadSkel->DoesSocketExist(Loadout->HelmetSocket))
		{
			HeadParent = Body;
		}
		HelmetComponent = NewObject<UStaticMeshComponent>(Target, TEXT("Helmet"));
		HelmetComponent->SetStaticMesh(HelmetMesh);
		HelmetComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		HelmetComponent->SetupAttachment(HeadParent, Loadout->HelmetSocket);
		HelmetComponent->SetRelativeTransform(Loadout->HelmetOffset);
		HelmetComponent->RegisterComponent();
		MakeDynamicMaterials(HelmetComponent, HelmetMaterials);
		TintMaterials.Append(HelmetMaterials);
	}

	SetColors(Loadout->PrimaryColor, Loadout->SecondaryColor, Loadout->EmissiveColor);
	SetHelmet(Loadout->bHelmetOnByDefault, /*bInstant*/ true);
}

void UPoly99HeroAppearanceComponent::SetColors(FLinearColor Primary, FLinearColor Secondary, FLinearColor Emissive)
{
	for (UMaterialInstanceDynamic* MID : TintMaterials)
	{
		MID->SetVectorParameterValue(NAME_Primary, Primary);
		MID->SetVectorParameterValue(NAME_Secondary, Secondary);
		MID->SetVectorParameterValue(NAME_Emissive, Emissive);
	}
}

void UPoly99HeroAppearanceComponent::SetHelmet(bool bOn, bool bInstant)
{
	// No helmet in the loadout: the head stays uncovered.
	bOn = bOn && HelmetComponent != nullptr;
	const bool bChanged = bOn != bHelmetOn;
	bHelmetOn = bOn;

	if (bInstant || HelmetTransitionTime <= 0.f || !HelmetComponent)
	{
		TransitionAlpha = bOn ? 1.f : 0.f;
		ApplyHelmetVisibility(bOn);
		SetDissolve(1.f - TransitionAlpha);
		SetComponentTickEnabled(false);
	}
	else
	{
		// Deploy: helmet fades in, hair/face hide when it is solid (TickComponent).
		// Retract: hair/face show now, helmet fades out and hides at the end.
		if (!bOn)
		{
			ApplyHelmetVisibility(false);
		}
		HelmetComponent->SetVisibility(true);
		SetComponentTickEnabled(true);
	}

	if (bChanged)
	{
		OnHelmetChanged.Broadcast(bHelmetOn);
	}
}

void UPoly99HeroAppearanceComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	const float Goal = bHelmetOn ? 1.f : 0.f;
	TransitionAlpha = FMath::FInterpConstantTo(TransitionAlpha, Goal, DeltaTime, 1.f / HelmetTransitionTime);
	SetDissolve(1.f - TransitionAlpha);

	if (FMath::IsNearlyEqual(TransitionAlpha, Goal))
	{
		ApplyHelmetVisibility(bHelmetOn);
		SetComponentTickEnabled(false);
	}
}

void UPoly99HeroAppearanceComponent::ApplyHelmetVisibility(bool bOn)
{
	if (HelmetComponent)
	{
		HelmetComponent->SetVisibility(bOn);
	}
	for (const FName& Name : HiddenUnderHelmet)
	{
		if (USceneComponent* C = FindNamed(Name))
		{
			C->SetVisibility(!bOn, /*bPropagateToChildren*/ true);
		}
	}
	if (bHideFaceUnderHelmet && HelmetComponent)
	{
		if (USceneComponent* Face = FindNamed(FaceComponentName))
		{
			// Keep the face ticking (helmet may be attached to it) but stop rendering it.
			Face->SetVisibility(!bOn, /*bPropagateToChildren*/ false);
		}
	}
}

void UPoly99HeroAppearanceComponent::SetDissolve(float Value)
{
	for (UMaterialInstanceDynamic* MID : HelmetMaterials)
	{
		MID->SetScalarParameterValue(NAME_Dissolve, Value);
	}
}
