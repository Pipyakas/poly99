#include "core_api.h"

#include <cmath>
#include <cstdio>
#include <cstring>

static int failures = 0;

#define CHECK(cond) do { \
    if (!(cond)) { std::printf("FAIL: %s (line %d)\n", #cond, __LINE__); failures++; } \
} while (0)

static const float kDt = 1.0f / 60.0f;

static Poly99Config makeConfig() {
    Poly99Config c = {};
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
    const unsigned char wc[4] = {255, 176, 0, 255};
    memcpy(c.playerColor, pc, 4);
    memcpy(c.bulletColor, bc, 4);
    memcpy(c.enemyColor, ec, 4);
    memcpy(c.wandererColor, wc, 4);
    c.dashSpeed = 1100.0f;
    c.dashDuration = 0.14f;
    c.dashCooldown = 0.8f;
    c.wandererSpeed = 90.0f;
    c.wandererRadius = 20.0f;
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

static float dist2(float ax, float ay, float bx, float by) {
    float dx = ax - bx, dy = ay - by;
    return std::sqrt(dx * dx + dy * dy);
}

static int countEvents(const Poly99Snapshot &s, int type) {
    int n = 0;
    for (int i = 0; i < s.eventCount; i++) {
        if (s.events[i].type == type) n++;
    }
    return n;
}

/* ------------------------------------------------------------------ */
/* Original smoke test: init, move, shoot, spawn, shutdown.           */
/* ------------------------------------------------------------------ */
static void testBaseline() {
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
    CHECK(s.dashing == 0);
    CHECK(s.dashCooldownRemaining == 0.0f);
    CHECK(s.events != NULL);
    CHECK(s.eventCount == 0);

    const Poly99Entity *player = findType(s, POLY99_ET_PLAYER);
    CHECK(player != NULL);
    CHECK(player->x > 630.0f && player->x < 650.0f);
    CHECK(player->y > 350.0f && player->y < 370.0f);

    Poly99Input in = {};
    in.moveX = 1.0f;
    in.moveY = 0.0f;
    float x0 = player->x;
    poly99_tick(kDt, &in);
    poly99_get_snapshot(&s);
    player = findType(s, POLY99_ET_PLAYER);
    CHECK(player->x > x0);

    in = {};
    in.aimX = 1.0f;
    in.aimY = 0.0f;
    in.firing = 1;
    poly99_tick(kDt, &in);
    poly99_get_snapshot(&s);
    CHECK(countType(s, POLY99_ET_BULLET) == 1);

    for (int i = 0; i < 90; i++) poly99_tick(kDt, &in);
    poly99_get_snapshot(&s);
    CHECK(countType(s, POLY99_ET_ENEMY_GRASSHOPPER) >= 1);
    /* No dashing without input, and the buffer never exceeds its cap. */
    CHECK(s.dashing == 0);
    CHECK(s.eventCount <= POLY99_MAX_EVENTS);

    poly99_shutdown();
    poly99_get_snapshot(&s);
    CHECK(s.entityCount == 0);
}

/* ------------------------------------------------------------------ */
/* Dash                                                                */
/* ------------------------------------------------------------------ */
static float travelDistance(bool useDash) {
    Poly99Config cfg = makeConfig();
    poly99_init(4242, &cfg);
    poly99_set_arena(1280, 720);

    Poly99Snapshot s;
    poly99_get_snapshot(&s);
    const Poly99Entity *p = findType(s, POLY99_ET_PLAYER);
    float x0 = p ? p->x : 0.0f;

    Poly99Input in = {};
    in.moveX = 1.0f;
    in.moveY = 0.0f;
    in.dash = useDash ? 1 : 0;
    for (int i = 0; i < 10; i++) poly99_tick(kDt, &in);
    poly99_get_snapshot(&s);
    p = findType(s, POLY99_ET_PLAYER);
    return p ? p->x - x0 : 0.0f;
}

static void testDashTravel() {
    float walked = travelDistance(false);
    float dashed = travelDistance(true);
    /* 0.167 s of walking at 300 px/s ~= 50 px; the same window with a
       0.14 s burst at 1100 px/s must be far larger. */
    CHECK(walked > 1.0f);
    CHECK(dashed > walked * 2.0f);
}

static void testDashFallsBackToAimThenFacing() {
    Poly99Config cfg = makeConfig();
    Poly99Snapshot s;

    /* No move input: the dash follows the aim vector. */
    poly99_init(31337, &cfg);
    poly99_set_arena(1280, 720);
    poly99_get_snapshot(&s);
    const Poly99Entity *p0 = findType(s, POLY99_ET_PLAYER);
    CHECK(p0 != NULL);
    float y0 = p0->y;
    Poly99Input in = {};
    in.aimX = 0.0f;
    in.aimY = 1.0f;
    in.dash = 1;
    poly99_tick(kDt, &in);
    poly99_get_snapshot(&s);
    p0 = findType(s, POLY99_ET_PLAYER);
    CHECK(s.dashing == 1);
    CHECK(p0->y > y0 + 5.0f);

    /* Neither move nor aim: the dash follows the facing direction. */
    poly99_init(31338, &cfg);
    poly99_set_arena(1280, 720);
    poly99_get_snapshot(&s);
    p0 = findType(s, POLY99_ET_PLAYER);
    CHECK(p0 != NULL);
    float x1 = p0->x, y1 = p0->y, rot = p0->rot;
    in = Poly99Input{};
    in.dash = 1;
    poly99_tick(kDt, &in);
    poly99_get_snapshot(&s);
    p0 = findType(s, POLY99_ET_PLAYER);
    float step = cfg.dashSpeed * kDt;
    CHECK(s.dashing == 1);
    CHECK(std::fabs((p0->x - x1) - std::cos(rot) * step) < 0.01f);
    CHECK(std::fabs((p0->y - y1) - std::sin(rot) * step) < 0.01f);
}

static void testDashCooldown() {
    Poly99Config cfg = makeConfig();
    poly99_init(555, &cfg);
    poly99_set_arena(1280, 720);

    Poly99Snapshot s;
    Poly99Input in = {};
    in.moveX = 1.0f;
    in.moveY = 0.0f;
    in.dash = 1;

    poly99_tick(kDt, &in);
    poly99_get_snapshot(&s);
    CHECK(s.dashing == 1);
    CHECK(s.dashCooldownRemaining > 0.0f);
    CHECK(countEvents(s, POLY99_EV_PLAYER_DASH) == 1);

    /* Holding the button does not re-trigger, and the burst ends on its own. */
    for (int i = 0; i < 20; i++) poly99_tick(kDt, &in);
    poly99_get_snapshot(&s);
    CHECK(s.dashing == 0);
    CHECK(s.dashCooldownRemaining > 0.0f);
    CHECK(countEvents(s, POLY99_EV_PLAYER_DASH) == 0);

    /* Release, then press again while still cooling down: no new burst. */
    in.dash = 0;
    poly99_tick(kDt, &in);
    in.dash = 1;
    poly99_tick(kDt, &in);
    poly99_get_snapshot(&s);
    CHECK(s.dashing == 0);
    CHECK(s.dashCooldownRemaining > 0.0f);

    /* Once the cooldown lapses the next rising edge dashes again. */
    int guard = 0;
    while (guard++ < 600) {
        in.dash = 0;
        poly99_tick(kDt, &in);
        poly99_get_snapshot(&s);
        if (s.dashCooldownRemaining <= 0.0f) break;
    }
    CHECK(s.dashCooldownRemaining == 0.0f);
    in.dash = 1;
    poly99_tick(kDt, &in);
    poly99_get_snapshot(&s);
    CHECK(s.dashing == 1);
}

static void testDashInvulnerable() {
    Poly99Config cfg = makeConfig();
    cfg.enemySpeed = 180.0f;
    cfg.enemyRadius = 120.0f; /* fat target so nothing tunnels through */
    poly99_init(777, &cfg);
    poly99_set_arena(1280, 720);

    Poly99Snapshot s;
    Poly99Input in = {};

    /* Let a grasshopper close in, stopping well before contact (sum of radii). */
    float gap = 1e9f;
    int clean = 1;
    for (int i = 0; i < 900; i++) {
        poly99_get_snapshot(&s);
        if (s.lives != 3) { clean = 0; break; }
        const Poly99Entity *p = findType(s, POLY99_ET_PLAYER);
        const Poly99Entity *e = findType(s, POLY99_ET_ENEMY_GRASSHOPPER);
        if (p && e) {
            gap = dist2(p->x, p->y, e->x, e->y);
            if (gap <= 250.0f) break;
        }
        poly99_tick(kDt, &in);
    }
    CHECK(clean == 1);
    CHECK(gap <= 250.0f);

    /* Dash straight into the oncoming enemy. */
    poly99_get_snapshot(&s);
    const Poly99Entity *p = findType(s, POLY99_ET_PLAYER);
    const Poly99Entity *e = findType(s, POLY99_ET_ENEMY_GRASSHOPPER);
    CHECK(p != NULL && e != NULL);
    if (!p || !e) return;

    float dx = e->x - p->x, dy = e->y - p->y;
    float len = std::sqrt(dx * dx + dy * dy);
    if (len < 0.001f) len = 1.0f;
    in.moveX = dx / len;
    in.moveY = dy / len;
    in.dash = 1;

    int overlapped = 0, hitWhileDashing = 0, survived = 0;
    for (int i = 0; i < 20; i++) {
        poly99_tick(kDt, &in);
        poly99_get_snapshot(&s);
        if (s.lives < 3 && s.dashing) hitWhileDashing = 1;
        if (s.lives == 3 && !s.dashing) survived = 1;
        const Poly99Entity *pp = findType(s, POLY99_ET_PLAYER);
        const Poly99Entity *ee = findType(s, POLY99_ET_ENEMY_GRASSHOPPER);
        if (s.dashing && pp && ee) {
            if (dist2(pp->x, pp->y, ee->x, ee->y) <= cfg.playerRadius + cfg.enemyRadius) overlapped = 1;
        }
    }
    CHECK(hitWhileDashing == 0); /* invulnerable for the whole burst */
    CHECK(survived == 1);        /* burst ended with all lives intact */
    CHECK(overlapped == 1);      /* the enemy really did touch the dashing player */

    /* Not invulnerable forever: it lands once the burst is over. */
    in.dash = 0;
    int hitAfter = 0;
    for (int i = 0; i < 300; i++) {
        poly99_tick(kDt, &in);
        poly99_get_snapshot(&s);
        if (s.lives < 3) { hitAfter = 1; break; }
    }
    CHECK(hitAfter == 1);
}

/* ------------------------------------------------------------------ */
/* Wanderer                                                            */
/* ------------------------------------------------------------------ */
static void testWanderer() {
    Poly99Config cfg = makeConfig();
    cfg.playerLives = 100000;
    /* The player sits in one very long burst, so it is invulnerable for the whole
       run: nothing ever dies, entity slots keep their identity, and the wanderer
       traffic is not disturbed by grasshoppers piling onto the player. */
    cfg.dashDuration = 1000.0f;
    cfg.dashCooldown = 1000.0f;
    cfg.enemySpawnCap = 40;
    cfg.spawnInterval = 0.05f;
    cfg.spawnIntervalMin = 0.02f;
    cfg.waveDuration = 0.5f; /* reach wave 2 almost immediately */

    poly99_init(9090, &cfg);
    poly99_set_arena(1280, 720);

    Poly99Snapshot s;
    Poly99Input in = {};
    in.dash = 1;

    /* Wanderers are spawned just outside the arena (like grasshoppers) and are
       pulled in on their first update, so only check ones that have been alive
       for at least two ticks. */
    int prev[POLY99_MAX_ENTITIES], settled[POLY99_MAX_ENTITIES];
    int prevCount = 0, settledCount = 0;
    int peak = 0, seen = 0, inside = 1;
    for (int i = 0; i < 1800; i++) {
        for (int k = 0; k < settledCount; k++) {
            const Poly99Entity &e = s.entities[settled[k]];
            if (!e.alive || e.type != POLY99_ET_ENEMY_WANDERER) continue;
            if (e.x < -0.001f || e.x > 1280.0f + 0.001f ||
                e.y < -0.001f || e.y > 720.0f + 0.001f) inside = 0;
        }

        poly99_tick(kDt, &in);
        poly99_get_snapshot(&s);

        int cur[POLY99_MAX_ENTITIES];
        int curCount = 0;
        for (int k = 0; k < POLY99_MAX_ENTITIES; k++) {
            if (!s.entities[k].alive || s.entities[k].type != POLY99_ET_ENEMY_WANDERER) continue;
            cur[curCount++] = k;
        }
        settledCount = 0;
        for (int a = 0; a < curCount; a++) {
            for (int b = 0; b < prevCount; b++) {
                if (cur[a] == prev[b]) { settled[settledCount++] = cur[a]; break; }
            }
        }
        prevCount = curCount;
        for (int a = 0; a < curCount; a++) prev[a] = cur[a];

        if (curCount > peak) peak = curCount;
        if (curCount > 0 && seen == 0) seen = 1;
        if (s.eventCount > POLY99_MAX_EVENTS) inside = 0;
    }
    CHECK(s.wave > 1);     /* the mix only turns on from wave 2 */
    CHECK(seen == 1);      /* wanderers really were spawned */
    CHECK(peak >= 3);
    CHECK(inside == 1);   /* never left the arena, and the event buffer never overran */
}

/* ------------------------------------------------------------------ */
/* Events                                                              */
/* ------------------------------------------------------------------ */
static void testEventsEnemyKilled() {
    Poly99Config cfg = makeConfig();
    cfg.enemyRadius = 60.0f;
    cfg.fireCooldown = 0.05f;
    cfg.enemySpeed = 60.0f;

    poly99_init(2468, &cfg);
    poly99_set_arena(1280, 720);

    Poly99Snapshot s;
    Poly99Input in = {};

    float known[64][2];
    int knownCount = 0;
    int killed = 0, matched = 0;

    for (int i = 0; i < 900 && !killed; i++) {
        poly99_get_snapshot(&s);
        /* Remember where every enemy was before this tick. */
        knownCount = 0;
        for (int k = 0; k < POLY99_MAX_ENTITIES && knownCount < 64; k++) {
            if (s.entities[k].alive && s.entities[k].type == POLY99_ET_ENEMY_GRASSHOPPER) {
                known[knownCount][0] = s.entities[k].x;
                known[knownCount][1] = s.entities[k].y;
                knownCount++;
            }
        }

        const Poly99Entity *p = findType(s, POLY99_ET_PLAYER);
        const Poly99Entity *e = findType(s, POLY99_ET_ENEMY_GRASSHOPPER);
        if (p && e) {
            float dx = e->x - p->x, dy = e->y - p->y;
            float len = std::sqrt(dx * dx + dy * dy);
            if (len > 0.001f) {
                in.aimX = dx / len;
                in.aimY = dy / len;
                in.firing = 1;
            }
        } else {
            in = Poly99Input{};
        }

        poly99_tick(kDt, &in);
        poly99_get_snapshot(&s);
        for (int k = 0; k < s.eventCount; k++) {
            if (s.events[k].type != POLY99_EV_ENEMY_KILLED) continue;
            if (!killed) {
                killed = 1;
                CHECK(s.events[k].entityType == POLY99_ET_ENEMY_GRASSHOPPER);
                float tol = cfg.enemySpeed * kDt * 2.0f + 4.0f;
                for (int j = 0; j < knownCount; j++) {
                    if (dist2(s.events[k].x, s.events[k].y, known[j][0], known[j][1]) <= tol) matched = 1;
                }
            }
        }
    }
    CHECK(killed == 1);   /* a bullet kill produced an event */
    CHECK(matched == 1);  /* reported at the enemy's position */
    CHECK(s.score > 0);   /* and awarded points */

    /* The buffer is per-tick: the kill event does not survive into the next one. */
    Poly99Input idle = {};
    poly99_tick(kDt, &idle);
    poly99_get_snapshot(&s);
    CHECK(countEvents(s, POLY99_EV_ENEMY_KILLED) == 0);
    CHECK(s.events == NULL ? 0 : 1);
    CHECK(s.eventCount <= POLY99_MAX_EVENTS);
}

static void testEventsWaveAndGameOver() {
    Poly99Config cfg = makeConfig();
    cfg.waveDuration = 0.05f;
    cfg.playerLives = 1;
    cfg.enemySpeed = 400.0f;

    poly99_init(1357, &cfg);
    poly99_set_arena(1280, 720);

    Poly99Snapshot s;
    Poly99Input in = {};

    int sawWave = 0;
    for (int i = 0; i < 600 && !sawWave; i++) {
        poly99_tick(kDt, &in);
        poly99_get_snapshot(&s);
        if (countEvents(s, POLY99_EV_WAVE_START)) {
            sawWave = 1;
            CHECK(s.wave == 2);
            for (int k = 0; k < s.eventCount; k++) {
                if (s.events[k].type == POLY99_EV_WAVE_START) {
                    CHECK(s.events[k].entityType == POLY99_ET_NONE);
                    CHECK(s.events[k].x > 0.0f && s.events[k].y > 0.0f);
                }
            }
        }
    }
    CHECK(sawWave == 1);

    int sawGameOver = 0;
    for (int i = 0; i < 900 && !sawGameOver; i++) {
        poly99_tick(kDt, &in);
        poly99_get_snapshot(&s);
        if (countEvents(s, POLY99_EV_GAME_OVER)) sawGameOver = 1;
    }
    CHECK(sawGameOver == 1);
    CHECK(s.gameOver == 1);
    CHECK(s.lives == 0);
}

static void testEventsOverflow() {
    Poly99Config cfg = makeConfig();
    /* A long dash parks the player against the top wall while it is invulnerable,
       so grasshoppers pile up on it instead of dying on contact. The instant the
       burst ends they all land at once: several hundred events in a single tick. */
    cfg.dashDuration = 8.0f;
    cfg.dashCooldown = 30.0f;
    cfg.invulnTime = 0.0f;
    cfg.playerLives = 100000;
    cfg.enemySpeed = 400.0f;
    cfg.enemyRadius = 60.0f;
    cfg.enemySpawnCap = 400;
    cfg.spawnInterval = kDt;
    cfg.spawnIntervalMin = kDt;
    cfg.waveDuration = 1000.0f; /* stay in wave 1 */

    poly99_init(8642, &cfg);
    poly99_set_arena(1280, 720);

    Poly99Snapshot s;
    Poly99Input in = {};
    in.aimX = 0.0f;
    in.aimY = 1.0f;
    in.dash = 1;

    for (int i = 0; i < 470; i++) poly99_tick(kDt, &in);
    poly99_get_snapshot(&s);
    CHECK(s.dashing == 1);
    CHECK(s.lives == cfg.playerLives);   /* nothing got through the dash */
    int piled = countType(s, POLY99_ET_ENEMY_GRASSHOPPER);
    CHECK(piled > POLY99_MAX_EVENTS / 2); /* enough to overrun the event buffer */

    /* Wait out the burst, then take the whole wave in one tick. */
    in.dash = 0;
    int startLives = s.lives;
    int spilled = 0;
    for (int i = 0; i < 600; i++) {
        poly99_tick(kDt, &in);
        poly99_get_snapshot(&s);
        if (s.eventCount >= POLY99_MAX_EVENTS) {
            spilled = 1;
            CHECK(s.eventCount == POLY99_MAX_EVENTS); /* capped, not overrun */
            CHECK(s.lives < startLives);
            break;
        }
    }
    CHECK(spilled == 1);
    CHECK(s.eventCount <= POLY99_MAX_EVENTS);
    CHECK(s.events != NULL);

    /* Still alive and ticking afterwards. */
    poly99_tick(kDt, &in);
    poly99_get_snapshot(&s);
    CHECK(s.eventCount <= POLY99_MAX_EVENTS);
    CHECK(countType(s, POLY99_ET_ENEMY_GRASSHOPPER) < piled);
}

int main() {
    testBaseline();
    testDashTravel();
    testDashFallsBackToAimThenFacing();
    testDashCooldown();
    testDashInvulnerable();
    testWanderer();
    testEventsEnemyKilled();
    testEventsWaveAndGameOver();
    testEventsOverflow();

    if (failures == 0) {
        std::printf("core_tests: ALL PASSED\n");
        return 0;
    }
    std::printf("core_tests: %d FAILURE(S)\n", failures);
    return 1;
}
