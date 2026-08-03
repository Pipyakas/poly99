#include "raylib.h"

int main(void) {
    const int screenWidth = 1280;
    const int screenHeight = 720;

    InitWindow(screenWidth, screenHeight, "poly99 - Raylib Engine");
    SetTargetFPS(60);

    while (!WindowShouldClose()) {
        BeginDrawing();
        ClearBackground(BLACK);
        DrawText("poly99 - hello from raylib!", 20, 20, 30, RAYWHITE);
        EndDrawing();
    }

    CloseWindow();
    return 0;
}
