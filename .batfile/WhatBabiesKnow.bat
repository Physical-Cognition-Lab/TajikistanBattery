@echo off
title What Babies Know
cd /d "%~dp0.."
pixi run what-babies-know
if errorlevel 1 pause
