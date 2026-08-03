#ifndef POLY99_H
#define POLY99_H

#include "core_api.h"

struct GameState {
    Poly99Entity entities[POLY99_MAX_ENTITIES];
    int   entityCount;
    Poly99Config config;
    float arenaW;
    float arenaH;
    int   score;
    int   wave;
    int   lives;
    float fireTimer;
    float spawnTimer;
    float waveTimer;
    float invulnTimer;
    int   gameOver;
    int   playerIndex;
    unsigned int randState;
};

#endif /* POLY99_H */
