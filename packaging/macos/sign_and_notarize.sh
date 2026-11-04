#!/bin/bash
# Sign the macOS app built by packaging/build.py, package it in a DMG
# (make_dmg.sh), then sign, notarize and staple the DMG. Notarizing the DMG
# covers the app inside it.
#
# Required:
#   MACOS_SIGN_IDENTITY         Developer ID Application identity (name or SHA-1)
# Optional:
#   MACOS_PROVISIONING_PROFILE  path to the Developer ID provisioning profile.
#                               Needed for Touch ID key storage; without it the
#                               app is signed but only offers "don't save".
#   MACOS_BUNDLE_ID             default: com.formsmarts.Downloader
#   NOTARY_KEY_PATH, NOTARY_API_KEY_ID, NOTARY_API_ISSUER_ID
#                               App Store Connect API key (.p8 path) for
#                               notarization; skipped if unset.
set -euo pipefail

: "${MACOS_SIGN_IDENTITY:?}"
BUNDLE_ID="${MACOS_BUNDLE_ID:-com.formsmarts.Downloader}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/dist/FormSmarts Downloader.app"
ENTITLEMENTS="$ROOT/build/entitlements.plist"
SIGN_ARGS=(--force --options runtime --timestamp --sign "$MACOS_SIGN_IDENTITY")

if [[ -n "${MACOS_PROVISIONING_PROFILE:-}" ]]; then
    # The team ID comes from the profile, so it never needs configuring.
    PROFILE_PLIST="$(mktemp)"
    security cms -D -i "$MACOS_PROVISIONING_PROFILE" > "$PROFILE_PLIST"
    TEAM_ID="$(/usr/libexec/PlistBuddy -c 'Print :TeamIdentifier:0' "$PROFILE_PLIST")"
    rm -f "$PROFILE_PLIST"
    mkdir -p "$ROOT/build"
    sed -e "s/__TEAM_ID__/${TEAM_ID}/g" -e "s/__BUNDLE_ID__/${BUNDLE_ID}/g" \
        "$ROOT/packaging/macos/entitlements.plist" > "$ENTITLEMENTS"
    cp "$MACOS_PROVISIONING_PROFILE" "$APP/Contents/embedded.provisionprofile"
    SIGN_ARGS+=(--entitlements "$ENTITLEMENTS")
else
    echo "MACOS_PROVISIONING_PROFILE not set: signing without keychain entitlements"
    echo "(Touch ID key storage will be unavailable)."
fi

# Nested code was signed by PyInstaller with MACOS_SIGN_IDENTITY; re-sign
# the bundle so it seals the provisioning profile and carries the
# entitlements.
codesign "${SIGN_ARGS[@]}" "$APP"
codesign --verify --strict --verbose=2 "$APP"

DMG="$("$ROOT/packaging/macos/make_dmg.sh")"
codesign --force --timestamp --sign "$MACOS_SIGN_IDENTITY" "$DMG"

if [[ -n "${NOTARY_KEY_PATH:-}" ]]; then
    xcrun notarytool submit "$DMG" --wait \
        --key "$NOTARY_KEY_PATH" --key-id "$NOTARY_API_KEY_ID" --issuer "$NOTARY_API_ISSUER_ID"
    xcrun stapler staple "$DMG"
    spctl --assess --type open --context context:primary-signature --verbose=2 "$DMG"
else
    echo "NOTARY_KEY_PATH not set: skipping notarization."
fi
echo "Built $DMG"
