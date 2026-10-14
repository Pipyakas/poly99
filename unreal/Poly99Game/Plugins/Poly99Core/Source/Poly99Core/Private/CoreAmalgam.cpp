// Compiles the shared poly99 core (<repo>/core) into this module so the core
// stays the single source of truth for the web (raylib) and UE builds.
#include "CoreMinimal.h"

THIRD_PARTY_INCLUDES_START
#include "poly99.cpp"
THIRD_PARTY_INCLUDES_END
