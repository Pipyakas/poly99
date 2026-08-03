# poly99 — Geometry Wars × 1v99 Survival

## Vision

A twin-stick shooter in the Geometry Wars visual style with a **1vs99 survival mode**. Each player fights waves of enemies in their own instance — when you eliminate enemies, "attacks" spill over into opponents' instances as bonus spawn waves, debuffs, or environmental hazards. Last player standing wins. Built with a **shared gameplay core** in portable C++, rendered through three backends:

| Target | Renderer | Game Modes | Purpose |
|--------|----------|------------|---------|
| **Web** | raylib (via Emscripten) | 1v99 survival | Free, playable in browser |
| **Android** | WebView/TWA shell around the hosted web build | 1v99 survival | Self-updatable — always tests the latest pushed build from a phone |
| **Desktop/Console** | Unreal Engine 5 | 1v99 mode + additional modes | High-fidelity "poly99+" edition with particles, bloom, neon glow |

The core game logic (entities, physics, spawning, scoring, attack queue) is engine-agnostic — it only depends on standard C++ and a thin abstraction layer for input/time/audio.

---

## Project Structure

```
poly99/
├── core/                       # Shared gameplay core (engine-agnostic)
│   ├── CMakeLists.txt
│   ├── poly99.h                # Main include, defines GameState, Entity, etc.
│   ├── poly99.cpp              # Game simulation tick()
│   ├── entity.h / entity.cpp   # Entity pool, component-like data
│   ├── arena.h / arena.cpp     # Playfield boundary, grid, walls
│   ├── spawner.h / spawner.cpp # Wave system, enemy spawning
│   ├── player.h / player.cpp   # Player ship input + state
│   ├── enemy.h / enemy.cpp     # Enemy types (Grasshopper, Snake, etc.)
│   ├── projectile.h / .cpp     # Bullets, enemy projectiles
│   ├── collision.h / .cpp      # Spatial grid + collision detection
│   ├── score.h / score.cpp     # Score tracking, multiplier chain
│   ├── particle.h / .cpp       # Particle state (position, velocity, color, life)
│   └── core_api.h              # Pure-C interface for FFI / UE5 plugin
│
├── raylib/                     # raylib + Emscripten frontend
│   ├── CMakeLists.txt
│   ├── main.cpp                # Entry point, window, game loop
│   ├── renderer.h / .cpp       # raylib drawing (geometric shapes, neon glow)
│   ├── input.h / input.cpp     # Keyboard/gamepad → core input mapping
│   ├── audio.h / audio.cpp     # raylib audio → play sounds
│   └── web/                    # Emscripten build artifacts
│       ├── index.html
│       ├── index.js
│       └── poly99.data
│
├── android/                    # Self-updatable Android shell (WebView/TWA)
│   ├── app/
│   │   └── src/main/
│   │       ├── AndroidManifest.xml
│   │       ├── java/com/pipyakas/poly99/MainActivity.kt
│   │       └── res/
│   ├── build.gradle.kts
│   └── README.md               # Build + install instructions
│
├── .github/workflows/android-release.yml  # CI: builds APK on tag, attaches to GitHub Release
│
├── unreal/                     # Unreal Engine 5 plugin/project
│   ├── Poly99Game/
│   │   ├── Source/
│   │   │   ├── Poly99GameModule.cpp
│   │   │   ├── Poly99GameMode.h/.cpp
│   │   │   ├── Poly99PlayerController.h/.cpp
│   │   │   ├── Poly99Pawn.h/.cpp
│   │   │   ├── Poly99HUD.h/.cpp
│   │   │   └── Renderer/
│   │   │       ├── Poly99NiagaraManager.h/.cpp    # Niagara particle systems
│   │   │       ├── Poly99MeshRenderer.h/.cpp       # Instanced static meshes
│   │   │       ├── Poly99PostProcess.h/.cpp        # Bloom, glow, tone mapping
│   │   │       └── Poly99AudioComponent.h/.cpp
│   │   ├── Plugins/
│   │   │   └── Poly99Core/                         # Wraps core/ as UE5 module
│   │   │       ├── Source/
│   │   │       │   ├── Poly99Core.Build.cs
│   │   │       │   ├── Poly99CoreModule.cpp
│   │   │       │   ├── CoreBridge.h/.cpp            # Calls core_api.h, maps UE types
│   │   │       │   └── ...
│   │   │       └── Poly99Core.uplugin
│   │   └── Poly99Game.uproject
│   └── README.md
│
├── CMakeLists.txt              # Top-level: builds core tests + raylib target
├── plan.md                     # This file
└── README.md
```

