# poly99 — Android shell

Self-updatable Android wrapper for the hosted web build. The app loads the game
in a fullscreen `WebView`, serves it from a **local cache** on launch (offline-capable,
instant start), and checks in the background for newer versions.

## Behavior

- **Cache-first**: the game files (`index.html`, `index.js`, `index.wasm`,
  `index.data`) are cached in app-private storage. Launches serve the cached copy,
  so the game starts instantly and works offline.
- **Background update**: on every launch the app fetches `version.json` from the
  host. If the remote version differs from the cached one, the new files are
  pre-downloaded and the user is prompted: *"Update available — reload?"*
- **Orientation**: a small **⚙** button (bottom-right) opens settings with
  Landscape / Portrait / Auto; the choice persists between launches.
- **First launch**: if nothing is cached yet, the game loads from the network
  while the cache is populated in the background.

## Version manifest

The host must serve `version.json` (e.g. `{"version":"1.0.0"}`) alongside the web
build. Bump the version whenever you publish a new build to trigger the update
prompt on devices.

## Install

Grab the APK from the latest GitHub Release, or build it yourself:

```bash
./gradlew assembleDebug
adb install app/build/outputs/apk/debug/app-debug.apk
```

## Config

- **URL** — override with a gradle property:
  `./gradlew assembleDebug -PPOLY99_URL=https://example.com/game/`
- **Orientation** — default is landscape; changeable in-app via ⚙

## Releases

CI (`.github/workflows/android-release.yml`) builds the APK whenever a tag
matching `android-v*` is pushed and attaches it to a GitHub Release:

```bash
git tag android-v2
git push origin android-v2
```

The web content updates itself automatically via the version check; the shell
only needs a new release when the wrapper itself changes.
