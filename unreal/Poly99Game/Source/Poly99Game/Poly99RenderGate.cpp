#include "Poly99RenderGate.h"

#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "HAL/FileManager.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"

namespace
{
	TAutoConsoleVariable<int32> CVarPoly99RenderOnlyWhenStreamed(
		TEXT("Poly99.RenderOnlyWhenStreamed"), 1,
		TEXT("Stop rendering the world while nobody is watching the Pixel Streaming stream. ")
		TEXT("1 = on, 0 = always render. Fails open (renders anyway) if the viewer count file ")
		TEXT("cannot be read, so a dead watcher costs GPU rather than a black screen."));

	TAutoConsoleVariable<FString> CVarPoly99ViewerCountFile(
		TEXT("Poly99.ViewerCountFile"),
		TEXT("/var/mnt/ssd2/pixel-streaming/viewers"),
		TEXT("File holding the current viewer count as a single integer. Written by ")
		TEXT("pipeline/tools/pixel-streaming.sh from Wilbur's player registration log lines."));

	/** Seconds after which the count file is treated as stale, i.e. the watcher is dead. */
	constexpr double StalenessLimitSeconds = 5.0;
	constexpr double PollIntervalSeconds = 0.25;

	TAutoConsoleVariable<int32> CVarPoly99IdleFrameRate(
		TEXT("Poly99.IdleFrameRate"), 1,
		TEXT("Frames per second to cap the engine at while nobody is watching the stream. ")
		TEXT("0 = do not cap. Pixel Streaming captures through UE's MediaCapture, which ")
		TEXT("renders its own view, so bDisableWorldRendering alone barely dents idle GPU."));

	FPoly99RenderGate GRenderGate;
} // namespace

bool FPoly99RenderGate::IsTickable() const
{
	return CVarPoly99RenderOnlyWhenStreamed.GetValueOnGameThread() != 0
		&& GEngine != nullptr
		&& GEngine->GameViewport != nullptr;
}

bool FPoly99RenderGate::ReadViewerCount(int32& OutCount) const
{
	const FString Path = CVarPoly99ViewerCountFile.GetValueOnGameThread();

	// GetTimeStamp returns MinValue() for a path that does not exist.
	const FDateTime Written = IFileManager::Get().GetTimeStamp(*Path);
	if (Written == FDateTime::MinValue())
	{
		return false;
	}
	if ((FDateTime::UtcNow() - Written).GetTotalSeconds() > StalenessLimitSeconds)
	{
		return false;
	}

	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *Path))
	{
		return false;
	}
	Text.TrimStartAndEndInline();
	OutCount = FCString::Atoi(*Text);
	return true;
}

void FPoly99RenderGate::ApplyRenderState(bool bShouldRender, int32 Viewers)
{
	if (bRenderingEnabled == bShouldRender)
	{
		return;
	}
	bRenderingEnabled = bShouldRender;

	if (UGameViewportClient* Viewport = GEngine->GameViewport)
	{
		Viewport->bDisableWorldRendering = !bShouldRender;
	}

	// The frame cap is what actually saves the GPU: PS2 pulls frames through
	// UMediaCapture, which drives its own view render and is not gated by
	// bDisableWorldRendering. Capping the engine loop throttles that path too.
	const int32 IdleFps = CVarPoly99IdleFrameRate.GetValueOnGameThread();
	GEngine->SetMaxFPS(bShouldRender ? 0.0f : static_cast<float>(FMath::Max(0, IdleFps)));

	UE_LOG(LogTemp, Log,
		TEXT("RenderGate: world rendering %s, frame cap %s (%d viewer(s) on '%s')"),
		bShouldRender ? TEXT("enabled") : TEXT("disabled"),
		bShouldRender ? TEXT("off") : *FString::FromInt(IdleFps),
		Viewers, *CVarPoly99ViewerCountFile.GetValueOnGameThread());
}

void FPoly99RenderGate::Tick(float DeltaTime)
{
	const double Now = FPlatformTime::Seconds();
	if (Now < NextPollTime)
	{
		return;
	}
	NextPollTime = Now + PollIntervalSeconds;

	if (CVarPoly99RenderOnlyWhenStreamed.GetValueOnGameThread() == 0)
	{
		ApplyRenderState(true, 0);
		bLoggedOnce = false;
		return;
	}

	int32 Viewers = 0;
	if (!ReadViewerCount(Viewers))
	{
		// No trustworthy count. Render, and say so once so a black screen is never a mystery.
		ApplyRenderState(true, 0);
		// Repeat this one, not just log it once. This branch means the gate is failing OPEN -
		// the game renders at full speed with nothing on screen saying why. It happened on
		// 2026-10-15 (game CPU 264%, GPU pinned, no stream) purely because the viewer watcher
		// had died, and the only clue was a single line scrolled far out of view. The
		// supervisor in pixel-streaming.sh now restarts the watcher; this makes the state
		// obvious in a `tail` if it ever happens again.
		if (Now - LastNoCountWarnTime > NoCountWarnIntervalSeconds)
		{
			LastNoCountWarnTime = Now;
			UE_LOG(LogTemp, Warning,
				TEXT("RenderGate: no viewer count at '%s' - RENDERING AT FULL SPEED with no viewer. ")
				TEXT("If nobody is streaming, the viewer watcher is down; run 'pixel-streaming.sh start'."),
				*CVarPoly99ViewerCountFile.GetValueOnGameThread());
		}
		return;
	}

	bLoggedOnce = true;
	ApplyRenderState(Viewers > 0, Viewers);
}