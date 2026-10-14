#include "poly99.h"

#include <math.h>
#include <stddef.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace {

GameState g;

unsigned int nextRand(unsigned int *state) {
    *state ^= *state << 13;
    *state ^= *state >> 17;
    *state ^= *state << 5;
    return *state;
}

float randFloat(unsigned int *state) {
    return (float)(nextRand(state) & 0x00FFFFFF) / 16777215.0f;
}

int findFreeSlot() {
    for (int i = 0; i < POLY99_MAX_ENTITIES; i++) {
        if (!g.entities[i].alive) return i;
    }
    return -1;
}

Poly99Entity *spawn(int type) {
    int slot = findFreeSlot();
    if (slot < 0) return NULL;
    Poly99Entity *e = &g.entities[slot];
    e->type = type;
    e->alive = 1;
    g.entityCount++;
    return e;
}

void kill(Poly99Entity *e) {
    if (e->alive) {
        e->alive = 0;
        g.entityCount--;
    }
}

/* Fixed-size event ring for the frontend. Overflow silently drops events. */
void pushEvent(int type, float x, float y, int entityType,
               unsigned char cr, unsigned char cg, unsigned char cb, unsigned char ca) {
    if (g.eventCount >= POLY99_MAX_EVENTS) return;
    Poly99Event *ev = &g.events[g.eventCount++];
    ev->type = type;
    ev->x = x;
    ev->y = y;
    ev->entityType = entityType;
    ev->r = cr;
    ev->g = cg;
    ev->b = cb;
    ev->a = ca;
}

int isEnemyType(int type) {
    return type == POLY99_ET_ENEMY_GRASSHOPPER || type == POLY99_ET_ENEMY_WANDERER;
}

/* 0 = other, 1 = player, 2 = bullet, 3 = enemy */
int collisionClass(int type) {
    if (type == POLY99_ET_PLAYER) return 1;
    if (type == POLY99_ET_BULLET) return 2;
    if (isEnemyType(type)) return 3;
    return 0;
}

int enemyScoreValue(int type) {
    return type == POLY99_ET_ENEMY_WANDERER ? 20 : 10;
}

void spawnBullet(float x, float y, float angle) {
    Poly99Entity *b = spawn(POLY99_ET_BULLET);
    if (!b) return;
    b->x = x;
    b->y = y;
    b->vx = cosf(angle) * g.config.bulletSpeed;
    b->vy = sinf(angle) * g.config.bulletSpeed;
    b->radius = g.config.bulletRadius;
    b->rot = angle;
    b->r = g.config.bulletColor[0];
    b->g = g.config.bulletColor[1];
    b->b = g.config.bulletColor[2];
    b->a = g.config.bulletColor[3];
}

void spawnGrasshopper(float x, float y) {
    Poly99Entity *e = spawn(POLY99_ET_ENEMY_GRASSHOPPER);
    if (!e) return;
    e->x = x;
    e->y = y;
    e->vx = 0.0f;
    e->vy = 0.0f;
    e->radius = g.config.enemyRadius;
    e->rot = 0.0f;
    e->r = g.config.enemyColor[0];
    e->g = g.config.enemyColor[1];
    e->b = g.config.enemyColor[2];
    e->a = g.config.enemyColor[3];
}

void spawnWanderer(float x, float y) {
    Poly99Entity *e = spawn(POLY99_ET_ENEMY_WANDERER);
    if (!e) return;
    e->x = x;
    e->y = y;
    float angle = randFloat(&g.randState) * 6.2831853f;
    e->vx = cosf(angle) * g.config.wandererSpeed;
    e->vy = sinf(angle) * g.config.wandererSpeed;
    e->radius = g.config.wandererRadius;
    e->rot = angle;
    e->r = g.config.wandererColor[0];
    e->g = g.config.wandererColor[1];
    e->b = g.config.wandererColor[2];
    e->a = g.config.wandererColor[3];
}

int countEnemies() {
    int n = 0;
    for (int i = 0; i < POLY99_MAX_ENTITIES; i++) {
        if (g.entities[i].alive && isEnemyType(g.entities[i].type)) n++;
    }
    return n;
}

