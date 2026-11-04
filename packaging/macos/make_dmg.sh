#!/bin/bash
# Package dist/FormSmarts Downloader.app into a DMG with an Applications
# shortcut, so users can drag the app to Applications.
# Prints the DMG's path. Signing/notarizing is done by sign_and_notarize.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/dist/FormSmarts Downloader.app"
VERSION="$(sed -nE 's/^__version__ = "([^"]+)".*/\1/p' "$ROOT/formsmarts_downloader/__init__.py")"
DMG="$ROOT/dist/FormSmarts-Downloader-${VERSION}-macos-arm64.dmg"
STAGING="$ROOT/build/dmg"

rm -rf "$STAGING" "$DMG"
mkdir -p "$STAGING"
cp -R "$APP" "$STAGING/"
ln -s /Applications "$STAGING/Applications"
# hdiutil occasionally fails with "Resource busy" on CI runners, so retry
for attempt in 1 2 3; do
    hdiutil create -quiet -volname "FormSmarts Downloader" -srcfolder "$STAGING" \
        -ov -format UDZO "$DMG" && break
    sleep 5
done
test -f "$DMG"
rm -rf "$STAGING"
echo "$DMG"
