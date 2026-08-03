#include "ui.h"

#include "audio.h"
#include "input.h"

#include <cmath>

#if defined(__EMSCRIPTEN__)
#include <emscripten.h>
#endif

namespace {

int prevTouchCount = 0;
int pauseSel = 0;
int settingsSel = 0;

int flashRow = -1;
float flashTimer = 0.0f;

bool pointInRect(Vector2 p, Rectangle r) {
    return p.x >= r.x && p.x <= r.x + r.width && p.y >= r.y && p.y <= r.y + r.height;
}

bool isPointerOver(Rectangle r) {
    if (pointInRect(GetMousePosition(), r)) return true;
    int tc = GetTouchPointCount();
    for (int i = 0; i < tc; i++) {
        if (pointInRect(GetTouchPosition(i), r)) return true;
    }
    return false;
}

bool isPointerDown(Rectangle r) {
    if (IsMouseButtonDown(MOUSE_BUTTON_LEFT) && pointInRect(GetMousePosition(), r)) return true;
    int tc = GetTouchPointCount();
    for (int i = 0; i < tc; i++) {
        if (pointInRect(GetTouchPosition(i), r)) return true;
    }
    return false;
}

bool pointerTap(Rectangle r, Vector2& out) {
    if (IsMouseButtonPressed(MOUSE_BUTTON_LEFT) && pointInRect(GetMousePosition(), r)) {
        out = GetMousePosition();
        return true;
    }
    int tc = GetTouchPointCount();
    if (tc > prevTouchCount && tc > 0) {
        Vector2 t = GetTouchPosition(0);
        if (pointInRect(t, r)) { out = t; return true; }
    }
    return false;
}

#if defined(__EMSCRIPTEN__)
float localGetFloat(const char* key, float def) {
    return (float)EM_ASM_DOUBLE({
        if (typeof localStorage === 'undefined') return $1;
        var v = localStorage.getItem(UTF8ToString($0));
        return (v === null || v === '') ? $1 : parseFloat(v);
    }, key, (double)def);
}
int localGetInt(const char* key, int def) {
    return EM_ASM_INT({
        if (typeof localStorage === 'undefined') return $1;
        var v = localStorage.getItem(UTF8ToString($0));
        return (v === null || v === '') ? $1 : parseInt(v, 10);
    }, key, def);
}
void localSetFloat(const char* key, float v) {
    EM_ASM({
        if (typeof localStorage !== 'undefined') localStorage.setItem(UTF8ToString($0), $1.toString());
    }, key, (double)v);
}
void localSetInt(const char* key, int v) {
    EM_ASM({
        if (typeof localStorage !== 'undefined') localStorage.setItem(UTF8ToString($0), $1.toString());
    }, key, v);
}
#else
float localGetFloat(const char*, float def) { return def; }
int localGetInt(const char*, int def) { return def; }
void localSetFloat(const char*, float) {}
void localSetInt(const char*, int) {}
#endif

Rectangle centerPanel(float w, float h) {
    return { (GetScreenWidth() - w) * 0.5f, (GetScreenHeight() - h) * 0.5f, w, h };
}

void drawOverlay() {
    DrawRectangle(0, 0, GetScreenWidth(), GetScreenHeight(), (Color){ 0, 0, 0, 170 });
}

void drawPanel(Rectangle r) {
    DrawRectangleRec(r, (Color){ 10, 10, 12, 238 });
    DrawRectangleLinesEx(r, 2.0f, (Color){ 0, 255, 255, 150 });
}

void drawRowBase(Rectangle r, bool selected, int row) {
    bool hovered = isPointerOver(r);
    bool pressed = isPointerDown(r);
    bool flash = (flashTimer > 0.0f) && (flashRow == row);

    Color fill = { 255, 255, 255, 14 };
    if (pressed) fill = (Color){ 0, 255, 255, 90 };
    else if (hovered || selected || flash) fill = (Color){ 0, 255, 255, 40 };

    DrawRectangleRec(r, fill);
    if (flash) {
        DrawRectangleLinesEx(r, 3.0f, (Color){ 255, 255, 255, 220 });
    } else if (selected) {
        DrawRectangleLinesEx(r, 2.0f, (Color){ 0, 255, 255, 220 });
    } else if (hovered) {
        DrawRectangleLinesEx(r, 2.0f, (Color){ 0, 255, 255, 120 });
    }
}

void triggerFlash(int row) {
    flashRow = row;
    flashTimer = 0.15f;
    playUiClick();
}

void drawLabel(Rectangle r, const char* label, const char* value) {
    DrawText(label, (int)r.x + 16, (int)r.y + (int)(r.height - 24) / 2, 22, RAYWHITE);
    if (value) {
        int w = MeasureText(value, 22);
        DrawText(value, (int)(r.x + r.width - w - 16), (int)r.y + (int)(r.height - 24) / 2, 22, (Color){ 0, 255, 255, 220 });
    }
}

Rectangle pauseButtonRect() {
    return { GetScreenWidth() - 56.0f, 16.0f, 40.0f, 40.0f };
}

void drawPauseButton() {
    Rectangle r = pauseButtonRect();
    bool over = isPointerOver(r);
    bool down = isPointerDown(r);
    DrawRectangleRec(r, down ? (Color){ 0, 255, 255, 70 } : over ? (Color){ 255, 255, 255, 45 } : (Color){ 255, 255, 255, 30 });
    DrawRectangleLinesEx(r, 2.0f, over ? (Color){ 0, 255, 255, 200 } : (Color){ 255, 255, 255, 120 });
    DrawRectangle((int)r.x + 12, (int)r.y + 10, 6, 20, RAYWHITE);
    DrawRectangle((int)r.x + 22, (int)r.y + 10, 6, 20, RAYWHITE);
}

// ---- Pause menu ----

void updatePauseMenu(GameMode& mode) {
    const int n = 2;
    if (IsKeyPressed(KEY_UP) || IsKeyPressed(KEY_W)) pauseSel = (pauseSel + n - 1) % n;
    if (IsKeyPressed(KEY_DOWN) || IsKeyPressed(KEY_S)) pauseSel = (pauseSel + 1) % n;

    Rectangle panel = centerPanel(420, 200);
    float rowH = 56;
    Rectangle btnResume = { panel.x + 40, panel.y + 70, panel.width - 80, rowH };
    Rectangle btnSettings = { btnResume.x, btnResume.y + rowH + 14, btnResume.width, rowH };

    if (IsKeyPressed(KEY_ENTER) || IsKeyPressed(KEY_SPACE)) {
        if (pauseSel == 0) { mode = GameMode::Play; return; }
        settingsSel = 0;
        triggerFlash(1);
        mode = GameMode::Settings;
        return;
    }
    Vector2 tap;
    if (pointerTap(btnResume, tap)) { triggerFlash(0); mode = GameMode::Play; return; }
    if (pointerTap(btnSettings, tap)) { settingsSel = 0; triggerFlash(1); mode = GameMode::Settings; return; }
}

void drawPauseMenu() {
    drawOverlay();
    Rectangle panel = centerPanel(420, 200);
    drawPanel(panel);

    int titleW = MeasureText("PAUSED", 34);
    DrawText("PAUSED", (int)(panel.x + (panel.width - titleW) / 2), (int)panel.y + 20, 34, RAYWHITE);

    float rowH = 56;
    Rectangle btnResume = { panel.x + 40, panel.y + 70, panel.width - 80, rowH };
    Rectangle btnSettings = { btnResume.x, btnResume.y + rowH + 14, btnResume.width, rowH };

    drawRowBase(btnResume, pauseSel == 0, 0);
    drawLabel(btnResume, "Resume", nullptr);
    drawRowBase(btnSettings, pauseSel == 1, 1);
    drawLabel(btnSettings, "Settings", nullptr);
}

// ---- Settings menu ----

void updateSettingsMenu(GameMode& mode, SettingsData& s) {
    const int n = 4;
    if (IsKeyPressed(KEY_UP) || IsKeyPressed(KEY_W)) settingsSel = (settingsSel + n - 1) % n;
    if (IsKeyPressed(KEY_DOWN) || IsKeyPressed(KEY_S)) settingsSel = (settingsSel + 1) % n;

    Rectangle panel = centerPanel(440, 320);
    float rowH = 50;
    float x = panel.x + 36;
    float w = panel.width - 72;
    float y = panel.y + 66;
    Rectangle rows[4];
    for (int i = 0; i < 4; i++) {
        rows[i] = { x, y + i * (rowH + 12), w, rowH };
    }

    if (IsKeyPressed(KEY_LEFT) && settingsSel == 1) s.masterVolume = fmaxf(0.0f, s.masterVolume - 0.05f);
    if (IsKeyPressed(KEY_RIGHT) && settingsSel == 1) s.masterVolume = fminf(1.0f, s.masterVolume + 0.05f);

    if (IsKeyPressed(KEY_ENTER) || IsKeyPressed(KEY_SPACE)) {
        if (settingsSel == 0) { triggerFlash(0); toggleTouchSetting(); }
        else if (settingsSel == 2) { triggerFlash(2); s.fullscreen = !s.fullscreen; ToggleFullscreen(); }
        else if (settingsSel == 3) { triggerFlash(3); mode = GameMode::Paused; return; }
    }

    Vector2 tap;
    if (pointerTap(rows[0], tap)) { triggerFlash(0); toggleTouchSetting(); }
    if (pointerTap(rows[2], tap)) { triggerFlash(2); s.fullscreen = !s.fullscreen; ToggleFullscreen(); }
    if (pointerTap(rows[3], tap)) { triggerFlash(3); mode = GameMode::Paused; return; }

    Rectangle track = { rows[1].x + 150, rows[1].y + (rowH - 8) / 2, rows[1].width - 220, 8 };
    bool drag = IsMouseButtonDown(MOUSE_BUTTON_LEFT) && pointInRect(GetMousePosition(), track);
    if (pointerTap(track, tap) || drag) {
        Vector2 p = drag ? GetMousePosition() : tap;
        s.masterVolume = fminf(1.0f, fmaxf(0.0f, (p.x - track.x) / track.width));
        if (!drag) triggerFlash(1);
    }

    localSetFloat("poly99_volume", s.masterVolume);
    localSetInt("poly99_fullscreen", s.fullscreen ? 1 : 0);
}

void drawSettingsMenu(const SettingsData& s, bool touch) {
    drawOverlay();
    Rectangle panel = centerPanel(440, 320);
    drawPanel(panel);

    int titleW = MeasureText("SETTINGS", 34);
    DrawText("SETTINGS", (int)(panel.x + (panel.width - titleW) / 2), (int)panel.y + 20, 34, RAYWHITE);

    float rowH = 50;
    float x = panel.x + 36;
    float w = panel.width - 72;
    float y = panel.y + 66;

    Rectangle touchRow = { x, y, w, rowH };
    drawRowBase(touchRow, settingsSel == 0, 0);
    drawLabel(touchRow, "Touch Controls", touch ? "ON" : "OFF");

    Rectangle volRow = { x, y + (rowH + 12), w, rowH };
    drawRowBase(volRow, settingsSel == 1, 1);
    drawLabel(volRow, "Volume", TextFormat("%d%%", (int)(s.masterVolume * 100.0f)));
    Rectangle track = { x + 150, volRow.y + (rowH - 8) / 2, w - 220, 8 };
    DrawRectangleRec(track, (Color){ 255, 255, 255, 40 });
    float fillW = track.width * s.masterVolume;
    if (fillW > 0) DrawRectangleRec((Rectangle){ track.x, track.y, fillW, track.height }, (Color){ 0, 255, 255, 220 });
    bool volActive = settingsSel == 1 || isPointerOver(track);
    DrawCircleV((Vector2){ track.x + fillW, track.y + track.height / 2 }, volActive ? 8.0f : 7.0f, (Color){ 0, 255, 255, (unsigned char)(volActive ? 255 : 220) });

    Rectangle fsRow = { x, y + 2 * (rowH + 12), w, rowH };
    drawRowBase(fsRow, settingsSel == 2, 2);
    drawLabel(fsRow, "Fullscreen", s.fullscreen ? "ON" : "OFF");

    Rectangle backRow = { x, y + 3 * (rowH + 12), w, rowH };
    drawRowBase(backRow, settingsSel == 3, 3);
    drawLabel(backRow, "Back", nullptr);
}

} // namespace

