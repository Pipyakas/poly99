#include "Poly99PlayerController.h"

#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"
#include "Poly99AttractMode.h"
#include "Poly99HeroAppearanceComponent.h"
#include "Poly99HeroPawn.h"
#include "Poly99Simulation.h"

namespace
{
	// Our action space: X = forward (screen up), Y = right.
	//
	// Sticks are bound as SEPARATE 1D keys, not Gamepad_Left2D / Gamepad_Right2D.
	// Pixel Streaming 2 only ever injects Gamepad_LeftX / Gamepad_LeftY (and the
	// right-stick equivalents) - see RTCInputHandler.cpp's GamepadInputToFKey table,
	// which maps each browser gamepad axis to its own FKey. UE has no code that
	// synthesises the 2D stick keys from those: EKeys::GetPairedKeyDetails is only used
	// to *decompose* a 2D key into X/Y when injecting, and the SDL platform layer pushes
	// the 2D key itself. So binding Gamepad_Left2D works with a real local controller and
	// silently never fires over a stream, which is exactly how movement went missing.
	void AddDeadZone(FEnhancedActionKeyMapping& M, UObject* Outer)
	{
		UInputModifierDeadZone* D = NewObject<UInputModifierDeadZone>(Outer);
		D->LowerThreshold = 0.2f;
		M.Modifiers.Add(D);
	}

	void MapAxis(UInputMappingContext* Ctx, UInputAction* Action, FKey Key, UObject* Outer)
	{
		FEnhancedActionKeyMapping& M = Ctx->MapKey(Action, Key);
		AddDeadZone(M, Outer);
	}
}

APoly99PlayerController::APoly99PlayerController()
{
	bShowMouseCursor = true;
	bEnableClickEvents = false;
	bEnableMouseOverEvents = false;
}

UInputAction* APoly99PlayerController::MakeAction(FName Name, int32 ValueType)
{
	UInputAction* A = NewObject<UInputAction>(this, Name);
	A->ValueType = static_cast<EInputActionValueType>(ValueType);
	return A;
}

void APoly99PlayerController::BeginPlay()
{
	Super::BeginPlay();
	// Gamepad only: never capture or lock the mouse (gamepad input still reaches the game).
	FInputModeGameAndUI Mode;
	Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
	Mode.SetHideCursorDuringCapture(false);
	SetInputMode(Mode);
	// The mapping context is added at the end of SetupInputComponent, where it is built.
	// Doing it from here depends on SetupInputComponent having already run, which the
	// engine does not guarantee - InitInputSystem() (and therefore SetupInputComponent())
	// is also called lazily from PlayerTick.
}

void APoly99PlayerController::SetupInputComponent()
{
	Super::SetupInputComponent();

	// X = forward, Y = right. Stick Y is "up" on a pad, so it feeds the forward axis.
	MoveXAction = MakeAction(TEXT("IA_MoveX"), static_cast<int32>(EInputActionValueType::Axis1D));
	MoveYAction = MakeAction(TEXT("IA_MoveY"), static_cast<int32>(EInputActionValueType::Axis1D));
	AimXAction = MakeAction(TEXT("IA_AimX"), static_cast<int32>(EInputActionValueType::Axis1D));
	AimYAction = MakeAction(TEXT("IA_AimY"), static_cast<int32>(EInputActionValueType::Axis1D));
	FireAction = MakeAction(TEXT("IA_Fire"), static_cast<int32>(EInputActionValueType::Boolean));
	DashAction = MakeAction(TEXT("IA_Dash"), static_cast<int32>(EInputActionValueType::Boolean));
	HelmetAction = MakeAction(TEXT("IA_ToggleHelmet"), static_cast<int32>(EInputActionValueType::Boolean));
	StartAction = MakeAction(TEXT("IA_Start"), static_cast<int32>(EInputActionValueType::Boolean));

	Mapping = NewObject<UInputMappingContext>(this, TEXT("IMC_Poly99"));

	MapAxis(Mapping, MoveXAction, EKeys::Gamepad_LeftX, this);
	MapAxis(Mapping, MoveYAction, EKeys::Gamepad_LeftY, this);
	MapAxis(Mapping, AimXAction, EKeys::Gamepad_RightX, this);
	MapAxis(Mapping, AimYAction, EKeys::Gamepad_RightY, this);

	Mapping->MapKey(FireAction, EKeys::Gamepad_RightTrigger);
	Mapping->MapKey(DashAction, EKeys::Gamepad_LeftTrigger);
	Mapping->MapKey(DashAction, EKeys::Gamepad_RightShoulder);
	Mapping->MapKey(HelmetAction, EKeys::Gamepad_FaceButton_Top);
	// The attract screen says "PRESS A". Without this binding that promise would be a lie:
	// no existing action was on the face button.
	Mapping->MapKey(StartAction, EKeys::Gamepad_FaceButton_Bottom);

	UEnhancedInputComponent* EIC = CastChecked<UEnhancedInputComponent>(InputComponent);
	EIC->BindAction(MoveXAction, ETriggerEvent::Triggered, this, &APoly99PlayerController::OnMoveX);
	EIC->BindAction(MoveYAction, ETriggerEvent::Triggered, this, &APoly99PlayerController::OnMoveY);
	EIC->BindAction(AimXAction, ETriggerEvent::Triggered, this, &APoly99PlayerController::OnAimX);
	EIC->BindAction(AimYAction, ETriggerEvent::Triggered, this, &APoly99PlayerController::OnAimY);
	EIC->BindAction(FireAction, ETriggerEvent::Started, this, &APoly99PlayerController::OnFire);
	EIC->BindAction(FireAction, ETriggerEvent::Completed, this, &APoly99PlayerController::OnFireStop);
	EIC->BindAction(DashAction, ETriggerEvent::Started, this, &APoly99PlayerController::OnDash);
	EIC->BindAction(HelmetAction, ETriggerEvent::Started, this, &APoly99PlayerController::OnToggleHelmet);
	EIC->BindAction(StartAction, ETriggerEvent::Started, this, &APoly99PlayerController::OnStart);

	if (UEnhancedInputLocalPlayerSubsystem* Sub = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer()))
	{
		Sub->AddMappingContext(Mapping, 0);
		UE_LOG(LogTemp, Log, TEXT("Input: IMC_Poly99 added (%d mappings). Move=LeftX/LeftY Aim=RightX/RightY Fire=RT Dash=LT,RB Helmet=Y"), Mapping->GetMappings().Num());
	}
	else
	{
		UE_LOG(LogTemp, Error, TEXT("Input: no EnhancedInputLocalPlayerSubsystem - IMC_Poly99 NOT added, gamepad will do nothing"));
	}
}

