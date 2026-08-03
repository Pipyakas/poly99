#pragma once

#include "core_api.h"
#include "raylib.h"

void initTouchSetting(int defaultMode);
bool touchEnabled();
void toggleTouchSetting();
void buildInput(Poly99Input& out, const Camera2D& camera, const Poly99Snapshot& snap, bool touch);
void drawTouchControls();
