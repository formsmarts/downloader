"""Build the desktop app with PyInstaller for the current platform.

    pip install . pyinstaller
    python packaging/build.py

Output:
  Windows: dist/FormSmarts Downloader.exe  (single file)
  macOS:   dist/FormSmarts Downloader.app

PyInstaller can't cross-compile: build the Windows app on Windows and the
macOS app on a Mac (the GitHub Actions workflow does both).

On macOS, set MACOS_SIGN_IDENTITY to a "Developer ID Application" identity
(name or SHA-1) to sign the bundled code, then run
packaging/macos/sign_and_notarize.sh. MACOS_BUNDLE_ID overrides the bundle
identifier.
Without signing, the app works but can't save the API key (Touch ID
storage requires a signed app with a provisioning profile).
"""

import os
import plistlib
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from formsmarts_downloader import __version__  # noqa: E402

APP_NAME = "FormSmarts Downloader"
BUNDLE_ID = os.environ.get("MACOS_BUNDLE_ID") or "com.formsmarts.Downloader"


def main():
    args = [
        str(ROOT / "packaging" / "launch_gui.py"),
        "--name", APP_NAME,
        "--windowed",
        "--noconfirm",
        "--clean",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        # Imported lazily; list explicitly so they're always bundled.
        "--hidden-import", "formsmarts_downloader.downloader",
        "--collect-submodules", "keyring.backends",
        "--hidden-import", "truststore",
        "--add-data", "{}{}formsmarts_downloader/assets".format(
            ROOT / "formsmarts_downloader" / "assets", os.pathsep
        ),
    ]
    if sys.platform == "win32":
        args += [
            "--onefile",
            "--icon", str(ROOT / "packaging" / "icons" / "app_icon.ico"),
            "--hidden-import", "formsmarts_downloader._win_hello",
            "--hidden-import", "formsmarts_downloader._win_dates",
            "--collect-submodules", "winrt",
        ]
    elif sys.platform == "darwin":
        args += [
            "--osx-bundle-identifier", BUNDLE_ID,
            "--icon", str(ROOT / "packaging" / "icons" / "app_icon.icns"),
            "--hidden-import", "formsmarts_downloader._mac_keychain",
            "--hidden-import", "formsmarts_downloader._mac_dates",
        ]
        identity = os.environ.get("MACOS_SIGN_IDENTITY")
        if identity:
            args += ["--codesign-identity", identity]
    PyInstaller.__main__.run(args)

    if sys.platform == "darwin":
        _set_bundle_info(ROOT / "dist" / (APP_NAME + ".app"))


def _set_bundle_info(app: Path):
    plist_path = app / "Contents" / "Info.plist"
    with open(plist_path, "rb") as f:
        info = plistlib.load(f)
    info["CFBundleShortVersionString"] = __version__
    info["CFBundleVersion"] = __version__
    info["NSHighResolutionCapable"] = True
    info["LSMinimumSystemVersion"] = "11.0"
    with open(plist_path, "wb") as f:
        plistlib.dump(info, f)


if __name__ == "__main__":
    main()