void uiInit(SettingsData& s) {
    s.masterVolume = localGetFloat("poly99_volume", 1.0f);
    s.masterVolume = fminf(1.0f, fmaxf(0.0f, s.masterVolume));
    s.fullscreen = localGetInt("poly99_fullscreen", 0) != 0;
    if (s.fullscreen) ToggleFullscreen();
}

void uiUpdate(GameMode& mode, SettingsData& s, bool touch, bool gameOver) {
    int tc = GetTouchPointCount();
    prevTouchCount = tc;

    if (flashTimer > 0.0f) flashTimer -= GetFrameTime();

    bool pauseRequest = IsKeyPressed(KEY_ESCAPE) || IsKeyPressed(KEY_P);
    if (touch) {
        Vector2 tap;
        pauseRequest = pauseRequest || pointerTap(pauseButtonRect(), tap);
    }

    if (mode == GameMode::Play) {
        if (!gameOver && pauseRequest) {
            pauseSel = 0;
            triggerFlash(0);
            mode = GameMode::Paused;
        }
    } else if (mode == GameMode::Paused) {
        if (pauseRequest) { mode = GameMode::Play; return; }
        updatePauseMenu(mode);
    } else { // Settings
        if (pauseRequest) { mode = GameMode::Paused; return; }
        updateSettingsMenu(mode, s);
    }
}

void uiDraw(GameMode mode, const SettingsData& s, bool touch, bool gameOver) {
    if (mode == GameMode::Play) {
        if (touch && !gameOver) drawPauseButton();
        return;
    }
    if (mode == GameMode::Paused) drawPauseMenu();
    else drawSettingsMenu(s, touchEnabled());
}
