# FormSmarts PDF Downloader

Downloads the PDF version of your [FormSmarts](https://formsmarts.com) form
submissions, for a form and date range you choose, into a folder on your
computer.

It comes as a desktop app for Windows and macOS, and as a command-line tool.

## Desktop app

Download the latest version from the
[Releases](https://github.com/formsmarts/downloader/releases) page:

- **Windows:** `FormSmarts PDF Downloader.exe`. Double-click it to run it.
  No installation is needed.
- **macOS:** `FormSmarts-PDF-Downloader-macOS.zip`. Unzip it and drag
  **FormSmarts PDF Downloader** into your Applications folder.

On first launch, fill in **Settings**:

- **Download folder:** where PDFs are saved.
- **Account ID:** your FormSmarts account ID (looks like `FSA-123456`),
  found under *Account Overview* in your FormSmarts account.
- **API key:** found under *Security Settings* in your FormSmarts account.

Then enter a **Form ID** and a date range and click **Download PDFs**.

## Where your API key is stored

You choose one of two options:

| Option | What happens |
| --- | --- |
| **Most secure:** don't save the API key | The key is never saved. You enter it once each time you open the app. |
| **Save the API key, unlock it with Windows Hello / Touch ID** | The key is saved on this computer, and your operating system asks you to verify (Windows Hello PIN, fingerprint or face; Touch ID or your Mac password) every time the app reads it. Other programs can't read it without that verification. |

The API key is never written to the settings file.

- **Windows:** the key is encrypted with a key derived from a Windows Hello
  credential (held by your computer's TPM) and stored in Windows
  Credential Manager. Requires Windows Hello to be set up
  (*Settings → Accounts → Sign-in options*).
- **macOS:** the key is stored in the system keychain with a
  Touch ID / password requirement, and never leaves this Mac. Requires the
  signed app from the Releases page.

If neither is available, the app only offers the first option.

Versions before 1.1 saved the key without this protection. The new version
removes such a saved key and offers to save it again with protection.

## Output

PDFs are saved into a folder named after the form and the dates you chose,
for example:

    <download folder>/lqh_2026-01-01_to_2026-01-31/

Each file is named after the submission time and reference number. If you
run the same download again, PDFs that were already downloaded are skipped,
so it's safe to re-run to pick up new submissions. The tool pauses briefly
between downloads so it doesn't overload FormSmarts' servers.

## Command-line tool

Requires Python 3.9+.

    python3 -m venv .venv
    source .venv/bin/activate          # Windows: .venv\Scripts\activate
    pip install .

    fs-pdf-downloader --configure       # one-time setup
    fs-pdf-downloader                   # interactive download
    fs-pdf-downloader --form-id lqh --start-date 2026-01-01 --end-date 2026-01-31
    fs-pdf-downloader --forget-key      # delete the saved API key

The command-line tool shares settings with the desktop app. On Windows it
can use Windows Hello. On macOS, Touch ID storage is only available to the
signed desktop app, so the command-line tool asks for the key each time.

Settings (download folder, account ID) are saved to:

- Windows: `%APPDATA%\FormSmartsPDFDownloader\config.json`
- macOS: `~/Library/Application Support/FormSmartsPDFDownloader/config.json`
- Linux: `~/.config/FormSmartsPDFDownloader/config.json`

### Windows install script

As an alternative to the desktop app, `windows\install.bat` sets up the
command-line tool for the current user: it installs Python if needed,
creates a private environment, and adds a *FormSmarts PDF Downloader*
shortcut to the Desktop. `windows\uninstall.bat` removes it, along with
your saved settings and API key. PDFs you've downloaded are not deleted.

## Building the desktop app

Builds run on GitHub Actions (`.github/workflows/build.yml`) when a `v*`
tag is pushed, producing a draft release with both apps. To build locally:

    pip install . pyinstaller
    python packaging/build.py

PyInstaller can't cross-compile, so the Windows app has to be built on
Windows and the macOS app on a Mac.

### macOS signing

Touch ID key storage only works in an app signed with a Developer ID and an
embedded provisioning profile. To set that up:

1. In the Apple Developer portal, register the App ID
   `com.formsmarts.pdfdownloader` and create a **Developer ID**
   provisioning profile for it.
2. Add these repository secrets:

   | Secret | Value |
   | --- | --- |
   | `MACOS_CERT_P12` | base64 of the *Developer ID Application* certificate + key (.p12) |
   | `MACOS_CERT_PASSWORD` | password of the .p12 |
   | `MACOS_SIGN_IDENTITY` | the identity name, e.g. `Developer ID Application: <Name> (<TEAMID>)` |
   | `APPLE_TEAM_ID` | your team ID |
   | `MACOS_PROVISIONING_PROFILE` | base64 of the provisioning profile |
   | `NOTARY_KEY` | base64 of an App Store Connect API key (.p8), for notarization |
   | `NOTARY_KEY_ID`, `NOTARY_ISSUER_ID` | that API key's ID and issuer ID |

Without these secrets, the workflow produces an unsigned macOS build. It
runs, but only offers the "don't save" option, and macOS warns that it
comes from an unidentified developer.

To sign locally, set the same values as environment variables
(`MACOS_PROVISIONING_PROFILE` and `NOTARY_KEY_PATH` as file paths), run
`packaging/build.py`, then `packaging/macos/sign_and_notarize.sh`.

## Support

If anything goes wrong, note the exact message and contact
[FormSmarts support](https://formsmarts.com/form-builder-support#contact).
