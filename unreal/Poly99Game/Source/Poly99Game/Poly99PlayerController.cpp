#include "Poly99PlayerController.h"

#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"
#include "Poly99HeroAppearanceComponent.h"
#include "Poly99HeroPawn.h"
#include "Poly99Simulation.h"

namespace
{
	// Our action space: X = forward (screen up), Y = right.
	void AddSwizzle(FEnhancedActionKeyMapping& M, UObject* Outer)
	{
		UInputModifierSwizzleAxis* S = NewObject<UInputModifierSwizzleAxis>(Outer);
		S->Order = EInputAxisSwizzle::YXZ;
		M.Modifiers.Add(S);
	}


	void AddDeadZone(FEnhancedActionKeyMapping& M, UObject* Outer)
	{
		UInputModifierDeadZone* D = NewObject<UInputModifierDeadZone>(Outer);
		D->LowerThreshold = 0.2f;
		M.Modifiers.Add(D);
	}

	/** Stick 2D gives X = right, Y = up; swap into (forward, right). */
	void MapStick(UInputMappingContext* Ctx, UInputAction* Action, FKey Key, UObject* Outer)
	{
		FEnhancedActionKeyMapping& M = Ctx->MapKey(Action, Key);
		AddDeadZone(M, Outer);
		AddSwizzle(M, Outer);
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
	if (UEnhancedInputLocalPlayerSubsystem* Sub = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer()))
	{
		Sub->AddMappingContext(Mapping, 0);
	}
}

void APoly99PlayerController::SetupInputComponent()
{
	Super::SetupInputComponent();

	MoveAction = MakeAction(TEXT("IA_Move"), static_cast<int32>(EInputActionValueType::Axis2D));
	AimAction = MakeAction(TEXT("IA_Aim"), static_cast<int32>(EInputActionValueType::Axis2D));
	FireAction = MakeAction(TEXT("IA_Fire"), static_cast<int32>(EInputActionValueType::Boolean));
	DashAction = MakeAction(TEXT("IA_Dash"), static_cast<int32>(EInputActionValueType::Boolean));
	HelmetAction = MakeAction(TEXT("IA_ToggleHelmet"), static_cast<int32>(EInputActionValueType::Boolean));

	Mapping = NewObject<UInputMappingContext>(this, TEXT("IMC_Poly99"));

	MapStick(Mapping, MoveAction, EKeys::Gamepad_Left2D, this);
	MapStick(Mapping, AimAction, EKeys::Gamepad_Right2D, this);

	Mapping->MapKey(FireAction, EKeys::Gamepad_RightTrigger);
	Mapping->MapKey(DashAction, EKeys::Gamepad_LeftTrigger);
	Mapping->MapKey(DashAction, EKeys::Gamepad_RightShoulder);
	Mapping->MapKey(HelmetAction, EKeys::Gamepad_FaceButton_Top);

	UEnhancedInputComponent* EIC = CastChecked<UEnhancedInputComponent>(InputComponent);
	EIC->BindAction(MoveAction, ETriggerEvent::Triggered, this, &APoly99PlayerController::OnMove);
	EIC->BindAction(MoveAction, ETriggerEvent::Completed, this, &APoly99PlayerController::OnMoveStop);
	EIC->BindAction(AimAction, ETriggerEvent::Triggered, this, &APoly99PlayerController::OnAim);
	EIC->BindAction(AimAction, ETriggerEvent::Completed, this, &APoly99PlayerController::OnAimStop);
	EIC->BindAction(FireAction, ETriggerEvent::Started, this, &APoly99PlayerController::OnFire);
	EIC->BindAction(FireAction, ETriggerEvent::Completed, this, &APoly99PlayerController::OnFireStop);
	EIC->BindAction(DashAction, ETriggerEvent::Started, this, &APoly99PlayerController::OnDash);
	EIC->BindAction(HelmetAction, ETriggerEvent::Started, this, &APoly99PlayerController::OnToggleHelmet);
}

void APoly99PlayerController::OnMove(const FInputActionValue& Value) { Move = Value.Get<FVector2D>(); }
void APoly99PlayerController::OnMoveStop(const FInputActionValue&) { Move = FVector2D::ZeroVector; }

void APoly99PlayerController::OnAim(const FInputActionValue& Value) { StickAim = Value.Get<FVector2D>(); }
void APoly99PlayerController::OnAimStop(const FInputActionValue&) { StickAim = FVector2D::ZeroVector; }
void APoly99PlayerController::OnFire(const FInputActionValue&) { bFireHeld = true; }
void APoly99PlayerController::OnFireStop(const FInputActionValue&) { bFireHeld = false; }
void APoly99PlayerController::OnDash(const FInputActionValue&) { bDashQueued = true; }

void APoly99PlayerController::OnToggleHelmet(const FInputActionValue&)
{
	if (APoly99HeroPawn* Hero = GetPawn<APoly99HeroPawn>())
	{
		Hero->GetAppearance()->ToggleHelmet();
	}
}

void APoly99PlayerController::PlayerTick(float DeltaTime)
{
	Super::PlayerTick(DeltaTime);

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
	bDashQueued = false;
}
