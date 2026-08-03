#ifndef POLY99_CORE_API_H
#define POLY99_CORE_API_H

#ifdef __cplusplus
extern "C" {
#endif

#define POLY99_MAX_ENTITIES 1024

typedef enum Poly99EntityType {
    POLY99_ET_NONE = 0,
    POLY99_ET_PLAYER,
    POLY99_ET_BULLET,
    POLY99_ET_ENEMY_GRASSHOPPER
} Poly99EntityType;

typedef struct Poly99Entity {
    float x, y;
    float vx, vy;
    float rot;
    float radius;
    int   type;
    unsigned char r, g, b, a;
    int   alive;
} Poly99Entity;

typedef struct Poly99Config {
    float playerSpeed;
    float playerRadius;
    int   playerLives;
    float bulletSpeed;
    float bulletRadius;
    float fireCooldown;
    float enemySpeed;
    float enemyRadius;
    int   enemySpawnCap;
    float spawnInterval;
    float spawnIntervalMin;
    float waveDuration;
    float invulnTime;
    unsigned char playerColor[4];
    unsigned char bulletColor[4];
    unsigned char enemyColor[4];
} Poly99Config;

typedef struct Poly99Input {
    float moveX, moveY;
    float aimX, aimY;
    int   firing;
    int   restart;
} Poly99Input;

typedef struct Poly99Snapshot {
    const Poly99Entity *entities;
    int   entityCount;
    int   score;
    int   wave;
    int   lives;
    int   gameOver;
} Poly99Snapshot;

void poly99_init(unsigned int seed, const Poly99Config *config);
void poly99_set_arena(float width, float height);
void poly99_tick(float dt, const Poly99Input *input);
void poly99_get_snapshot(Poly99Snapshot *out);
void poly99_shutdown(void);

#ifdef __cplusplus
}
#endif

#endif /* POLY99_CORE_API_H */
