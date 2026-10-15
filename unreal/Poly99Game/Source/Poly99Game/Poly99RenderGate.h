#pragma once

#include "CoreMinimal.h"
#include "Tickable.h"

/**
 * Stops the world render while nobody is watching the stream.
 *
 * Pixel Streaming 2 has no "render on demand" switch, and neither does the engine:
 * UGameViewportClient::Draw runs the full scene render every tick as long as the app
 * ticks. The closest supported stop is UGameViewportClient::bDisableWorldRendering,
 * which skips the world render entirely (Lumen, Nanite, shadows, post) and leaves only
 * a canvas clear - see GameViewportClient.cpp, the `if (!bDisableWorldRendering ...)`
 * guards around the player views.
 *
 * The viewer count comes from a small file that pipeline/tools/pixel-streaming.sh
 * keeps up to date by counting player registrations in Wilbur's log. PS2 itself only
 * exposes IsConnected()/IsStreaming(), and both are true from boot because streaming
 * is auto-started, so neither one means "somebody is actually watching".
 *
 * Fail-open on purpose: if the file is missing or stale, rendering stays on. A broken
 * watcher must cost GPU, never a black screen for someone who is watching.
 */
class FPoly99RenderGate final : public FTickableGameObject
{
public:
	virtual void Tick(float DeltaTime) override;
	virtual bool IsTickable() const override;
	virtual bool IsTickableWhenPaused() const override { return true; }
	virtual bool IsTickableInEditor() const override { return false; }
	virtual TStatId GetStatId() const override
	{
		RETURN_QUICK_DECLARE_CYCLE_STAT(FPoly99RenderGate, STATGROUP_Tickables);
	}

	/** Reads the viewer count file. False if it is absent or older than the staleness limit. */
	bool ReadViewerCount(int32& OutCount) const;

private:
	void ApplyRenderState(bool bShouldRender, int32 Viewers);

	double NextPollTime = 0.0;
	bool bRenderingEnabled = true;
	bool bLoggedOnce = false;

	/** Throttles the "rendering with no viewer count" warning; see the Tick comment. */
	double LastNoCountWarnTime = -1000.0;
	static constexpr double NoCountWarnIntervalSeconds = 30.0;
};