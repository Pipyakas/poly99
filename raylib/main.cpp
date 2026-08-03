#include "audio.h"
#include "config.h"
#include "core_api.h"
#include "input.h"
#include "raylib.h"
#include "renderer.h"
#include "ui.h"

#include <cmath>

#if defined(__EMSCRIPTEN__)
#include <emscripten.h>
#endif

#ifndef POLY99_DEFAULT_TOUCH
#define POLY99_DEFAULT_TOUCH 2
#endif

static void SyncCanvasSizeToViewport(void) {
#if defined(__EMSCRIPTEN__)
    int cssWidth = EM_ASM_INT({ return window.innerWidth; });
    int cssHeight = EM_ASM_INT({ return window.innerHeight; });
    if ((cssWidth != GetScreenWidth()) || (cssHeight != GetScreenHeight())) {
        SetWindowSize(cssWidth, cssHeight);
    }
#else
    (void)0;
#endif
}

static int countAlive(const Poly99Snapshot& s, int type) {
    int n = 0;
    for (int i = 0; i < POLY99_MAX_ENTITIES; i++) {
        if (s.entities[i].alive && s.entities[i].type == type) n++;
    }
    return n;
}

int main(void) {
    AppConfig app;
    loadAppConfig(app);

    SetConfigFlags(FLAG_WINDOW_RESIZABLE);
    InitWindow(1280, 720, "poly99 - Raylib Engine");
    InitAudioDevice();
    initAudioSfx(app.shootFreq, app.hitFreq, app.waveFreq);

    SetTargetFPS(60);

    SettingsData settings;
    uiInit(settings);
    SetMasterVolume(settings.masterVolume);

    unsigned int seed = (unsigned int)(GetTime() * 1000.0f) ^ 0x9E3779B9u;
    poly99_init(seed, &app.core);
    initTouchSetting(POLY99_DEFAULT_TOUCH);

    GameMode mode = GameMode::Play;

    int prevEnemies = 0;
    int prevBullets = 0;
    int prevWave = 1;

    while (!WindowShouldClose()) {
        const float dt = GetFrameTime();
        SyncCanvasSizeToViewport();

        const float screenW = (float)GetScreenWidth();
        const float screenH = (float)GetScreenHeight();
        float aspect = screenW / screenH;
        aspect = fminf(fmaxf(aspect, app.minAspect), app.maxAspect);
        const float designW = app.designHeight * aspect;
        const float designH = app.designHeight;

        poly99_set_arena(designW, designH);

        const float scale = fminf(screenW / designW, screenH / designH);
        const Vector2 offset = {
            (screenW - designW * scale) * 0.5f,
            (screenH - designH * scale) * 0.5f
        };
        Camera2D camera = { 0 };
        camera.zoom = scale;
        camera.offset = offset;

        Poly99Snapshot snap;
        poly99_get_snapshot(&snap);

        const bool touch = touchEnabled();

        uiUpdate(mode, settings, touch, snap.gameOver != 0);

        if (mode == GameMode::Play) {
            Poly99Input input = {};
            buildInput(input, camera, snap, touch);
            poly99_tick(dt, &input);
            poly99_get_snapshot(&snap);

            int enemies = countAlive(snap, POLY99_ET_ENEMY_GRASSHOPPER);
            int bullets = countAlive(snap, POLY99_ET_BULLET);
            if (bullets > prevBullets) playShoot();
            if (enemies < prevEnemies) playHit();
            if (snap.wave > prevWave) playWave();
            prevEnemies = enemies;
            prevBullets = bullets;
            prevWave = snap.wave;
        } else {
            SetMasterVolume(settings.masterVolume);
        }

        BeginDrawing();
        ClearBackground(BLACK);
        BeginMode2D(camera);
        drawArena(designW, designH, GetTime());
        drawEntities(snap, GetTime());
        EndMode2D();

        if (mode == GameMode::Play) {
            drawHUD(snap, touch);
            if (snap.gameOver) drawGameOver(snap, touch);
            else if (touch) drawTouchControls();
        }
        uiDraw(mode, settings, touch, snap.gameOver != 0);
        EndDrawing();
    }

    closeAudioSfx();
    CloseAudioDevice();
    CloseWindow();
    poly99_shutdown();
    return 0;
}
