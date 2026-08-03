#include "renderer.h"

#include <cmath>

namespace {

Color withAlpha(Color c, float a) {
    Color out = c;
    out.a = (unsigned char)(c.a * a);
    return out;
}

void drawTriangleGlow(Vector2 center, float rot, float r, Color c) {
    const int layers = 5;
    Vector2 tip = { center.x + cosf(rot) * r, center.y + sinf(rot) * r };
    Vector2 b1 = { center.x + cosf(rot + 2.4f) * r, center.y + sinf(rot + 2.4f) * r };
    Vector2 b2 = { center.x + cosf(rot - 2.4f) * r, center.y + sinf(rot - 2.4f) * r };

    for (int i = layers; i >= 1; i--) {
        float s = 1.0f + i * 0.4f;
        float a = 0.12f * (1.0f - (float)i / (float)layers);
        Vector2 t = { center.x + cosf(rot) * r * s, center.y + sinf(rot) * r * s };
        Vector2 u = { center.x + cosf(rot + 2.4f) * r * s, center.y + sinf(rot + 2.4f) * r * s };
        Vector2 v = { center.x + cosf(rot - 2.4f) * r * s, center.y + sinf(rot - 2.4f) * r * s };
        DrawTriangle(t, u, v, withAlpha(c, a));
    }
    DrawTriangle(tip, b1, b2, withAlpha(c, 0.25f));
    DrawTriangleLines(tip, b1, b2, c);
}

void drawDiamondGlow(Vector2 center, float rot, float r, Color c) {
    const int layers = 5;
    for (int i = layers; i >= 1; i--) {
        float rr = r + i * 6.0f;
        float a = 0.10f * (1.0f - (float)i / (float)layers);
        DrawPoly(center, 4, rr, rot * 180.0f / (float)PI + 45.0f, withAlpha(c, a));
    }
    DrawPolyLinesEx(center, 4, r, rot * 180.0f / (float)PI + 45.0f, 2.0f, c);
}

void drawCircleGlow(Vector2 center, float r, Color c) {
    const int layers = 4;
    for (int i = layers; i >= 1; i--) {
        float rr = r + i * 4.0f;
        float a = 0.12f * (1.0f - (float)i / (float)layers);
        DrawCircleLines((int)center.x, (int)center.y, rr, withAlpha(c, a));
    }
    DrawCircleV(center, r, c);
}

} // namespace

void drawArena(float designW, float designH, float time) {
    DrawRectangle(0, 0, (int)designW, (int)designH, (Color){ 35, 35, 35, 255 });

    Color grid = { 60, 60, 80, 40 };
    for (int x = 0; x <= (int)designW; x += 160) DrawLine(x, 0, x, (int)designH, grid);
    for (int y = 0; y <= (int)designH; y += 160) DrawLine(0, y, (int)designW, y, grid);

    float pulse = 0.5f + 0.5f * sinf(time * 2.0f);
    Color border = { 0, 255, 255, (unsigned char)(120 + 80 * pulse) };
    DrawRectangleLinesEx((Rectangle){ 0, 0, designW, designH }, 3.0f, border);
}

void drawEntities(const Poly99Snapshot& snap, float time) {
    for (int i = 0; i < POLY99_MAX_ENTITIES; i++) {
        const Poly99Entity& e = snap.entities[i];
        if (!e.alive) continue;
        Color c = { e.r, e.g, e.b, e.a };
        Vector2 pos = { e.x, e.y };
        switch (e.type) {
            case POLY99_ET_PLAYER:
                drawTriangleGlow(pos, e.rot, e.radius, c);
                break;
            case POLY99_ET_BULLET:
                drawCircleGlow(pos, e.radius, c);
                break;
            case POLY99_ET_ENEMY_GRASSHOPPER:
                drawDiamondGlow(pos, e.rot, e.radius, c);
                break;
            default:
                break;
        }
    }
}

void drawHUD(const Poly99Snapshot& snap, bool touch) {
    DrawText(TextFormat("SCORE %06d", snap.score), 16, 16, 24, RAYWHITE);
    DrawText(TextFormat("WAVE %d", snap.wave), 16, 46, 24, RAYWHITE);
    DrawText(TextFormat("LIVES %d", snap.lives), 16, 76, 24, RAYWHITE);
    const char* mode = touch ? "JOY ON  [T]" : "JOY OFF  [T]";
    DrawText(mode, GetScreenWidth() - 200, 16, 20, GRAY);
}

void drawGameOver(const Poly99Snapshot& snap, bool touch) {
    DrawRectangle(0, 0, GetScreenWidth(), GetScreenHeight(), (Color){ 0, 0, 0, 180 });
    const char* msg = "GAME OVER";
    int w = MeasureText(msg, 60);
    DrawText(msg, (GetScreenWidth() - w) / 2, GetScreenHeight() / 2 - 80, 60, RED);

    const char* scoreLine = TextFormat("SCORE %d   WAVE %d", snap.score, snap.wave);
    int w2 = MeasureText(scoreLine, 24);
    DrawText(scoreLine, (GetScreenWidth() - w2) / 2, GetScreenHeight() / 2, 24, RAYWHITE);

    const char* hint = touch ? "Tap to restart" : "Press Enter to restart";
    int w3 = MeasureText(hint, 20);
    DrawText(hint, (GetScreenWidth() - w3) / 2, GetScreenHeight() / 2 + 40, 20, GRAY);
}
