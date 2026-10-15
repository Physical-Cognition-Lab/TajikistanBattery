@echo off
title Information Gain
cd /d "%~dp0.."
pixi run information-gain
if errorlevel 1 pause
