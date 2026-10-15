#include "Poly99AttractMode.h"

#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Poly99AttractScreen.h"
#include "Poly99HeroPawn.h"

APoly99AttractMode::APoly99AttractMode()
{
	PrimaryActorTick.bCanEverTick = true;
	// After the hero's own tick, so the orbit frames where the hero actually ended up this
	// frame instead of lagging a frame behind it.
	PrimaryActorTick.TickGroup = TG_PostPhysics;
}

APoly99AttractMode* APoly99AttractMode::Get(UWorld* World)
{
	// UWorld has no GetActorByClass; TActorIterator is the way to find a single instance.
	// The IsValid guard is load-bearing, not decoration: without it the compiler can see
	// the loop always returns on its first iteration and the build treats the ++It as
	// unreachable code, which is an error here.
	if (!World)
	{
		return nullptr;
	}
	for (TActorIterator<APoly99AttractMode> It(World); It; ++It)
	{
		if (IsValid(*It))
		{
			return *It;
		}
	}
	return nullptr;
}

void APoly99AttractMode::BeginPlay()
{
	Super::BeginPlay();
	Phase = EPhase::Running;
	// A fixed starting angle so the view does not jump between runs.
	Angle = 35.f;
}

APlayerController* APoly99AttractMode::FirstPlayer() const
{
	return GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
}

void APoly99AttractMode::EnsureStarted()
{
	if (bStarted)
	{
		return;
	}
	APlayerController* PC = FirstPlayer();
	if (!PC)
	{
		// No local player yet (the pawn is spawned for them a moment later). Try again next
		// tick rather than failing the whole mode.
		return;
	}

	Camera = GetWorld()->SpawnActor<ACameraActor>(ACameraActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator);
	if (!Camera)
	{
		return;
	}
	Camera->GetCameraComponent()->SetFieldOfView(52.f);

	Screen = CreateWidget<UPoly99AttractScreen>(PC, UPoly99AttractScreen::StaticClass());
	if (Screen)
	{
		Screen->AddToViewport(20);
	}

	PC->SetViewTarget(Camera);
	bStarted = true;
}

FVector APoly99AttractMode::FocusPoint() const
{
	// Film the hero. It exists from boot because the game runs windowed with a local
	// player (Pixel Streaming is not a dedicated server), so there is nothing to spawn and
	// nothing to keep in sync.
	if (const UWorld* World = GetWorld())
	{
		for (TActorIterator<APoly99HeroPawn> It(World); It; ++It)
		{
			if (IsValid(*It))
			{
				// Chest height, so the hero sits slightly below centre in frame.
				return It->GetActorLocation() + FVector(0.f, 0.f, 110.f);
			}
		}
	}
	return GetActorLocation();
}

void APoly99AttractMode::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	switch (Phase)
	{
	case EPhase::Idle:
		return;

	case EPhase::Running:
	{
		EnsureStarted();
		if (!bStarted)
		{
			return;
		}
		Time += DeltaSeconds;
		Angle = FMath::Fmod(Angle + OrbitSpeed * DeltaSeconds, 360.f);

		const FVector Focus = FocusPoint();
		const float R = Radius * (1.f + RadiusWobble * FMath::Sin(Time * 0.21f));
		const float H = Height + HeightWobble * FMath::Sin(Time * 0.13f + 1.1f);

		const FVector CamLoc = Focus + FVector(FMath::Cos(FMath::DegreesToRadians(Angle)) * R,
			FMath::Sin(FMath::DegreesToRadians(Angle)) * R, H);
		// Aim above and left of the hero rather than straight at him: that drops him below
		// centre and pushes him to the right of frame, where the centred title and prompt
		// are not. Aiming directly at the hero put his head behind the POLY99 text.
		const FVector ToHero = (Focus - CamLoc).GetSafeNormal();
		const FVector Right = FVector::CrossProduct(FVector::UpVector, ToHero).GetSafeNormal();
		const FVector Look = Focus + FVector(0.f, 0.f, AimRise) + Right * AimSide;

		Camera->SetActorLocationAndRotation(CamLoc,
			(Look - CamLoc).Rotation(), false, nullptr, ETeleportType::TeleportPhysics);
		return;
	}

	case EPhase::FadingOut:
	{
		FadeElapsed += DeltaSeconds;
		const float T = FMath::Clamp(FadeElapsed / FMath::Max(FadeSeconds, 0.01f), 0.f, 1.f);
		if (Screen)
		{
			Screen->SetFade(T);
		}
		if (APlayerController* PC = FirstPlayer())
		{
			PC->PlayerCameraManager->StartCameraFade(1.f, 1.f, FMath::Max(FadeSeconds, 0.01f), FLinearColor::Black);
		}
		if (T >= 1.f)
		{
			Phase = EPhase::HandingOver;
			FadeElapsed = 0.f;
			if (APlayerController* PC = FirstPlayer())
			{
				// Give the view back to the hero's own spring arm. Cut while the screen is
				// black so the change of camera is not visible.
				// Both branches are AActor*, but the ternary has to be spelled out for it to
				// compile as a single expression.
				APawn* HeroPawn = PC->GetPawn();
				PC->SetViewTarget(HeroPawn ? static_cast<AActor*>(HeroPawn) : static_cast<AActor*>(PC));
			}
			if (Screen)
			{
				Screen->RemoveFromParent();
			}
			if (Camera)
			{
				Camera->Destroy();
				Camera = nullptr;
			}
		}
		return;
	}

	case EPhase::HandingOver:
	{
		FadeElapsed += DeltaSeconds;
		if (FadeElapsed >= FMath::Max(FadeSeconds, 0.01f))
		{
			if (APlayerController* PC = FirstPlayer())
			{
				PC->PlayerCameraManager->StopCameraFade();
			}
			bAttracting = false;
			Phase = EPhase::Idle;
			// The attract actor has no more work to do.
			SetActorTickEnabled(false);
			Destroy();
		}
		return;
	}
	}
}

void APoly99AttractMode::SkipToGameplay()
{
	if (!bAttracting || Phase == EPhase::FadingOut || Phase == EPhase::HandingOver)
	{
		return;
	}
	Phase = EPhase::FadingOut;
	FadeElapsed = 0.f;
}