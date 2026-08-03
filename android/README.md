# poly99 — Android shell

Self-updatable Android wrapper for the hosted web build. The app is a fullscreen
`WebView` that loads `https://pipyakas.github.io/poly99/` on launch, so it always
runs the **latest pushed build** — install once, never reinstall.

## Install

Grab the APK from the latest GitHub Release, or build it yourself:

```bash
./gradlew assembleDebug
adb install app/build/outputs/apk/debug/app-debug.apk
```

## Config

- **URL** — override with a gradle property:
  `./gradlew assembleDebug -PPOLY99_URL=https://example.com/game/`
- **Orientation** — currently locked to landscape in `AndroidManifest.xml`

## Releases

CI (`.github/workflows/android-release.yml`) builds the APK whenever a tag
matching `android-v*` is pushed and attaches it to a GitHub Release:

```bash
git tag android-v1
git push origin android-v1
```

The web content updates itself automatically via `gh-pages`; the shell only needs
a new release when the wrapper itself changes.