---

## Core Design (Shared)

### `core_api.h` — Pure-C Interface

The core exposes a flat C API so it can be called from any language/framework:
- `poly99_init(seed)` — initialise game state
- `poly99_tick(dt, input_state)` — advance one frame
- `poly99_get_entities()` → read-only array of positions, colors, sizes, types
- `poly99_get_score()`, `poly99_get_wave()`, etc.
- `poly99_get_particles()` → particle data for rendering
- `poly99_shutdown()`

This is the only header the raylib and UE5 frontends include.

### Entity System

- Fixed-size pool, no dynamic allocation during gameplay
- Each entity: `{ pos, vel, rot, radius, color, type, hp, timer, alive }`
- Types: `Player`, `Bullet`, `EnemyGrasshopper`, `EnemySnake`, `EnemySpinner`, `EnemyWanderer`, `Pickup`
- Spatial grid (cell size ~64px) for fast collision queries

### Gameplay Features — 1v99 Survival

- **Each player has their own instance**: an arena with waves of AI enemies. No shared map.
- **Attack system**: killing enemies charges your attack meter. Filling it sends a "packet" to a target opponent's instance as bonus waves, bullet storms, or hazards.
- **Targeting**: players can switch their attack target between "attackers" (those targeting you), "kill leaders", "badge holders", or "random".
- **KO/elimination**: if an opponent is overwhelmed by incoming attacks (too many enemies in their arena), they are eliminated. Last one standing wins.
- **Survival loop**: survive ever-hardening waves in your own arena while managing incoming attacks from up to 99 opponents.
- **Enemy types** (Geometry Wars-inspired):
  - *Grasshopper*: basic chaser, most common
  - *Snake*: follows trails, segments — hard to kill without chain reaction
  - *Spinner*: orbits a point, emits radial bullets — area denial
  - *Wanderer*: random direction, bounces off walls, splits on death — fills space
  - *Gate*: stationary, spawns other enemies, must be destroyed to stem the tide
- **Combo chains**: killing enemies in quick succession builds a multiplier that boosts attack damage sent to opponents.
- **Pickups**: bomb (screen clear), shield (temporary invulnerability), speed boost, attack multiplier — dropped by enemies.
- **Arena**: large rectangle with neon grid that pulses to music; edges show active incoming attacks as a glow.

---

## raylib Frontend (Web — 1v99 Survival)

- Single-window, `raylib` 5.5+ with `PLATFORM_WEB`
- `renderer.cpp` draws all entities as outline-only geometric shapes (circles, triangles, lines) with a neon glow effect via repeated draw calls with decreasing alpha
- Attack queue shown as a visual indicator on arena edges (incoming danger level by direction)
- Keyboard: WASD + mouse aim / Arrow keys + ZX for shooting; number keys 1-4 to switch targeting mode
- Gamepad: full twin-stick + d-pad for targeting mode
- Audio: raylib audio for simple synth sounds
- HUD shows: opponents remaining, attack meter, current kill streak, targeting mode
- Simulated 99 opponents via AI instances (no real multiplayer in web build — AI opponents that send attacks based on simulated performance)
- Build with Emscripten: `emcmake cmake -B build-web && cmake --build build-web`

---

## Android Frontend (Self-Updatable Test Shell)

A thin native Android wrapper around the hosted web build, **cache-first with background updates**: launches serve the locally cached game (instant start, works offline), then quietly check the host for a newer version and prompt the user to reload to update.

