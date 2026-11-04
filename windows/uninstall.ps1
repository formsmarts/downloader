#Requires -Version 5.1
<#
  Removes FormSmarts Downloader from the current Windows user account:
    - The private virtual environment / installed application
      (%LOCALAPPDATA%\FormSmartsDownloader)
    - Saved settings (download folder, account ID)
      (%APPDATA%\FormSmartsDownloader)
    - The saved API key (Windows Credential Manager) and Windows Hello key
    - The Desktop shortcut

  PDFs already downloaded are left untouched - they live in whatever
  download folder was configured, not in any of the locations above.
#>

$ErrorActionPreference = "Stop"

$InstallDir   = Join-Path $env:LOCALAPPDATA "FormSmartsDownloader"
$ConfigDir    = Join-Path $env:APPDATA "FormSmartsDownloader"
$DesktopDir   = [Environment]::GetFolderPath("Desktop")
$LauncherPath = Join-Path $DesktopDir "FormSmarts Downloader.bat"
# Version 1.0 was named "FormSmarts PDF Downloader".
$LegacyPaths  = @(
    (Join-Path $env:LOCALAPPDATA "FormSmartsPDFDownloader"),
    (Join-Path $env:APPDATA "FormSmartsPDFDownloader"),
    (Join-Path $DesktopDir "FormSmarts PDF Downloader.bat")
)

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

Write-Host "This will remove FormSmarts Downloader from this computer:"
Write-Host "  - The application and its private Python environment"
Write-Host "  - Your saved download folder / account ID settings"
Write-Host "  - Your saved API key (if any) and the app's Windows Hello key"
Write-Host "  - The Desktop shortcut"
Write-Host ""
Write-Host "PDFs you've already downloaded will NOT be deleted." -ForegroundColor Yellow
Write-Host ""
$confirm = Read-Host "Continue? [y/N]"
if ($confirm -notmatch "^[Yy]") {
    Write-Host "Cancelled. Nothing was removed."
    exit 0
}

Write-Step "Removing the saved API key"
$AppExe = Join-Path $InstallDir "venv\Scripts\fs-downloader.exe"
if (Test-Path $AppExe) {
    # Removes the saved key from Credential Manager and the app's Windows
    # Hello key.
    & $AppExe --forget-key
} else {
    Write-Host "No installed application found - nothing to remove."
}

Write-Step "Removing the application"
if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
    Write-Host "Removed: $InstallDir"
} else {
    Write-Host "Nothing found at: $InstallDir"
}

Write-Step "Removing saved settings"
if (Test-Path $ConfigDir) {
    Remove-Item $ConfigDir -Recurse -Force
    Write-Host "Removed: $ConfigDir"
} else {
    Write-Host "Nothing found at: $ConfigDir"
}

Write-Step "Removing the Desktop shortcut"
if (Test-Path $LauncherPath) {
    Remove-Item $LauncherPath -Force
    Write-Host "Removed: $LauncherPath"
} else {
    Write-Host "No shortcut found at: $LauncherPath"
    Write-Host "(if you moved or renamed it, delete it manually)"
}

foreach ($path in $LegacyPaths) {
    if (Test-Path $path) {
        Remove-Item $path -Recurse -Force
        Write-Host "Removed (previous version): $path"
    }
}

Write-Step "Uninstall complete"
Write-Host "FormSmarts Downloader has been removed from this computer."
