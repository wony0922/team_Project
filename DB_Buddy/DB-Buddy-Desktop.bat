@echo off
title DB-Buddy Desktop
echo Starting DB-Buddy Desktop Application...
cd /d "%~dp0"

rem -------------------------------------------------
rem Search for Python executable (prefer local .venv)
rem -------------------------------------------------
set "PYTHON_EXE="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    echo [INFO] Detected .venv virtual environment.
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
    echo [INFO] Detected venv virtual environment.
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        echo [INFO] Using system Python to create local virtual environment.
        echo [INFO] Creating .venv ...
        python -m venv .venv
        if %errorlevel% neq 0 (
            echo [ERROR] Failed to create .venv.
            pause
            exit /b 1
        )
        set "PYTHON_EXE=.venv\Scripts\python.exe"
    ) else (
        echo [ERROR] Python not found.
        echo         Please install Python or add it to your PATH.
        pause
        exit /b 1
    )
)

echo [INFO] Using: %PYTHON_EXE%

rem -------------------------------------------------
rem Run dependency bootstrap
rem -------------------------------------------------
%PYTHON_EXE% bootstrap.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] An error occurred while running the application.
    pause
)