void spawnEnemyAtEdge() {
    float x, y;
    int side = nextRand(&g.randState) % 4;
    switch (side) {
        case 0: x = randFloat(&g.randState) * g.arenaW; y = -40.0f; break;             // top
        case 1: x = randFloat(&g.randState) * g.arenaW; y = g.arenaH + 40.0f; break;  // bottom
        case 2: x = -40.0f; y = randFloat(&g.randState) * g.arenaH; break;            // left
        default: x = g.arenaW + 40.0f; y = randFloat(&g.randState) * g.arenaH; break; // right
    }
    /* Wanderers only join the mix from wave 2 on, at roughly 30% of spawns. */
    int wanderer = (g.wave >= 2) && (randFloat(&g.randState) < 0.30f);
    if (wanderer) spawnWanderer(x, y);
    else spawnGrasshopper(x, y);
}

void resetGame() {
    for (int i = 0; i < POLY99_MAX_ENTITIES; i++) g.entities[i].alive = 0;
    g.entityCount = 0;
    g.score = 0;
    g.wave = 1;
    g.lives = g.config.playerLives;
    g.gameOver = 0;
    g.fireTimer = 0.0f;
    g.spawnTimer = g.config.spawnInterval;
    g.waveTimer = g.config.waveDuration;
    g.invulnTimer = 0.0f;
    g.dashing = 0;
    g.dashTimeLeft = 0.0f;
    g.dashCooldown = 0.0f;
    g.dashDirX = 0.0f;
    g.dashDirY = 0.0f;
    g.dashHeldPrev = 0;

    Poly99Entity *p = spawn(POLY99_ET_PLAYER);
    if (p) {
        p->x = g.arenaW * 0.5f;
        p->y = g.arenaH * 0.5f;
        p->vx = 0.0f;
        p->vy = 0.0f;
        p->rot = -90.0f * (float)(M_PI / 180.0);
        p->radius = g.config.playerRadius;
        p->r = g.config.playerColor[0];
        p->g = g.config.playerColor[1];
        p->b = g.config.playerColor[2];
        p->a = g.config.playerColor[3];
        g.playerIndex = p - g.entities;
    } else {
        g.playerIndex = -1;
    }
}

} // namespace

void poly99_init(unsigned int seed, const Poly99Config *config) {
    g = GameState{};
    g.randState = seed ? seed : 0x9E3779B9u;
    g.arenaW = 1280.0f;
    g.arenaH = 720.0f;
    if (config) g.config = *config;
    resetGame();
}

void poly99_set_arena(float width, float height) {
    if (width > 0.0f) g.arenaW = width;
    if (height > 0.0f) g.arenaH = height;
    if (g.playerIndex >= 0 && g.entities[g.playerIndex].alive) {
        Poly99Entity *p = &g.entities[g.playerIndex];
        if (p->x > g.arenaW) p->x = g.arenaW;
        if (p->y > g.arenaH) p->y = g.arenaH;
    }
}

