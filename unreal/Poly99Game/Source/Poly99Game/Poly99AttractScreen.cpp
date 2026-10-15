#include "Poly99AttractScreen.h"

#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/TextBlock.h"
#include "Styling/CoreStyle.h"

namespace
{
	const FLinearColor TitleColor(0.93f, 0.95f, 0.99f);
	const FLinearColor SubtitleColor(0.45f, 0.56f, 0.72f);
	const FLinearColor PromptColor(0.42f, 0.86f, 1.0f);
	const FLinearColor HintColor(0.60f, 0.66f, 0.76f);
	const FLinearColor FooterColor(0.34f, 0.39f, 0.48f);

	FSlateFontInfo FontAt(int32 Size)
	{
		// GetDefaultFont() returns a TSharedRef<FCompositeFont>, which FSlateFontInfo has no
		// constructor for; GetDefaultFontStyle is the overload that returns one already.
		return FCoreStyle::GetDefaultFontStyle(FName(), static_cast<float>(Size));
	}
}

bool UPoly99AttractScreen::Initialize()
{
	if (!Super::Initialize())
	{
		return false;
	}

	UCanvasPanel* Canvas = WidgetTree->ConstructWidget<UCanvasPanel>();

	// A text line centred horizontally at YAnchor, aligned VAlign along its own height.
	auto AddLine = [&](float YAnchor, float VAlign, const FString& Text, int32 Size,
		const FLinearColor& Color) -> UTextBlock*
	{
		UTextBlock* T = WidgetTree->ConstructWidget<UTextBlock>();
		T->SetText(FText::FromString(Text));
		T->SetFont(FontAt(Size));
		T->SetColorAndOpacity(FSlateColor(Color));
		// The attract screen is decoration; it must never eat input the game wants.
		T->SetVisibility(ESlateVisibility::HitTestInvisible);

		UCanvasPanelSlot* Slot = Canvas->AddChildToCanvas(T);
		Slot->SetAnchors(FAnchors(0.5f, YAnchor, 0.5f, YAnchor));
		Slot->SetAlignment(FVector2D(0.5f, VAlign));
		Slot->SetAutoSize(true);
		Slot->SetZOrder(10);
		return T;
	};

	// Full-screen scrim, kept light: the hero and arena are the point, the text just has to
	// stay legible over whatever the camera happens to be framing.
	UBorder* Scrim = WidgetTree->ConstructWidget<UBorder>();
	Scrim->SetBrushColor(FLinearColor(0.02f, 0.03f, 0.05f, 0.58f));
	Scrim->SetVisibility(ESlateVisibility::HitTestInvisible);
	UCanvasPanelSlot* ScrimSlot = Canvas->AddChildToCanvas(Scrim);
	ScrimSlot->SetAnchors(FAnchors(0.f, 0.f, 1.f, 1.f));
	ScrimSlot->SetAlignment(FVector2D(0.f, 0.f));
	ScrimSlot->SetOffsets(FMargin(0.f));
	ScrimSlot->SetZOrder(0);

	AddLine(0.30f, 0.5f, TEXT("POLY99"), 108, TitleColor);
	AddLine(0.40f, 0.0f, TEXT("DASH  ·  WANDER  ·  SURVIVE"), 26, SubtitleColor);

	Prompt = AddLine(0.62f, 0.0f, TEXT("PRESS  A  TO  START"), 34, PromptColor);

	AddLine(0.74f, 0.0f,
		TEXT("LEFT STICK — MOVE          RIGHT STICK — AIM\n"
			 "RT — FIRE          LT / RB — DASH          Y — HELMET"),
		20, HintColor);

	AddLine(0.94f, 1.0f, TEXT("streamed live from D1"), 16, FooterColor);

	Root = Canvas;
	WidgetTree->RootWidget = Canvas;
	return true;
}

void UPoly99AttractScreen::NativeTick(const FGeometry& MyGeometry, float InDeltaTime)
{
	Super::NativeTick(MyGeometry, InDeltaTime);

	Time += InDeltaTime;
	if (Prompt)
	{
		// Breathe rather than blink - a hard on/off flash is harsh at 120 Hz.
		const float Pulse = 0.55f + 0.45f * FMath::Sin(Time * 2.2f);
		Prompt->SetColorAndOpacity(FSlateColor(FLinearColor(
			PromptColor.R, PromptColor.G, PromptColor.B, Pulse * (1.f - Fade))));
	}
}

void UPoly99AttractScreen::SetFade(float InAlpha)
{
	Fade = FMath::Clamp(InAlpha, 0.f, 1.f);
	SetRenderOpacity(1.f - Fade);
}