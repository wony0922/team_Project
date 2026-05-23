@echo off
title DB-Buddy Desktop
echo Starting DB-Buddy Desktop Application...
cd /d "%~dp0"

rem -------------------------------------------------
rem Search for Python executable (venv / .venv / system Python)
rem -------------------------------------------------
set "PYTHON_EXE="

if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
    echo [INFO] Detected venv virtual environment.
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    echo [INFO] Detected .venv virtual environment.
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_EXE=python"
        echo [INFO] Using system Python.
    ) else (
        echo [ERROR] Python not found.
        echo         Please create a venv/.venv environment or add Python to your PATH.
        pause
        exit /b 1
    )
)

echo [INFO] Using: %PYTHON_EXE%

rem -------------------------------------------------
rem Check and install required packages
rem -------------------------------------------------
%PYTHON_EXE% -c "import webview" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing required packages...
    %PYTHON_EXE% -m pip install -r requirements.txt pywebview
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install packages.
        pause
        exit /b 1
    )
)

rem -------------------------------------------------
rem Run Desktop App
rem -------------------------------------------------
%PYTHON_EXE% desktop_app.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] An error occurred while running the application.
    pause
)
