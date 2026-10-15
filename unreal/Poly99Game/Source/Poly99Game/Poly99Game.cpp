#include "Modules/ModuleManager.h"

#include "Poly99RenderFeatures.h"

/**
 * Applies the render feature toggles once at module load. The CVars are already set from
 * DefaultEngine.ini before this runs, so this re-asserts them at SetByCode priority, which is
 * what stops a later scalability change from quietly switching a feature the owner turned off.
 */
class FPoly99GameModule : public FDefaultGameModuleImpl
{
public:
	virtual void StartupModule() override
	{
		FDefaultGameModuleImpl::StartupModule();
		UPoly99RenderFeatures::ApplyAll();
		UPoly99RenderFeatures::LogState();
	}
};

IMPLEMENT_PRIMARY_GAME_MODULE(FPoly99GameModule, Poly99Game, "Poly99Game");