void APoly99PlayerController::OnMoveX(const FInputActionValue& Value) { Move.X = Value.Get<float>(); }
void APoly99PlayerController::OnMoveY(const FInputActionValue& Value) { Move.Y = Value.Get<float>(); }

void APoly99PlayerController::OnAimX(const FInputActionValue& Value) { StickAim.X = Value.Get<float>(); }
void APoly99PlayerController::OnAimY(const FInputActionValue& Value) { StickAim.Y = Value.Get<float>(); }
void APoly99PlayerController::OnFire(const FInputActionValue&) { bFireHeld = true; }
void APoly99PlayerController::OnFireStop(const FInputActionValue&) { bFireHeld = false; }
void APoly99PlayerController::OnDash(const FInputActionValue&) { bDashQueued = true; }

void APoly99PlayerController::OnStart(const FInputActionValue&)
{
	SkipAttract();
}

void APoly99PlayerController::OnToggleHelmet(const FInputActionValue&)
{
	bHelmetPressed = true;
	if (APoly99HeroPawn* Hero = GetPawn<APoly99HeroPawn>())
	{
		Hero->GetAppearance()->ToggleHelmet();
	}
}

void APoly99PlayerController::SkipAttract()
{
	if (APoly99AttractMode* Attract = APoly99AttractMode::Get(GetWorld()))
	{
		Attract->SkipToGameplay();
	}
}

void APoly99PlayerController::PlayerTick(float DeltaTime)
{
	Super::PlayerTick(DeltaTime);

	// Any real stick movement also starts the game. The attract screen is only ever
	// dismissed by the player doing something, and A alone is a narrow target - a drifted
	// stick should count too.
	if (APoly99AttractMode* Attract = APoly99AttractMode::Get(GetWorld()))
	{
		if (Move.SizeSquared() > FMath::Square(0.25f) || StickAim.SizeSquared() > FMath::Square(0.25f))
		{
			Attract->SkipToGameplay();
		}
	}

	UPoly99Simulation* Sim = GetWorld()->GetSubsystem<UPoly99Simulation>();
	if (!Sim)
	{
		return;
	}

	FVector2D Aim = FVector2D::ZeroVector;
	bool bFire = bFireHeld;
	if (StickAim.Size() >= StickFireThreshold)
	{
		Aim = StickAim.GetSafeNormal();
		bFire = true;
	}
	if (Aim.IsNearlyZero())
	{
		Aim = LastAim;
	}
	LastAim = Aim;

	Sim->SetInput(Move, Aim, bFire, bDashQueued);

	// Diagnostic. PS2 logs no analog message even at Verbose - the only labels it emits
	// are GAMEPAD_CONNECTED/PRESSED/RELEASED and the KEY_*/MOUSE_* ones - so there is no
	// way to tell from the streamer's log whether stick axes arrived. This does. Throttled
	// to 1 Hz and only while the sticks are off centre, so an idle session stays quiet.
	if (!Move.IsNearlyZero() || !StickAim.IsNearlyZero() || bFire)
	{
		const double Now = GetWorld()->GetTimeSeconds();
		if (Now - LastInputLogTime > 1.0)
		{
			LastInputLogTime = Now;
			UE_LOG(LogTemp, Log, TEXT("Input live: Move=(%.2f, %.2f) Aim=(%.2f, %.2f) Fire=%d Dash=%d"),
				Move.X, Move.Y, StickAim.X, StickAim.Y, bFire ? 1 : 0, bDashQueued ? 1 : 0);
		}
	}

	bDashQueued = false;
}
