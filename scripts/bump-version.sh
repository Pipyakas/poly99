#!/usr/bin/env bash
# Bump the Android version manifest to the current GMT+7 ISO timestamp.
# Run before deploying a new web build to gh-pages:
#   ./scripts/bump-version.sh
set -euo pipefail

version=$(TZ="Etc/GMT-7" date -Iseconds)
printf '{"version":"%s"}\n' "$version" > version.json
echo "version.json -> $version"
