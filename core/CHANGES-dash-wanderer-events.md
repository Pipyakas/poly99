# Core API changes — dash, wanderer, event buffer

Scope: `core/` (engine-agnostic gameplay core) plus the minimal raylib frontend
wiring needed to keep it building and playable. No STL, no exceptions, no runtime
heap: everything lives in the existing fixed-size pools/buffers.

---

## 1. Dash

### API

| Where | Change |
|---|---|
| `core_api.h` `Poly99Input` | `int dash;` — **held** state; the core latches the rising edge itself |
| `core_api.h` `Poly99Config` | `float dashSpeed; float dashDuration; float dashCooldown;` (appended at the end of the struct) |
| `core_api.h` `Poly99Snapshot` | `int dashing; float dashCooldownRemaining;` |

### Behaviour

* Triggered on the **rising edge** of `input.dash`, only when `dashCooldown` has
  lapsed. Holding the button does not re-trigger; the burst always runs to
  completion.
* Direction: move vector if non-zero, else aim vector, else the facing angle
  (`player->rot`). Move/aim vectors are normalized, so a partially-held stick
  dashes at the same speed.
* Speed `dashSpeed` for `dashDuration` seconds, then normal movement resumes.
  Movement uses the same arena clamp as walking, so a dash into a wall stops at
  the wall.
* The player is **invulnerable for the whole burst**. The dash timers tick after
  the collision pass, so the snapshot's `dashing` flag is exact: a player that is
  `dashing` in a snapshot can never have taken a hit in that tick.
* `dashCooldown` starts the moment the burst starts (so the downtime is measured
  from the start of the dash, not its end).

## 2. Wanderer (second enemy type)

### API

| Where | Change |
|---|---|
| `core_api.h` `Poly99EntityType` | `POLY99_ET_ENEMY_WANDERER` appended after `POLY99_ET_ENEMY_GRASSHOPPER` (existing values unchanged) |
| `core_api.h` `Poly99Config` | `float wandererSpeed; float wandererRadius; unsigned char wandererColor[4];` |

### Behaviour

* Spawns at the arena edges through the same `spawnEnemyAtEdge()` path as
  grasshoppers.
* The spawner mixes wanderers in from **wave 2 onward**, at ~30% of spawns
  (`randFloat() < 0.30f`). Wave 1 is unchanged: grasshoppers only.
* Moves in a single random straight line at `wandererSpeed` and **bounces off the
  arena walls** (position is clamped to the arena and the axis velocity is
  flipped), so a wanderer can never end up outside the playfield.
* Never chases the player; collides with the player and with bullets exactly like
  a grasshopper.
* Worth **2x**: `20 * wave` instead of `10 * wave`.

The collision pass was generalised from four hard-coded type pairs to a class
based check (player / bullet / enemy), which is behaviour-identical for
grasshoppers and bullets and adds wanderers without new branches.

## 3. Event buffer

### API

```c
#define POLY99_MAX_EVENTS 256

typedef enum Poly99EventType {
    POLY99_EV_ENEMY_KILLED = 0,
    POLY99_EV_PLAYER_HIT,
    POLY99_EV_PLAYER_DASH,
    POLY99_EV_BULLET_FIRED,
    POLY99_EV_WAVE_START,
    POLY99_EV_GAME_OVER
} Poly99EventType;

typedef struct Poly99Event {
    int           type;
    float         x, y;
    int           entityType;
    unsigned char r, g, b, a;
} Poly99Event;
```

`Poly99Snapshot` gains `const Poly99Event *events; int eventCount;` (the pointer
is valid until the next `poly99_tick`).

### Behaviour

* Fixed 256-entry array inside `GameState`; **cleared at the start of every
  `poly99_tick`**, including ticks that return early on game over.
* Events beyond 256 in a single tick are dropped (no wrap-around, no reordering).
* Emission points:

| Event | When | Position | entityType | Colour |
|---|---|---|---|---|
| `BULLET_FIRED` | a bullet is spawned | player | `POLY99_ET_BULLET` | bullet colour |
| `ENEMY_KILLED` | bullet/enemy overlap | the enemy | the enemy type | enemy colour |
| `PLAYER_HIT` | player/enemy overlap, not invulnerable | player | `POLY99_ET_PLAYER` | player colour |
| `PLAYER_DASH` | dash burst starts | player | `POLY99_ET_PLAYER` | player colour |
| `WAVE_START` | wave counter increments | arena centre | `POLY99_ET_NONE` | player colour |
| `GAME_OVER` | lives reach 0 | player | `POLY99_ET_PLAYER` | player colour |

