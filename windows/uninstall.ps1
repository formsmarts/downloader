#Requires -Version 5.1
<#
  Removes FormSmarts PDF Downloader from the current Windows user account:
    - The private virtual environment / installed application
      (%LOCALAPPDATA%\FormSmartsPDFDownloader)
    - Saved settings (download folder, account ID)
      (%APPDATA%\FormSmartsPDFDownloader)
    - The saved API key, if any was saved to Windows Credential Manager
    - The Desktop shortcut

  PDFs already downloaded are left untouched - they live in whatever
  download folder was configured, not in any of the locations above.
#>

$ErrorActionPreference = "Stop"

$InstallDir   = Join-Path $env:LOCALAPPDATA "FormSmartsPDFDownloader"
$VenvPython   = Join-Path $InstallDir "venv\Scripts\python.exe"
$ConfigDir    = Join-Path $env:APPDATA "FormSmartsPDFDownloader"
$ConfigPath   = Join-Path $ConfigDir "config.json"
$DesktopDir   = [Environment]::GetFolderPath("Desktop")
$LauncherPath = Join-Path $DesktopDir "FormSmarts PDF Downloader.bat"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

Write-Host "This will remove FormSmarts PDF Downloader from this computer:"
Write-Host "  - The application and its private Python environment"
Write-Host "  - Your saved download folder / account ID settings"
Write-Host "  - Your saved API key (if one was saved to Windows Credential Manager)"
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
if (Test-Path $VenvPython) {
    $accountId = $null
    if (Test-Path $ConfigPath) {
        try {
            $accountId = (Get-Content $ConfigPath -Raw | ConvertFrom-Json).account_id
        } catch { }
    }
    if ($accountId) {
        $pyCode = @"
import keyring
try:
    keyring.delete_password('FormSmarts PDF Downloader', '$accountId')
except Exception:
    pass
"@
        & $VenvPython -c $pyCode
        Write-Host "Removed the saved API key for account $accountId (if it existed)."
    } else {
        Write-Host "No saved account ID found - nothing to remove."
    }
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

Write-Step "Uninstall complete"
Write-Host "FormSmarts PDF Downloader has been removed from this computer."
