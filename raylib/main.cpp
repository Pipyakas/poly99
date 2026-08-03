#include "raylib.h"

#include <cmath>

#if defined(__EMSCRIPTEN__)
#include <emscripten.h>
#endif

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

    const float logicalWidth = 1280.0f;
    const float logicalHeight = 720.0f;

    while (!WindowShouldClose())
    {
        SyncCanvasSizeToViewport();

        const float screenWidth = (float)GetScreenWidth();
        const float screenHeight = (float)GetScreenHeight();
        const float scale = fminf(screenWidth/logicalWidth, screenHeight/logicalHeight);
        const Vector2 offset = {
            (screenWidth - logicalWidth*scale)*0.5f,
            (screenHeight - logicalHeight*scale)*0.5f
        };
        const Camera2D camera = { 0 };
        camera.zoom = scale;
        camera.offset = offset;

        BeginDrawing();
        ClearBackground(BLACK);
        BeginMode2D(camera);
        DrawText("poly99 - hello from raylib!", 20, 20, 30, RAYWHITE);
        EndMode2D();
        EndDrawing();
    }

    CloseWindow();
    return 0;
}
