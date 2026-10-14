#include "Poly99HeroPawn.h"

#include "Animation/AnimSingleNodeInstance.h"
#include "Animation/BlendSpace.h"
#include "Camera/CameraComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/ChildActorComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Poly99HeroAppearanceComponent.h"
#include "Poly99HeroLoadout.h"
#include "Poly99Simulation.h"

APoly99HeroPawn::APoly99HeroPawn()
{
	PrimaryActorTick.bCanEverTick = true;
	// Read the simulation after it ticked this frame.
	PrimaryActorTick.TickGroup = TG_PostPhysics;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	Visual = CreateDefaultSubobject<UChildActorComponent>(TEXT("Visual"));
	Visual->SetupAttachment(Root);

	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(Root);
	CameraBoom->SetUsingAbsoluteRotation(true);
	CameraBoom->SetRelativeRotation(FRotator(-62.f, 0.f, 0.f));
	CameraBoom->TargetArmLength = 2600.f;
	CameraBoom->bDoCollisionTest = false;
	CameraBoom->bEnableCameraLag = true;
	CameraBoom->CameraLagSpeed = 6.f;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(CameraBoom);
	Camera->SetFieldOfView(55.f);

	Appearance = CreateDefaultSubobject<UPoly99HeroAppearanceComponent>(TEXT("Appearance"));
}

void APoly99HeroPawn::BeginPlay()
{
	Super::BeginPlay();
	if (UPoly99HeroLoadout* L = Loadout.LoadSynchronous())
	{
		ApplyLoadout(L);
	}
}

void APoly99HeroPawn::ApplyLoadout(UPoly99HeroLoadout* NewLoadout)
{
	if (!NewLoadout)
	{
		return;
	}
	if (UClass* MetaHumanClass = NewLoadout->MetaHumanClass.LoadSynchronous())
	{
		Visual->SetChildActorClass(MetaHumanClass);
	}
	Appearance->ApplyLoadout(NewLoadout, Visual->GetChildActor());

	USkeletalMeshComponent* Body = Appearance->GetBody();
	if (UBlendSpace* BS = Locomotion.LoadSynchronous(); Body && BS)
	{
		Body->SetAnimationMode(EAnimationMode::AnimationSingleNode);
		Body->PlayAnimation(BS, /*bLooping*/ true);
	}
}

void APoly99HeroPawn::UpdateLocomotion(const FVector& Velocity, float DeltaSeconds)
{
	USkeletalMeshComponent* Body = Appearance->GetBody();
	UAnimSingleNodeInstance* Inst = Body ? Body->GetSingleNodeInstance() : nullptr;
	if (!Inst)
	{
		return;
	}
	// Direction of travel relative to where the hero faces (aim), in degrees.
	const float FacingYaw = Visual->GetComponentRotation().Yaw - VisualYawOffset;
	float Direction = 0.f;
	if (PlanarSpeed > 1.f)
	{
		Direction = FRotator::NormalizeAxis(FMath::RadiansToDegrees(FMath::Atan2(Velocity.Y, Velocity.X)) - FacingYaw);
	}
	const FVector2D Target(Direction, PlanarSpeed);
	// Avoid interpolating across the +-180 seam.
	if (FMath::Abs(Target.X - BlendInput.X) > 180.f)
	{
		BlendInput.X = Target.X;
	}
	BlendInput = FMath::Vector2DInterpTo(BlendInput, Target, DeltaSeconds, LocomotionInterpSpeed);
	Inst->SetBlendSpacePosition(FVector(BlendInput.X, BlendInput.Y, 0.f));
}

void APoly99HeroPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const UPoly99Simulation* Sim = GetWorld()->GetSubsystem<UPoly99Simulation>();
	FPoly99EntityView Player;
	if (!Sim || !Sim->GetPlayer(Player))
	{
		PlanarSpeed = 0.f;
		UpdateLocomotion(FVector::ZeroVector, DeltaSeconds);
		return;
	}

	SetActorLocation(Player.Location);
	PlanarSpeed = Player.Velocity.Size2D();

	const FRotator Current = Visual->GetComponentRotation();
	const FRotator Goal(0.f, Player.Yaw + VisualYawOffset, 0.f);
	Visual->SetWorldRotation(FMath::RInterpConstantTo(Current, Goal, DeltaSeconds, TurnRate));
	UpdateLocomotion(Player.Velocity, DeltaSeconds);
}
