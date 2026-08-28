@echo off
setlocal
title Restart passenger traffic application

set "RUNNER=%~dp0restart_app.ps1"
if not exist "%RUNNER%" (
    echo Restart script not found:
    echo %RUNNER%
    pause
    exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%RUNNER%"
if errorlevel 1 (
    echo.
    echo Application restart failed. See the message above.
    pause
    exit /b 1
)

exit /b 0