Frontends that want audio/FX should read `snap.events[0..eventCount)` after
`poly99_tick` and drive their own presentation layer from it.

## 4. New config keys (raylib frontend)

Defaults live in `raylib/config.cpp` `fillDefaults()`; every key is optional in
`config/game.json` and falls back to the default.

| JSON path | Field | Default |
|---|---|---|
| `player.dashSpeed` | `dashSpeed` | `1100` |
| `player.dashDuration` | `dashDuration` | `0.14` (s) |
| `player.dashCooldown` | `dashCooldown` | `0.8` (s) |
| `wanderer.speed` | `wandererSpeed` | `90` |
| `wanderer.radius` | `wandererRadius` | `20` |
| `wanderer.color` | `wandererColor` | `#FFB000` |

`wanderer` is a new top-level object mirroring the existing `enemy` object;
`#RRGGBB` strings go through the same `readColor()` helper.

Other frontend changes (minimal, compile-driven):

* `raylib/input.cpp` — dash bound to Left/Right Shift and gamepad left shoulder.
  Space was left alone because it is already bound to firing. The frontend only
  reports the held state; the rising edge is the core's job.
* `raylib/renderer.cpp` — wanderers draw as glowing squares
  (`drawSquareGlow`), visually distinct from the diamond grasshoppers.
* `raylib/main.cpp` — the HUD/audio enemy counter includes wanderers.

`config/game.json` was **not** modified; all six keys are optional.

## 5. Build/test

`core/CMakeLists.txt` now carries its own `cmake_minimum_required(VERSION 3.16)`
so the core can be configured standalone, and the GCC-only flags are guarded:
`-Wall -Wextra` + `m` for non-MSVC, `/W4` for MSVC.

Commands run (Visual Studio 2026, MSVC 19.51.36260, CMake 4.3.2):

```
cmake -S core -B build-core-only
cmake --build build-core-only --target core_tests
.\build-core-only\Debug\core_tests.exe
ctest --test-dir build-core-only -C Debug --output-on-failure
```

Result:

```
core_tests: ALL PASSED
1/1 Test #1: core_tests .......................   Passed    0.43 sec
100% tests passed, 0 tests failed out of 1
```

(`ctest` needs `-C Debug` because MSVC generates a multi-config tree. Running the
`.exe` directly needs no extra flags.)

One pre-existing warning remains and is unrelated to this change:
`poly99.cpp:179 C4244` on `g.playerIndex = p - g.entities;`.

### Test coverage added

`core/core_tests.cpp` keeps the original smoke test and adds:

* `testDashTravel` — 0.167 s of dashing covers more than twice the distance of
  the same window of walking.
* `testDashFallsBackToAimThenFacing` — no move input dashes along the aim vector;
  with neither move nor aim, along the facing angle.
* `testDashCooldown` — burst starts once, holding does not re-trigger, a press
  during the cooldown is refused, and the next rising edge after it lapses works.
* `testDashInvulnerable` — a grasshopper closes in, the player dashes straight
  into it; the enemy really does overlap the dashing player (asserted) and never
  lands. After the burst ends the same enemy does land.
* `testWanderer` — 1800 ticks from wave 2 on; every wanderer that has been alive
  for more than one tick stays inside the arena, wanderers are actually spawned,
  and the event buffer never overruns.
* `testEventsEnemyKilled` — a bullet kill emits `ENEMY_KILLED` at the enemy's
  position (matched against the pre-tick snapshot) and awards score; the event is
  gone on the next tick.
* `testEventsWaveAndGameOver` — `WAVE_START` fires on the wave bump, `GAME_OVER`
  fires when lives run out.
* `testEventsOverflow` — a long dash keeps the player invulnerable while several
  hundred grasshoppers pile onto it; the instant the burst ends they all land in
  one tick. The buffer caps at exactly `POLY99_MAX_EVENTS`, lives drop, and the
  simulation keeps ticking normally afterwards.

### Other verification

* `core_api.h` still compiles as **C** (`cl /TC /Zs` on a file that includes and
  uses every new field/enum): clean.
* The raylib submodule is not checked out on this machine, so the frontend was
  compile-checked against a minimal stub `raylib.h`
  (`cl /std:c++17 /Zs`): `config.cpp`, `input.cpp` and `main.cpp` are clean
  (`main.cpp` keeps two pre-existing `double`→`float` warnings). `renderer.cpp`
  reports three `C4576` errors, all on **pre-existing** compound literals
  (`(Color){...}` / `(Rectangle){...}` at lines 74, 82, 119) that only compile
  under the clang/emscripten toolchain the web build uses; the new
  `drawSquareGlow` deliberately avoids that syntax.
