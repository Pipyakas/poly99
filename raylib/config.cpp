#include "config.h"

#include "json.h"
#include "raylib.h"

#include <cstdio>
#include <cstring>
#include <string>

namespace {

void fillDefaults(AppConfig& out) {
    Poly99Config& c = out.core;
    c.playerSpeed = 300.0f;
    c.playerRadius = 14.0f;
    c.playerLives = 3;
    c.bulletSpeed = 700.0f;
    c.bulletRadius = 4.0f;
    c.fireCooldown = 0.12f;
    c.enemySpeed = 130.0f;
    c.enemyRadius = 15.0f;
    c.enemySpawnCap = 10;
    c.spawnInterval = 1.0f;
    c.spawnIntervalMin = 0.25f;
    c.waveDuration = 30.0f;
    c.invulnTime = 1.0f;
    const unsigned char player[4] = {255, 255, 255, 255};
    const unsigned char bullet[4] = {57, 255, 20, 255};
    const unsigned char enemy[4] = {255, 59, 59, 255};
    const unsigned char wanderer[4] = {255, 176, 0, 255};
    memcpy(c.playerColor, player, 4);
    memcpy(c.bulletColor, bullet, 4);
    memcpy(c.enemyColor, enemy, 4);
    memcpy(c.wandererColor, wanderer, 4);
    c.dashSpeed = 1100.0f;
    c.dashDuration = 0.14f;
    c.dashCooldown = 0.8f;
    c.wandererSpeed = 90.0f;
    c.wandererRadius = 20.0f;
    out.designHeight = 720.0f;
    out.minAspect = 1.3333f;
    out.maxAspect = 2.3333f;
    out.shootFreq = 880.0f;
    out.hitFreq = 180.0f;
    out.waveFreq = 440.0f;
}

float readNum(const polyjson::Value& obj, const char* key, float def) {
    const polyjson::Value* v = obj.get(key);
    return v ? (float)v->asNumber(def) : def;
}

void readColor(const polyjson::Value& obj, const char* key, unsigned char out[4]) {
    const polyjson::Value* v = obj.get(key);
    if (!v || !v->isString()) return;
    unsigned int r = 0, g = 0, b = 0;
    if (sscanf(v->asString().c_str(), "#%02x%02x%02x", &r, &g, &b) == 3) {
        out[0] = (unsigned char)r;
        out[1] = (unsigned char)g;
        out[2] = (unsigned char)b;
        out[3] = 255;
    }
}

} // namespace

void loadAppConfig(AppConfig& out) {
    fillDefaults(out);

    int len = 0;
    unsigned char* data = LoadFileData("config/game.json", &len);
    if (!data || len <= 0) {
        if (data) UnloadFileData(data);
        return;
    }
    std::string text((const char*)data, (size_t)len);
    UnloadFileData(data);

    polyjson::Value root;
    std::string error;
    if (!polyjson::parse(text, root, error)) {
        TraceLog(LOG_WARNING, "config parse failed: %s", error.c_str());
        return;
    }

    const polyjson::Value* player = root.get("player");
    const polyjson::Value* bullet = root.get("bullet");
    const polyjson::Value* enemy = root.get("enemy");
    const polyjson::Value* wanderer = root.get("wanderer");
    const polyjson::Value* spawn = root.get("spawn");
    const polyjson::Value* audio = root.get("audio");

    if (player) {
        out.core.playerSpeed = readNum(*player, "speed", out.core.playerSpeed);
        out.core.playerRadius = readNum(*player, "radius", out.core.playerRadius);
        out.core.playerLives = (int)readNum(*player, "lives", (float)out.core.playerLives);
        out.core.dashSpeed = readNum(*player, "dashSpeed", out.core.dashSpeed);
        out.core.dashDuration = readNum(*player, "dashDuration", out.core.dashDuration);
        out.core.dashCooldown = readNum(*player, "dashCooldown", out.core.dashCooldown);
        readColor(*player, "color", out.core.playerColor);
    }
    if (bullet) {
        out.core.bulletSpeed = readNum(*bullet, "speed", out.core.bulletSpeed);
        out.core.bulletRadius = readNum(*bullet, "radius", out.core.bulletRadius);
        out.core.fireCooldown = readNum(*bullet, "cooldown", out.core.fireCooldown);
        readColor(*bullet, "color", out.core.bulletColor);
    }
    if (enemy) {
        out.core.enemySpeed = readNum(*enemy, "speed", out.core.enemySpeed);
        out.core.enemyRadius = readNum(*enemy, "radius", out.core.enemyRadius);
        out.core.enemySpawnCap = (int)readNum(*enemy, "spawnCap", (float)out.core.enemySpawnCap);
        readColor(*enemy, "color", out.core.enemyColor);
    }
    if (wanderer) {
        out.core.wandererSpeed = readNum(*wanderer, "speed", out.core.wandererSpeed);
        out.core.wandererRadius = readNum(*wanderer, "radius", out.core.wandererRadius);
        readColor(*wanderer, "color", out.core.wandererColor);
    }
    if (spawn) {
        out.core.spawnInterval = readNum(*spawn, "interval", out.core.spawnInterval);
        out.core.spawnIntervalMin = readNum(*spawn, "intervalMin", out.core.spawnIntervalMin);
        out.core.waveDuration = readNum(*spawn, "waveDuration", out.core.waveDuration);
    }
    out.core.invulnTime = readNum(root, "invulnTime", out.core.invulnTime);
    out.designHeight = readNum(root, "designHeight", out.designHeight);
    out.minAspect = readNum(root, "minAspect", out.minAspect);
    out.maxAspect = readNum(root, "maxAspect", out.maxAspect);
    if (audio) {
        out.shootFreq = readNum(*audio, "shoot", out.shootFreq);
        out.hitFreq = readNum(*audio, "hit", out.hitFreq);
        out.waveFreq = readNum(*audio, "wave", out.waveFreq);
    }
}
