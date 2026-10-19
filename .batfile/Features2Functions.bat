@echo off
title Features to Functions
cd /d "%~dp0.."
pixi run features-to-functions
if errorlevel 1 pause
