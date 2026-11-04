# FormSmarts Downloader

Downloads the PDF version of your [FormSmarts](https://formsmarts.com) form
submissions, for a form and date range you choose, into a folder on your
computer.

It comes as a desktop app for Windows and macOS, and as a command-line tool.

## Desktop app

Download the latest version from the
[Releases](https://github.com/formsmarts/downloader/releases) page:

- **Windows:** `FormSmarts-Downloader-<version>-windows-x64.exe`.
  Double-click it to run it. No installation is needed.
- **macOS** (Apple Silicon): `FormSmarts-Downloader-<version>-macos-arm64.dmg`.
  Open it and drag **FormSmarts Downloader** onto the Applications folder.

On first launch, fill in **Settings**:

- **Download folder:** where PDFs are saved.
- **Account ID:** your FormSmarts account ID (looks like `FSA-123456`),
  found under *Account Overview* in your FormSmarts account.
- **API key:** found under *Security Settings* in your FormSmarts account.

Then enter a **Form ID** and a date range and click **Download**.

## Where your API key is stored

You choose one of two options:

| Option | What happens |
| --- | --- |
| **Most secure:** don't save the API key | The key is never saved. You enter it once each time you open the app. |
| **Save the API key, unlock it with Windows Hello / Touch ID** | The key is saved on this computer, and your operating system asks you to verify (Windows Hello PIN, fingerprint or face; Touch ID or your Mac password) every time the app reads it. Other programs can't read it without that verification. |

The API key is never written to the settings file.

- **Windows:** the key is locked with Windows Hello, the same PIN,
  fingerprint or face recognition you use to sign in to Windows. Windows
  keeps the unlocking key in security hardware built into your computer
  and blocks repeated wrong guesses. Windows Hello needs to be set up
  (*Settings → Accounts → Sign-in options*).
- **macOS:** the key is stored in your Mac's keychain (where macOS keeps
  your passwords), locked with Touch ID or your Mac password. It never
  leaves this Mac. This requires the app from the Releases page.

If neither is available, the app only offers the first option.

Version 1.0 saved the key without this protection. The new version
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

    fs-downloader --configure       # one-time setup
    fs-downloader                   # interactive download
    fs-downloader --form-id lqh --start-date 2026-01-01 --end-date 2026-01-31
    fs-downloader --forget-key      # delete the saved API key

The command-line tool shares settings with the desktop app. On Windows it
can use Windows Hello. On macOS, Touch ID storage is only available to the
signed desktop app, so the command-line tool asks for the key each time.

Settings (download folder, account ID) are saved to:

- Windows: `%APPDATA%\FormSmartsDownloader\config.json`
- macOS: `~/Library/Application Support/FormSmartsDownloader/config.json`
- Linux: `~/.config/FormSmartsDownloader/config.json`

### Windows install script

As an alternative to the desktop app, `windows\install.bat` sets up the
command-line tool for the current user: it installs Python if needed,
creates a private environment, and adds a *FormSmarts Downloader*
shortcut to the Desktop. `windows\uninstall.bat` removes it, along with
your saved settings and API key. PDFs you've downloaded are not deleted.

## Support

If anything goes wrong, note the exact message and contact
[FormSmarts support](https://formsmarts.com/form-builder-support#contact).
