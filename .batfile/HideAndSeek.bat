@echo off
title Hide and Seek
cd /d "%~dp0.."
pixi run hide-and-seek
if errorlevel 1 pause
