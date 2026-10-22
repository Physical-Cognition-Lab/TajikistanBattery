@echo off
title Hide and Seek
cd /d "%~dp0.."
pixi run hide-and-seek
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
    echo Study stopped with error code %RC%.
) else (
    echo Study finished.
)
echo Press any key to close this window.
pause >nul
exit /b %RC%
