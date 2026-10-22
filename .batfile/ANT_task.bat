@echo off
title ANT Task
cd /d "%~dp0.."
pixi run ant-task
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
