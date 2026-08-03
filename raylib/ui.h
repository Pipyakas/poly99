#pragma once

#include "raylib.h"

enum class GameMode {
    Play,
    Paused,
    Settings
};

struct SettingsData {
    float masterVolume;
    bool  fullscreen;
};

void uiInit(SettingsData& s);
void uiUpdate(GameMode& mode, SettingsData& s, bool touch, bool gameOver);
void uiDraw(GameMode mode, const SettingsData& s, bool touch, bool gameOver);
