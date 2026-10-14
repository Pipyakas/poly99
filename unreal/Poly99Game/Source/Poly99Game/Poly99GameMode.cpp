#include "Poly99GameMode.h"

#include "Poly99EntityRenderer.h"
#include "Poly99HeroPawn.h"
#include "Poly99PlayerController.h"

APoly99GameMode::APoly99GameMode()
{
	DefaultPawnClass = APoly99HeroPawn::StaticClass();
	PlayerControllerClass = APoly99PlayerController::StaticClass();
	RendererClass = APoly99EntityRenderer::StaticClass();
}

void APoly99GameMode::StartPlay()
{
	if (UPoly99Simulation* Sim = GetWorld()->GetSubsystem<UPoly99Simulation>())
	{
		Sim->StartSimulation(CoreConfig, Seed != 0 ? Seed : FMath::Rand());
	}
	if (RendererClass)
	{
		GetWorld()->SpawnActor<APoly99EntityRenderer>(RendererClass);
	}
	Super::StartPlay();
}
