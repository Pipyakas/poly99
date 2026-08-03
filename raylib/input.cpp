#include "input.h"

#include <cmath>

#if defined(__EMSCRIPTEN__)
#include <emscripten.h>
#endif

namespace {

int effectiveTouch = 0;

struct Stick {
    bool active = false;
    Vector2 anchor = { 0, 0 };
    Vector2 current = { 0, 0 };
};

Stick moveStick;
Stick aimStick;
const float stickMax = 60.0f;
const float matchRadius = 90.0f;

Vector2 stickAxis(const Stick& s) {
    Vector2 d = { s.current.x - s.anchor.x, s.current.y - s.anchor.y };
    float len = sqrtf(d.x * d.x + d.y * d.y);
    if (len < 8.0f) return { 0, 0 };
    float clamped = fminf(len, stickMax) / stickMax;
    return { d.x / len * clamped, d.y / len * clamped };
}

void updateTouchSticks() {
    const int maxTouches = 8;
    Vector2 touches[maxTouches];
    bool claimed[maxTouches] = { false };
    int count = GetTouchPointCount();
    if (count > maxTouches) count = maxTouches;
    for (int i = 0; i < count; i++) touches[i] = GetTouchPosition(i);

    const float screenW = (float)GetScreenWidth();

    Stick* sticks[2] = { &moveStick, &aimStick };
    bool matched[2] = { false, false };

    for (int si = 0; si < 2; si++) {
        if (!sticks[si]->active) continue;
        int best = -1;
        float bestDist = matchRadius * matchRadius;
        for (int i = 0; i < count; i++) {
            if (claimed[i]) continue;
            float dx = touches[i].x - sticks[si]->anchor.x;
            float dy = touches[i].y - sticks[si]->anchor.y;
            float d2 = dx * dx + dy * dy;
            if (d2 <= bestDist) { bestDist = d2; best = i; }
        }
        if (best >= 0) {
            claimed[best] = true;
            sticks[si]->current = touches[best];
            matched[si] = true;
        } else {
            sticks[si]->active = false;
        }
    }

    if (moveStick.active && !matched[0]) moveStick.active = false;
    if (aimStick.active && !matched[1]) aimStick.active = false;

    for (int i = 0; i < count; i++) {
        if (claimed[i]) continue;
        if (!moveStick.active && touches[i].x < screenW * 0.5f) {
            moveStick = { true, touches[i], touches[i] };
            claimed[i] = true;
            continue;
        }
        if (!aimStick.active && touches[i].x >= screenW * 0.5f) {
            aimStick = { true, touches[i], touches[i] };
            claimed[i] = true;
        }
    }
}

} // namespace

void initTouchSetting(int defaultMode) {
    int stored = -1;
#if defined(__EMSCRIPTEN__)
    stored = EM_ASM_INT({
        if (typeof localStorage === 'undefined') return -1;
        var s = localStorage.getItem('poly99_touch');
        if (s === null || s === '') return -1;
        return parseInt(s, 10) ? 1 : 0;
    });
#endif
    if (stored >= 0) { effectiveTouch = stored; return; }

    if (defaultMode == 2) {
#if defined(__EMSCRIPTEN__)
        effectiveTouch = EM_ASM_INT({
            var ua = navigator.userAgent || '';
            if (navigator.maxTouchPoints > 0 || ('ontouchstart' in window) || (ua.indexOf('Android') >= 0)) return 1;
            return 0;
        });
#else
        effectiveTouch = 0;
#endif
    } else {
        effectiveTouch = defaultMode;
    }
}

bool touchEnabled() { return effectiveTouch == 1; }

void toggleTouchSetting() {
    effectiveTouch = effectiveTouch ? 0 : 1;
#if defined(__EMSCRIPTEN__)
    EM_ASM({
        if (typeof localStorage !== 'undefined') {
            localStorage.setItem('poly99_touch', $0 ? '1' : '0');
        }
    }, effectiveTouch);
#endif
}

void buildInput(Poly99Input& out, const Camera2D& camera, const Poly99Snapshot& snap, bool touch) {
    out = Poly99Input{};

    float moveX = 0.0f, moveY = 0.0f;
    if (IsKeyDown(KEY_W) || IsKeyDown(KEY_UP)) moveY -= 1.0f;
    if (IsKeyDown(KEY_S) || IsKeyDown(KEY_DOWN)) moveY += 1.0f;
    if (IsKeyDown(KEY_A) || IsKeyDown(KEY_LEFT)) moveX -= 1.0f;
    if (IsKeyDown(KEY_D) || IsKeyDown(KEY_RIGHT)) moveX += 1.0f;

    float gx = GetGamepadAxisMovement(0, GAMEPAD_AXIS_LEFT_X);
    float gy = GetGamepadAxisMovement(0, GAMEPAD_AXIS_LEFT_Y);
    if (fabsf(gx) > 0.1f || fabsf(gy) > 0.1f) { moveX = gx; moveY = gy; }

    out.moveX = moveX;
    out.moveY = moveY;

    if (touch) {
        updateTouchSticks();
        Vector2 m = stickAxis(moveStick);
        Vector2 a = stickAxis(aimStick);
        out.moveX += m.x;
        out.moveY += m.y;
        out.aimX += a.x;
        out.aimY += a.y;
        if (a.x != 0.0f || a.y != 0.0f) out.firing = 1;
    } else {
        const Poly99Entity* player = nullptr;
        for (int i = 0; i < POLY99_MAX_ENTITIES; i++) {
            if (snap.entities[i].alive && snap.entities[i].type == POLY99_ET_PLAYER) { player = &snap.entities[i]; break; }
        }
        if (player) {
            Vector2 mouseWorld = GetScreenToWorld2D(GetMousePosition(), camera);
            float dx = mouseWorld.x - player->x;
            float dy = mouseWorld.y - player->y;
            float len = sqrtf(dx * dx + dy * dy);
            if (len > 1.0f) {
                out.aimX = dx / len;
                out.aimY = dy / len;
            }
        }
        float rx = GetGamepadAxisMovement(0, GAMEPAD_AXIS_RIGHT_X);
        float ry = GetGamepadAxisMovement(0, GAMEPAD_AXIS_RIGHT_Y);
        if (fabsf(rx) > 0.1f || fabsf(ry) > 0.1f) { out.aimX = rx; out.aimY = ry; }

        out.firing = IsMouseButtonDown(MOUSE_BUTTON_LEFT) || IsKeyDown(KEY_SPACE) || IsKeyDown(KEY_Z) ||
                     IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_TRIGGER_1) ||
                     IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_FACE_DOWN);
    }

    if (snap.gameOver) {
        static int prevTouches = 0;
        int tc = GetTouchPointCount();
        bool tap = (tc > prevTouches) && tc > 0;
        prevTouches = tc;
        out.restart = IsKeyPressed(KEY_ENTER) || IsMouseButtonPressed(MOUSE_BUTTON_LEFT) || tap;
    }
}

void drawTouchControls() {
    const Color base = { 255, 255, 255, 40 };
    const Color knob = { 255, 255, 255, 160 };
    Stick* sticks[2] = { &moveStick, &aimStick };
    for (int i = 0; i < 2; i++) {
        Stick& s = *sticks[i];
        if (!s.active) continue;
        DrawCircleV(s.anchor, stickMax, base);
        DrawCircleLines((int)s.anchor.x, (int)s.anchor.y, (int)stickMax, base);
        DrawCircleV(s.current, 20.0f, knob);
        DrawCircleLines((int)s.current.x, (int)s.current.y, 20, knob);
    }
}
