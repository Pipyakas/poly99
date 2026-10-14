#include "Poly99EntityRenderer.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"

APoly99EntityRenderer::APoly99EntityRenderer()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));

	// Voxel enemies from unreal/blender (imported by poly99_pipeline.kit, authored facing +X).
	FPoly99EntityVisual Bullet;
	Bullet.Mesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Engine/BasicShapes/Sphere.Sphere")));
	Bullet.ZOffset = 90.f;
	Visuals.Add(EPoly99EntityType::Bullet, Bullet);

	FPoly99EntityVisual Grasshopper;
	Grasshopper.Mesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/Poly99/Kit/SM_Enemy_Grasshopper.SM_Enemy_Grasshopper")));
	Visuals.Add(EPoly99EntityType::EnemyGrasshopper, Grasshopper);

	FPoly99EntityVisual Wanderer;
	Wanderer.Mesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/Poly99/Kit/SM_Enemy_Wanderer.SM_Enemy_Wanderer")));
	Visuals.Add(EPoly99EntityType::EnemyWanderer, Wanderer);
}

void APoly99EntityRenderer::BeginPlay()
{
	Super::BeginPlay();

	for (const auto& Pair : Visuals)
	{
		UStaticMesh* Mesh = Pair.Value.Mesh.LoadSynchronous();
		if (!Mesh)
		{
			continue;
		}
		UInstancedStaticMeshComponent* ISM = NewObject<UInstancedStaticMeshComponent>(this);
		ISM->SetStaticMesh(Mesh);
		if (UMaterialInterface* Mat = Pair.Value.Material.LoadSynchronous())
		{
			ISM->SetMaterial(0, Mat);
		}
		ISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		ISM->SetMobility(EComponentMobility::Movable);
		ISM->SetupAttachment(GetRootComponent());
		ISM->RegisterComponent();
		ISMs.Add(ISM);

		FTypeBatch& Batch = Batches.Add(Pair.Key);
		Batch.ISM = ISM;
		Batch.Visual = Pair.Value;
		if (Pair.Value.ScalePerRadius > 0.f)
		{
			Batch.UnitScale = Pair.Value.ScalePerRadius;
		}
		else
		{
			// Fit the mesh's horizontal footprint to the entity diameter.
			const FVector Size = Mesh->GetBounds().BoxExtent * 2.f;
			const float Footprint = FMath::Max3(static_cast<float>(Size.X), static_cast<float>(Size.Y), 1.f);
			Batch.UnitScale = 2.f / Footprint;
		}
	}
}

void APoly99EntityRenderer::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const UPoly99Simulation* Sim = GetWorld()->GetSubsystem<UPoly99Simulation>();
	if (!Sim)
	{
		return;
	}

	for (auto& Pair : Batches)
	{
		Pair.Value.Transforms.Reset();
	}
	for (const FPoly99EntityView& E : Sim->GetEntities())
	{
		FTypeBatch* Batch = Batches.Find(E.Type);
		if (!Batch)
		{
			continue;
		}
		const FVector Loc = E.Location + FVector(0.f, 0.f, Batch->Visual.ZOffset);
		const FRotator Rot(0.f, E.Yaw + Batch->Visual.YawOffset, 0.f);
		Batch->Transforms.Emplace(Rot, Loc, FVector(E.Radius * Batch->UnitScale));
	}
	for (auto& Pair : Batches)
	{
		FTypeBatch& B = Pair.Value;
		const int32 Have = B.ISM->GetInstanceCount();
		const int32 Want = B.Transforms.Num();
		if (Have != Want)
		{
			B.ISM->ClearInstances();
			B.ISM->AddInstances(B.Transforms, /*bShouldReturnIndices*/ false, /*bWorldSpace*/ true);
		}
		else if (Want > 0)
		{
			B.ISM->BatchUpdateInstancesTransforms(0, B.Transforms, /*bWorldSpace*/ true, /*bMarkRenderStateDirty*/ true, /*bTeleport*/ true);
		}
	}
}
