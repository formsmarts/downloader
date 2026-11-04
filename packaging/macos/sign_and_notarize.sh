#!/bin/bash
# Sign, notarize and package the macOS app built by packaging/build.py.
#
# Required environment:
#   MACOS_SIGN_IDENTITY         "Developer ID Application: ..." identity (in a keychain)
#   APPLE_TEAM_ID               Apple Developer team ID
#   MACOS_PROVISIONING_PROFILE  path to the Developer ID provisioning profile
#                               for com.formsmarts.pdfdownloader
# Optional (notarization; skipped if unset):
#   NOTARY_KEY_PATH, NOTARY_KEY_ID, NOTARY_ISSUER_ID   App Store Connect API key
set -euo pipefail

: "${MACOS_SIGN_IDENTITY:?}" "${APPLE_TEAM_ID:?}" "${MACOS_PROVISIONING_PROFILE:?}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/dist/FormSmarts PDF Downloader.app"
ZIP="$ROOT/dist/FormSmarts-PDF-Downloader-macOS.zip"
ENTITLEMENTS="$ROOT/build/entitlements.plist"

mkdir -p "$ROOT/build"
sed "s/__TEAM_ID__/${APPLE_TEAM_ID}/g" "$ROOT/packaging/macos/entitlements.plist" > "$ENTITLEMENTS"
cp "$MACOS_PROVISIONING_PROFILE" "$APP/Contents/embedded.provisionprofile"

# Nested code was signed by PyInstaller (MACOS_SIGN_IDENTITY); re-sign the
# bundle itself so it seals the provisioning profile and carries the
# entitlements.
codesign --force --options runtime --timestamp \
    --entitlements "$ENTITLEMENTS" --sign "$MACOS_SIGN_IDENTITY" "$APP"
codesign --verify --strict --verbose=2 "$APP"

rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"

if [[ -n "${NOTARY_KEY_PATH:-}" ]]; then
    xcrun notarytool submit "$ZIP" --wait \
        --key "$NOTARY_KEY_PATH" --key-id "$NOTARY_KEY_ID" --issuer "$NOTARY_ISSUER_ID"
    xcrun stapler staple "$APP"
    rm -f "$ZIP"
    ditto -c -k --keepParent "$APP" "$ZIP"
    spctl --assess --type execute --verbose "$APP"
else
    echo "NOTARY_KEY_PATH not set: skipping notarization."
fi
echo "Built $ZIP"
