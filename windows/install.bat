@echo off
rem Double-click this file to install/update FormSmarts PDF Downloader.
rem It downloads Python (if needed) and all module dependencies, then
rem sets up a Desktop shortcut you can use from now on.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
echo.
pause
