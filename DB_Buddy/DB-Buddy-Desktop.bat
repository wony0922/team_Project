@echo off
title DB-Buddy Desktop
echo Starting DB-Buddy Desktop Application...
cd /d "%~dp0"
venv\Scripts\python.exe desktop_app.py
