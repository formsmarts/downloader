#Requires -Version 5.1
<#
  Installs (or updates) FormSmarts Downloader for the current Windows
  user. Safe to re-run at any time - it will download Python only if it
  isn't already usable, and will always refresh the app's module
  dependencies.

  What it does:
    1. Locates a usable Python 3.9+, installing it (via winget, or the
       official python.org installer) if none is found.
    2. Creates a private virtual environment under
       %LOCALAPPDATA%\FormSmartsDownloader\venv
    3. Installs the application and its dependencies (formsmarts, keyring, Windows Hello support)
       into that virtual environment via pip - never system-wide, and
       never relying on the current working directory to find the app.
    4. Creates a "FormSmarts Downloader" shortcut on the Desktop that
       runs the installed console-script entry point directly.
#>

$ErrorActionPreference = "Stop"

$MinPythonVersion = [version]"3.9.0"
$PythonInstallerVersion = "3.12.6"
$PythonInstallerUrl = "https://www.python.org/ftp/python/$PythonInstallerVersion/python-$PythonInstallerVersion-amd64.exe"

$ScriptDir     = $PSScriptRoot
$AppSourceDir  = Split-Path -Parent $ScriptDir
$InstallDir    = Join-Path $env:LOCALAPPDATA "FormSmartsDownloader"
$VenvDir       = Join-Path $InstallDir "venv"
$VenvPython    = Join-Path $VenvDir "Scripts\python.exe"
$AppExe        = Join-Path $VenvDir "Scripts\fs-downloader.exe"
$DesktopDir    = [Environment]::GetFolderPath("Desktop")
$LauncherPath  = Join-Path $DesktopDir "FormSmarts Downloader.bat"
# Version 1.0 was named "FormSmarts PDF Downloader".
$LegacyInstallDir   = Join-Path $env:LOCALAPPDATA "FormSmartsPDFDownloader"
$LegacyLauncherPath = Join-Path $DesktopDir "FormSmarts PDF Downloader.bat"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Get-PythonVersion([string]$exe, [string[]]$extraArgs = @()) {
    try {
        $checkArgs = $extraArgs + @("-c", "import sys; print('{}.{}.{}'.format(*sys.version_info[:3]))")
        $raw = & $exe @checkArgs 2>$null
        if ($LASTEXITCODE -eq 0 -and $raw) { return [version]$raw.Trim() }
    } catch { }
    return $null
}

function Find-ExistingPython {
    # Prefer the official launcher, then plain "python" on PATH.
    foreach ($candidate in @(
        @{ Cmd = "py"; Args = @("-3") },
        @{ Cmd = "python"; Args = @() },
        @{ Cmd = "python3"; Args = @() }
    )) {
        $cmd = Get-Command $candidate.Cmd -ErrorAction SilentlyContinue
        if ($cmd) {
            $version = Get-PythonVersion $cmd.Source $candidate.Args
            if ($version -and $version -ge $MinPythonVersion) {
                return @{ Launcher = $cmd.Source; LauncherArgs = $candidate.Args }
            }
        }
    }

    # Fall back to common install locations that may not yet be on PATH
    # (e.g. right after a fresh install in the same session).
    $searchRoots = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python"),
        "$env:ProgramFiles\Python*",
        "${env:ProgramFiles(x86)}\Python*"
    )
    foreach ($root in $searchRoots) {
        $candidates = Get-ChildItem -Path $root -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue
        foreach ($candidate in $candidates) {
            $version = Get-PythonVersion $candidate.FullName
            if ($version -and $version -ge $MinPythonVersion) {
                return @{ Launcher = $candidate.FullName; LauncherArgs = @() }
            }
        }
    }
    return $null
}

function Install-Python {
    Write-Step "Python 3.9+ not found - installing Python $PythonInstallerVersion"

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "Trying winget..."
        try {
            $wingetArgs = @(
                "install", "-e", "--id", "Python.Python.3.12", "--silent",
                "--accept-package-agreements", "--accept-source-agreements"
            )
            & winget @wingetArgs
            if ($LASTEXITCODE -eq 0) {
                $found = Find-ExistingPython
                if ($found) { return $found }
            }
        } catch {
            Write-Host "winget install failed, falling back to direct download." -ForegroundColor Yellow
        }
    }

    Write-Host "Downloading the official Python installer from python.org..."
    $installerPath = Join-Path $env:TEMP "python-$PythonInstallerVersion-amd64.exe"
    Invoke-WebRequest -Uri $PythonInstallerUrl -OutFile $installerPath -UseBasicParsing

    Write-Host "Running the Python installer (this installs for your user only)..."
    $proc = Start-Process -FilePath $installerPath -ArgumentList @(
        "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1"
    ) -Wait -PassThru
    Remove-Item $installerPath -ErrorAction SilentlyContinue

    if ($proc.ExitCode -ne 0) {
        throw "The Python installer exited with code $($proc.ExitCode)."
    }

    $found = Find-ExistingPython
    if (-not $found) {
        throw (
            "Python was installed but could not be located automatically. " +
            "Please close this window, open a new one, and run install.bat again."
        )
    }
    return $found
}

# ---------------------------------------------------------------------------

if ((Test-Path $LegacyInstallDir) -or (Test-Path $LegacyLauncherPath)) {
    Write-Step "Removing the previous version (FormSmarts PDF Downloader)"
    # Settings and the saved API key are migrated by the app itself.
    Remove-Item $LegacyInstallDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $LegacyLauncherPath -Force -ErrorAction SilentlyContinue
}

Write-Step "Looking for Python"
$python = Find-ExistingPython
if (-not $python) {
    $python = Install-Python
}
Write-Host "Using Python: $($python.Launcher) $($python.LauncherArgs -join ' ')"

Write-Step "Creating the private virtual environment"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
if (-not (Test-Path $VenvPython)) {
    $launcherArgs = $python.LauncherArgs
    & $python.Launcher @launcherArgs -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the virtual environment." }
}

Write-Step "Installing/updating the application and its dependencies"
# Installed via pip (not just copied) so it's found on sys.path regardless
# of the working directory the Desktop shortcut is launched from.
& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install --upgrade $AppSourceDir
if ($LASTEXITCODE -ne 0) { throw "Failed to install the application and its dependencies." }

Write-Step "Creating the Desktop shortcut"
@"
@echo off
"$AppExe" %*
pause
"@ | Set-Content -Path $LauncherPath -Encoding ASCII
Write-Host "Created: $LauncherPath"

Write-Step "Installation complete"
Write-Host "You can now double-click 'FormSmarts Downloader' on your Desktop"
Write-Host "any time you want to download submission PDFs."
Write-Host ""

$doConfigure = Read-Host "Set up your download folder and API key now? [Y/n]"
if ($doConfigure -eq "" -or $doConfigure -match "^[Yy]") {
    & $AppExe --configure
}
