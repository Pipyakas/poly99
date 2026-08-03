#pragma once

#include "core_api.h"
#include "raylib.h"

void drawArena(float designW, float designH, float time);
void drawEntities(const Poly99Snapshot& snap, float time);
void drawHUD(const Poly99Snapshot& snap, bool touch);
void drawGameOver(const Poly99Snapshot& snap, bool touch);
