#include "raylib.h"

#include <cmath>
#include <cstdio>

#if defined(__EMSCRIPTEN__)
#include <emscripten.h>
#endif

#define DESIGN_HEIGHT 720.0f
#define MIN_ASPECT    (4.0f/3.0f)   // 4:3
#define MAX_ASPECT    (21.0f/9.0f)  // 21:9

static void SyncCanvasSizeToViewport(void)
{
#if defined(__EMSCRIPTEN__)
    int cssWidth = EM_ASM_INT({ return window.innerWidth; });
    int cssHeight = EM_ASM_INT({ return window.innerHeight; });
    if ((cssWidth != GetScreenWidth()) || (cssHeight != GetScreenHeight()))
    {
        SetWindowSize(cssWidth, cssHeight);
    }
#else
    (void)0;
#endif
}

int main(void)
{
    SetConfigFlags(FLAG_WINDOW_RESIZABLE);
    InitWindow(1280, 720, "poly99 - Raylib Engine");
    SetTargetFPS(60);

    while (!WindowShouldClose())
    {
        SyncCanvasSizeToViewport();

        const float screenWidth = (float)GetScreenWidth();
        const float screenHeight = (float)GetScreenHeight();

        // Design space: fixed height, width derived from the (clamped) aspect ratio.
        // 16:9 -> 1280x720, 4:3 -> 960x720, 3:2 -> 1080x720, 21:9 -> 1680x720.
        float aspect = screenWidth / screenHeight;
        aspect = fminf(fmaxf(aspect, MIN_ASPECT), MAX_ASPECT);
        const float designWidth = DESIGN_HEIGHT * aspect;
        const float designHeight = DESIGN_HEIGHT;

        const float scale = fminf(screenWidth / designWidth, screenHeight / designHeight);
        const Vector2 offset = {
            (screenWidth - designWidth * scale) * 0.5f,
            (screenHeight - designHeight * scale) * 0.5f
        };

        Camera2D camera = { 0 };
        camera.zoom = scale;
        camera.offset = offset;

        BeginDrawing();
        ClearBackground(BLACK);
        BeginMode2D(camera);

        for (int x = 0; x <= (int)designWidth; x += 160)
            DrawLine(x, 0, x, (int)designHeight, ColorAlpha(RAYWHITE, 0.12f));
        for (int y = 0; y <= (int)designHeight; y += 160)
            DrawLine(0, y, (int)designWidth, y, ColorAlpha(RAYWHITE, 0.12f));
        DrawRectangleLinesEx((Rectangle){ 0, 0, designWidth, designHeight }, 4.0f, RAYWHITE);

        DrawText("poly99 - adaptive arena", 20, 20, 30, RAYWHITE);

        char info[64];
        snprintf(info, sizeof(info), "design %.0fx%.0f  aspect %.2f", designWidth, designHeight, aspect);
        DrawText(info, 20, 60, 20, RAYWHITE);

        EndMode2D();
        EndDrawing();
    }

    CloseWindow();
    return 0;
}
