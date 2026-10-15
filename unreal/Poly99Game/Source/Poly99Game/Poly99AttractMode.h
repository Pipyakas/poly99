#pragma once

#include "GameFramework/Actor.h"
#include "Poly99AttractMode.generated.h"

class ACameraActor;
class APlayerController;
class UPoly99AttractScreen;

/**
 * The attract screen: a slow cinematic orbit of the hero, with the title overlay, shown
 * until the player gives input.
 *
 * This is what D1 shows from boot. Over Pixel Streaming the client connects long before
 * the player touches a stick, so the screen is the thing you actually look at while the
 * game is up - it needs to look deliberate rather than being a paused game.
 *
 * The handover is on INPUT, not on connect. Exiting when the player joins would mean the
 * screen lasted about as long as it took to click "Click to start", which is no better
 * than not having one.
 */
UCLASS()
class POLY99GAME_API APoly99AttractMode : public AActor
{
	GENERATED_BODY()

public:
	APoly99AttractMode();

	/** Handover to gameplay: fade out, give the camera back, fade in. Safe to call twice. */
	UFUNCTION(BlueprintCallable, Category = "poly99")
	void SkipToGameplay();

	UFUNCTION(BlueprintPure, Category = "poly99")
	bool IsAttracting() const { return bAttracting; }

	/** The attract actor for this world, if one is running. */
	static APoly99AttractMode* Get(UWorld* World);

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

	/** Degrees per second around the hero. Slow enough to read as a camera move, not a spin. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float OrbitSpeed = 9.f;

	/** Close enough that the hero is the subject. At the gameplay spring arm length (2600)
	 *  the hero is ~7% of frame height against a bright arena floor and reads as a speck. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float Radius = 1250.f;

	/** Low enough to keep the camera near the hero rather than looking down at the whole map. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float Height = 640.f;

	/** Radius and height breathe on different periods so the move never visibly repeats. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float RadiusWobble = 0.10f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float HeightWobble = 150.f;

	/** Seconds for the fade out and back in. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float FadeSeconds = 0.45f;

	/** Z offset of the aim point relative to the hero's chest. Positive looks above him,
	 *  which pushes the hero down in frame. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float AimRise = 40.f;

	/** Lateral aim offset, in UU, perpendicular to the view. Aiming left of the hero pushes
	 *  the hero to the RIGHT of frame, clear of the centred title and prompt. Negative moves
	 *  the aim point left. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "poly99")
	float AimSide = -560.f;

private:
	/** What the camera films: the hero if it exists, else this actor. */
	FVector FocusPoint() const;

	/** Creates the camera and screen once a player controller exists to own them. */
	void EnsureStarted();

	APlayerController* FirstPlayer() const;

	UPROPERTY(Transient)
	TObjectPtr<ACameraActor> Camera;

	UPROPERTY(Transient)
	TObjectPtr<UPoly99AttractScreen> Screen;

	bool bAttracting = true;
	bool bStarted = false;
	float Time = 0.f;
	float Angle = 0.f;

	enum class EPhase : uint8 { Idle, Running, FadingOut, HandingOver };
	EPhase Phase = EPhase::Idle;
	float FadeElapsed = 0.f;
};