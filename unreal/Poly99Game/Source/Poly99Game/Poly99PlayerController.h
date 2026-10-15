#pragma once

#include "GameFramework/PlayerController.h"
#include "Poly99PlayerController.generated.h"

class UInputAction;
class UInputMappingContext;
struct FInputActionValue;

/**
 * Twin-stick input -> poly99 core. Gamepad only (owner requirement): the mouse is never
 * captured and the cursor stays free. Mappings are built in code (no input assets):
 * left stick move, right stick aim (+ auto-fire past StickFireThreshold), RT fire,
 * LT / RB dash, Y helmet toggle. Agents drive tests via UPoly99Simulation::SetInputOverride.
 */
UCLASS()
class POLY99GAME_API APoly99PlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	APoly99PlayerController();

	virtual void PlayerTick(float DeltaTime) override;

	/** Right-stick magnitude above which the hero auto-fires. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float StickFireThreshold = 0.35f;

protected:
	virtual void SetupInputComponent() override;
	virtual void BeginPlay() override;

private:
	/** Hands the view back from the attract screen to gameplay. Idempotent. */
	void SkipAttract();

	UInputAction* MakeAction(FName Name, int32 ValueType);
	void OnMoveX(const FInputActionValue& Value);
	void OnMoveY(const FInputActionValue& Value);
	void OnAimX(const FInputActionValue& Value);
	void OnAimY(const FInputActionValue& Value);
	void OnFire(const FInputActionValue& Value);
	void OnFireStop(const FInputActionValue& Value);
	void OnDash(const FInputActionValue& Value);
	void OnToggleHelmet(const FInputActionValue& Value);
	void OnStart(const FInputActionValue& Value);

	UPROPERTY(Transient)
	TObjectPtr<UInputMappingContext> Mapping;

	// Sticks are four separate 1D actions, not two 2D ones: Pixel Streaming only
	// injects the per-axis FKeys and nothing synthesises Gamepad_Left2D/Right2D.
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> MoveXAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> MoveYAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> AimXAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> AimYAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> FireAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> DashAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> HelmetAction;

	/** A button on the pad - the "PRESS A" on the attract screen. */
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> StartAction;

	bool bHelmetPressed = false;

	FVector2D Move = FVector2D::ZeroVector;
	FVector2D StickAim = FVector2D::ZeroVector;

	/** Throttle for the "Input live:" diagnostic in PlayerTick. */
	double LastInputLogTime = -1000.0;
	FVector2D LastAim = FVector2D(1.f, 0.f);
	bool bFireHeld = false;
	bool bDashQueued = false;
};