void poly99_tick(float dt, const Poly99Input *input) {
    Poly99Entity *player = (g.playerIndex >= 0) ? &g.entities[g.playerIndex] : NULL;

    g.eventCount = 0;

    if (g.gameOver) {
        if (input && input->restart) resetGame();
        return;
    }

    float moveX = input ? input->moveX : 0.0f;
    float moveY = input ? input->moveY : 0.0f;
    float len = sqrtf(moveX * moveX + moveY * moveY);
    if (len > 1.0f) {
        moveX /= len;
        moveY /= len;
    }

    if (player && player->alive) {
        /* Dash fires on the rising edge of input->dash while off cooldown. */
        int dashHeld = input && input->dash ? 1 : 0;
        if (dashHeld && !g.dashHeldPrev && !g.dashing && g.dashCooldown <= 0.0f) {
            float dx = 0.0f, dy = 0.0f;
            if (len > 0.001f) {
                dx = moveX / len;
                dy = moveY / len;
            } else {
                float aimX = input ? input->aimX : 0.0f;
                float aimY = input ? input->aimY : 0.0f;
                float aimLen = sqrtf(aimX * aimX + aimY * aimY);
                if (aimLen > 0.001f) {
                    dx = aimX / aimLen;
                    dy = aimY / aimLen;
                } else {
                    dx = cosf(player->rot);
                    dy = sinf(player->rot);
                }
            }
            g.dashDirX = dx;
            g.dashDirY = dy;
            g.dashing = 1;
            g.dashTimeLeft = g.config.dashDuration;
            g.dashCooldown = g.config.dashCooldown;
            pushEvent(POLY99_EV_PLAYER_DASH, player->x, player->y, POLY99_ET_PLAYER,
                      player->r, player->g, player->b, player->a);
        }
        g.dashHeldPrev = dashHeld;

        if (g.dashing) {
            player->vx = g.dashDirX * g.config.dashSpeed;
            player->vy = g.dashDirY * g.config.dashSpeed;
        } else {
            player->vx = moveX * g.config.playerSpeed;
            player->vy = moveY * g.config.playerSpeed;
        }
        player->x += player->vx * dt;
        player->y += player->vy * dt;

        if (player->x < 0.0f) player->x = 0.0f;
        if (player->x > g.arenaW) player->x = g.arenaW;
        if (player->y < 0.0f) player->y = 0.0f;
        if (player->y > g.arenaH) player->y = g.arenaH;

        float aimX = input ? input->aimX : 0.0f;
        float aimY = input ? input->aimY : 0.0f;
        float aimLen = sqrtf(aimX * aimX + aimY * aimY);
        if (aimLen > 0.05f) {
            player->rot = atan2f(aimY, aimX);
        }

        g.fireTimer -= dt;
        if (input && input->firing && g.fireTimer <= 0.0f) {
            spawnBullet(player->x, player->y, player->rot);
            g.fireTimer = g.config.fireCooldown;
            pushEvent(POLY99_EV_BULLET_FIRED, player->x, player->y, POLY99_ET_BULLET,
                      g.config.bulletColor[0], g.config.bulletColor[1],
                      g.config.bulletColor[2], g.config.bulletColor[3]);
        }
    }

    for (int i = 0; i < POLY99_MAX_ENTITIES; i++) {
        Poly99Entity *e = &g.entities[i];
        if (!e->alive) continue;

        if (e->type == POLY99_ET_BULLET) {
            e->x += e->vx * dt;
            e->y += e->vy * dt;
            if (e->x < -20.0f || e->x > g.arenaW + 20.0f || e->y < -20.0f || e->y > g.arenaH + 20.0f) {
                kill(e);
            }
        } else if (e->type == POLY99_ET_ENEMY_GRASSHOPPER) {
            if (player && player->alive) {
                float dx = player->x - e->x;
                float dy = player->y - e->y;
                float d = sqrtf(dx * dx + dy * dy);
                if (d > 0.001f) {
                    e->vx = dx / d * g.config.enemySpeed;
                    e->vy = dy / d * g.config.enemySpeed;
                    e->rot = atan2f(dy, dx);
                }
            }
            e->x += e->vx * dt;
            e->y += e->vy * dt;
            if (e->x < 0.0f) e->x = 0.0f;
            if (e->x > g.arenaW) e->x = g.arenaW;
            if (e->y < 0.0f) e->y = 0.0f;
            if (e->y > g.arenaH) e->y = g.arenaH;
        } else if (e->type == POLY99_ET_ENEMY_WANDERER) {
            /* Straight-line drift, bouncing off the arena walls. */
            e->x += e->vx * dt;
            e->y += e->vy * dt;
            if (e->x < 0.0f) { e->x = 0.0f; e->vx = -e->vx; }
            if (e->x > g.arenaW) { e->x = g.arenaW; e->vx = -e->vx; }
            if (e->y < 0.0f) { e->y = 0.0f; e->vy = -e->vy; }
            if (e->y > g.arenaH) { e->y = g.arenaH; e->vy = -e->vy; }
            if (e->vx != 0.0f || e->vy != 0.0f) e->rot = atan2f(e->vy, e->vx);
        }
    }

    if (g.invulnTimer > 0.0f) g.invulnTimer -= dt;

    for (int i = 0; i < POLY99_MAX_ENTITIES; i++) {
        Poly99Entity *a = &g.entities[i];
        if (!a->alive) continue;

        for (int j = i + 1; j < POLY99_MAX_ENTITIES; j++) {
            Poly99Entity *b = &g.entities[j];
            if (!b->alive) continue;

            int ca = collisionClass(a->type);
            int cb = collisionClass(b->type);
            Poly99Entity *shooter = NULL;  /* bullet half of the pair */
            Poly99Entity *victim = NULL;    /* enemy half of the pair   */
            Poly99Entity *hurter = NULL;    /* player half of the pair  */
            if (ca == 2 && cb == 3) { shooter = a; victim = b; }
            else if (cb == 2 && ca == 3) { shooter = b; victim = a; }
            else if (ca == 1 && cb == 3) { hurter = a; victim = b; }
            else if (cb == 1 && ca == 3) { hurter = b; victim = a; }
            else continue;

            float dx = a->x - b->x;
            float dy = a->y - b->y;
            float rr = a->radius + b->radius;
            if (dx * dx + dy * dy > rr * rr) continue;

            if (shooter) {
                kill(shooter);
                kill(victim);
                g.score += enemyScoreValue(victim->type) * g.wave;
                pushEvent(POLY99_EV_ENEMY_KILLED, victim->x, victim->y, victim->type,
                          victim->r, victim->g, victim->b, victim->a);
            } else if (hurter) {
                if (g.invulnTimer > 0.0f || g.dashing) continue; /* dashing player is untouchable */
                kill(victim);
                g.lives--;
                g.invulnTimer = g.config.invulnTime;
                pushEvent(POLY99_EV_PLAYER_HIT, hurter->x, hurter->y, POLY99_ET_PLAYER,
                          hurter->r, hurter->g, hurter->b, hurter->a);
                if (g.lives <= 0) {
                    g.lives = 0;
                    g.gameOver = 1;
                    pushEvent(POLY99_EV_GAME_OVER, hurter->x, hurter->y, POLY99_ET_PLAYER,
                              hurter->r, hurter->g, hurter->b, hurter->a);
                }
            }
        }
    }

    /* Dash timers tick after the collision pass so the player stays invulnerable
       for every tick the burst actually moves the player. */
    if (g.dashCooldown > 0.0f) {
        g.dashCooldown -= dt;
        if (g.dashCooldown < 0.0f) g.dashCooldown = 0.0f;
    }
    if (g.dashing) {
        g.dashTimeLeft -= dt;
        if (g.dashTimeLeft <= 0.0f) {
            g.dashing = 0;
            g.dashTimeLeft = 0.0f;
        }
    }

    g.spawnTimer -= dt;
    if (g.spawnTimer <= 0.0f) {
        float interval = g.config.spawnInterval;
        float minInterval = g.config.spawnIntervalMin;
        float shrink = (float)(g.wave - 1) * 0.08f;
        interval -= shrink;
        if (interval < minInterval) interval = minInterval;
        if (countEnemies() < g.config.enemySpawnCap) spawnEnemyAtEdge();
        g.spawnTimer = interval;
    }

    g.waveTimer -= dt;
    if (g.waveTimer <= 0.0f) {
        g.wave++;
        g.waveTimer = g.config.waveDuration;
        pushEvent(POLY99_EV_WAVE_START, g.arenaW * 0.5f, g.arenaH * 0.5f, POLY99_ET_NONE,
                  g.config.playerColor[0], g.config.playerColor[1],
                  g.config.playerColor[2], g.config.playerColor[3]);
    }
}

void poly99_get_snapshot(Poly99Snapshot *out) {
    if (!out) return;
    out->entities = g.entities;
    out->entityCount = g.entityCount;
    out->score = g.score;
    out->wave = g.wave;
    out->lives = g.lives;
    out->gameOver = g.gameOver;
    out->dashing = g.dashing;
    out->dashCooldownRemaining = g.dashCooldown;
    out->events = g.events;
    out->eventCount = g.eventCount;
}

void poly99_shutdown(void) {
    for (int i = 0; i < POLY99_MAX_ENTITIES; i++) g.entities[i].alive = 0;
    g.entityCount = 0;
}
