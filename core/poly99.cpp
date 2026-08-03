#include "poly99.h"

#include <math.h>

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

int countEnemies() {
    int n = 0;
    for (int i = 0; i < POLY99_MAX_ENTITIES; i++) {
        if (g.entities[i].alive && g.entities[i].type == POLY99_ET_ENEMY_GRASSHOPPER) n++;
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
    spawnGrasshopper(x, y);
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
        player->vx = moveX * g.config.playerSpeed;
        player->vy = moveY * g.config.playerSpeed;
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
        }
    }

    if (g.invulnTimer > 0.0f) g.invulnTimer -= dt;

    for (int i = 0; i < POLY99_MAX_ENTITIES; i++) {
        Poly99Entity *a = &g.entities[i];
        if (!a->alive) continue;

        for (int j = i + 1; j < POLY99_MAX_ENTITIES; j++) {
            Poly99Entity *b = &g.entities[j];
            if (!b->alive) continue;

            if (a->type == POLY99_ET_BULLET && b->type == POLY99_ET_ENEMY_GRASSHOPPER) {
                float dx = a->x - b->x;
                float dy = a->y - b->y;
                float rr = a->radius + b->radius;
                if (dx * dx + dy * dy <= rr * rr) {
                    kill(a);
                    kill(b);
                    g.score += 10 * g.wave;
                }
            } else if (a->type == POLY99_ET_ENEMY_GRASSHOPPER && b->type == POLY99_ET_BULLET) {
                float dx = a->x - b->x;
                float dy = a->y - b->y;
                float rr = a->radius + b->radius;
                if (dx * dx + dy * dy <= rr * rr) {
                    kill(a);
                    kill(b);
                    g.score += 10 * g.wave;
                }
            } else if (a->type == POLY99_ET_PLAYER && b->type == POLY99_ET_ENEMY_GRASSHOPPER && g.invulnTimer <= 0.0f) {
                float dx = a->x - b->x;
                float dy = a->y - b->y;
                float rr = a->radius + b->radius;
                if (dx * dx + dy * dy <= rr * rr) {
                    kill(b);
                    g.lives--;
                    g.invulnTimer = g.config.invulnTime;
                    if (g.lives <= 0) {
                        g.lives = 0;
                        g.gameOver = 1;
                    }
                }
            } else if (a->type == POLY99_ET_ENEMY_GRASSHOPPER && b->type == POLY99_ET_PLAYER && g.invulnTimer <= 0.0f) {
                float dx = a->x - b->x;
                float dy = a->y - b->y;
                float rr = a->radius + b->radius;
                if (dx * dx + dy * dy <= rr * rr) {
                    kill(a);
                    g.lives--;
                    g.invulnTimer = g.config.invulnTime;
                    if (g.lives <= 0) {
                        g.lives = 0;
                        g.gameOver = 1;
                    }
                }
            }
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
}

void poly99_shutdown(void) {
    for (int i = 0; i < POLY99_MAX_ENTITIES; i++) g.entities[i].alive = 0;
    g.entityCount = 0;
}
