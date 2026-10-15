#pragma once

#include "Blueprint/UserWidget.h"
#include "Poly99AttractScreen.generated.h"

class UTextBlock;
class UWidget;

/**
 * Attract screen overlay: title, prompt and control hints.
 *
 * Built entirely in C++ - this project has no Widget Blueprint assets. UUserWidget's
 * Initialize() creates the WidgetTree before RebuildWidget() runs, so the tree is
 * assembled there rather than in NativeConstruct (which is too late: by then the Slate
 * widget has already been generated from the tree).
 */
UCLASS()
class POLY99GAME_API UPoly99AttractScreen : public UUserWidget
{
	GENERATED_BODY()

public:
	virtual bool Initialize() override;
	virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

	/** 0 = fully visible, 1 = gone. Faded as the handover to gameplay begins. */
	void SetFade(float InAlpha);

private:
	UPROPERTY(Transient)
	TObjectPtr<UWidget> Root;

	/** The blinking "press start" line - the only thing that animates. */
	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> Prompt;

	float Time = 0.f;
	float Fade = 0.f;
};