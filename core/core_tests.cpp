#include "core_api.h"

#include <cstdio>
#include <cstring>

static int failures = 0;

#define CHECK(cond) do { \
    if (!(cond)) { std::printf("FAIL: %s (line %d)\n", #cond, __LINE__); failures++; } \
} while (0)

static Poly99Config makeConfig() {
    Poly99Config c;
    c.playerSpeed = 300.0f;
    c.playerRadius = 14.0f;
    c.playerLives = 3;
    c.bulletSpeed = 700.0f;
    c.bulletRadius = 4.0f;
    c.fireCooldown = 0.15f;
    c.enemySpeed = 120.0f;
    c.enemyRadius = 16.0f;
    c.enemySpawnCap = 8;
    c.spawnInterval = 1.0f;
    c.spawnIntervalMin = 0.2f;
    c.waveDuration = 30.0f;
    c.invulnTime = 1.0f;
    const unsigned char pc[4] = {255, 255, 255, 255};
    const unsigned char bc[4] = {255, 0, 255, 255};
    const unsigned char ec[4] = {255, 80, 80, 255};
    memcpy(c.playerColor, pc, 4);
    memcpy(c.bulletColor, bc, 4);
    memcpy(c.enemyColor, ec, 4);
    return c;
}

static int countType(const Poly99Snapshot &s, int type) {
    int n = 0;
    for (int i = 0; i < POLY99_MAX_ENTITIES; i++) {
        if (s.entities[i].alive && s.entities[i].type == type) n++;
    }
    return n;
}

static const Poly99Entity *findType(const Poly99Snapshot &s, int type) {
    for (int i = 0; i < POLY99_MAX_ENTITIES; i++) {
        if (s.entities[i].alive && s.entities[i].type == type) return &s.entities[i];
    }
    return NULL;
}

int main() {
    Poly99Config cfg = makeConfig();
    poly99_init(12345, &cfg);
    poly99_set_arena(1280, 720);

    Poly99Snapshot s;
    poly99_get_snapshot(&s);
    CHECK(s.entityCount == 1);
    CHECK(countType(s, POLY99_ET_PLAYER) == 1);
    CHECK(s.score == 0);
    CHECK(s.wave == 1);
    CHECK(s.lives == 3);
    CHECK(!s.gameOver);

    const Poly99Entity *player = findType(s, POLY99_ET_PLAYER);
    CHECK(player != NULL);
    CHECK(player->x > 630.0f && player->x < 650.0f);
    CHECK(player->y > 350.0f && player->y < 370.0f);

    Poly99Input in = {};
    in.moveX = 1.0f;
    in.moveY = 0.0f;
    float x0 = player->x;
    poly99_tick(1.0f / 60.0f, &in);
    poly99_get_snapshot(&s);
    player = findType(s, POLY99_ET_PLAYER);
    CHECK(player->x > x0);

    in = {};
    in.aimX = 1.0f;
    in.aimY = 0.0f;
    in.firing = 1;
    poly99_tick(1.0f / 60.0f, &in);
    poly99_get_snapshot(&s);
    CHECK(countType(s, POLY99_ET_BULLET) == 1);

    for (int i = 0; i < 90; i++) poly99_tick(1.0f / 60.0f, &in);
    poly99_get_snapshot(&s);
    CHECK(countType(s, POLY99_ET_ENEMY_GRASSHOPPER) >= 1);

    poly99_shutdown();
    poly99_get_snapshot(&s);
    CHECK(s.entityCount == 0);

    if (failures == 0) {
        std::printf("core_tests: ALL PASSED\n");
        return 0;
    }
    std::printf("core_tests: %d FAILURE(S)\n", failures);
    return 1;
}