- **Architecture**: single-activity app hosting the web build in a fullscreen `WebView` (TWA/Bubblewrap upgrade path if we want "Add to home screen" + launcher integration)
- **Caching**: game files are downloaded once into app-private storage and served via `shouldInterceptRequest` — no network needed on subsequent launches
- **Update check**: on launch, fetches `version.json` from the host; when the remote version differs, new files are pre-downloaded and the user is prompted ("Update available — reload?") to swap and reload. Offline hosts fall back to the cached build silently. **In dev the version is the GMT+7 ISO timestamp of the deploy** (`scripts/bump-version.sh`), so every publish is a unique update
- **URL**: points at the published site (e.g. `https://pipyakas.github.io/poly99/`), configurable via the `POLY99_URL` gradle property
- **Settings**: ⚙ overlay offers Landscape / Portrait / Auto orientation (persisted); cleartext/HTTP only in dev builds; hardware acceleration; back button; fullscreen
- **Distribution**: GitHub Actions builds the APK on a `android-v*` tag push and attaches it to a GitHub Release (`gh release` / Releases page). Install the APK once; the game inside updates itself
- **Dependency**: Android shell needs no raylib/UE5/CMake knowledge — it only requires the web build + `version.json` to be published
- **Build**: `./gradlew assembleDebug` from `android/`; CI flow is `git tag android-v2 && git push --tags`
- **Note**: phone testing needs touch input in the web build (see raylib section); shell works today for desktop-controlled preview but the web frontend must gain touch/gamepad controls for real on-device play

---

## Unreal Engine 5 Frontend (poly99+)

- **Core wrapped as UE5 plugin** (`Plugins/Poly99Core`): calls `core_api.h` once per tick from a `UObject` that lives in the game instance
- Supports **multiple game modes** implemented in Blueprints/C++: 1v99 survival (shared core), Time Attack, Survival, Sandbox
- Dedicated server architecture for real multiplayer: each player runs a core instance server-side; attack packets relayed between players
- `Poly99Pawn` reads entity data and spawns/updates `UInstancedStaticMeshComponent` for each entity type
- `Poly99NiagaraManager` converts particle state from core into Niagara emitters with custom glow/spark materials
- Post-process: bloom, auto-exposure, lens flare for the neon aesthetic
- Audio: MetaSounds driven by core events (enemy death, attack received, KO, combo)
- Game mode-specific logic (attack rules, scoring, win conditions) lives in UE5 C++/Blueprints, calling into the core for simulation
- No C++ exceptions or STL in core — `/EHsc` and UE5's custom STL must both be compatible

---

## Build & Workflow

```bash
# raylib web build
cd poly99
emcmake cmake -B build-web -DPLATFORM=Web
cmake --build build-web
npx serve build-web

# android shell (built by CI on `android-v*` tags; manual fallback below)
cd android && ./gradlew assembleDebug
# release flow: git tag android-v1 && git push --tags  ->  APK lands in GitHub Releases

# core standalone tests
cmake -B build-core -DPLATFORM=Desktop
cmake --build build-core && ./build-core/core_tests

# UE5 — open Poly99Game.uproject, build from editor
```

---

## Roadmap

| Phase | What | Output |
|-------|------|--------|
| 1 | Android WebView/TWA shell (self-updatable) | Installable APK shipped via GitHub Releases |
| 2 | Core entity + collision + enemy AI + attack queue system | Core library + unit tests |
| 3 | raylib renderer + input + 1v99 loop with simulated opponents | Playable web build |
| 4 | All enemy types, pickups, HUD, targeting modes, audio | Feature-complete web 1v99 |
| 5 | UE5 plugin wrapper + CoreBridge + 1v99 mode + dedicated server | Core runs inside UE5 with real multiplayer |
| 6 | UE5 visual pass + additional game modes | poly99+ edition with multiple modes |

---

## Key Technical Constraints

- Core uses **no STL** (or a controlled subset) to avoid ABI friction with UE5
- Core allocates **zero memory at runtime** — all pools are fixed-size, pre-allocated
- `core_api.h` is valid C and C++ — consumable from UE5's Clang, MSVC, and Emscripten
- raylib build uses Emscripten's `-sASYNCIFY` for main loop compatibility
