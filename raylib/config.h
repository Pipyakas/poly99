#pragma once

#include "core_api.h"

struct AppConfig {
    Poly99Config core;
    float designHeight;
    float minAspect;
    float maxAspect;
    float shootFreq;
    float hitFreq;
    float waveFreq;
};

void loadAppConfig(AppConfig& out);
