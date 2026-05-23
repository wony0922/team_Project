@echo off
title DB-Buddy Desktop
echo Starting DB-Buddy Desktop Application...
cd /d "%~dp0"

rem -------------------------------------------------
rem Python 실행 환경 탐색 (venv / .venv / 시스템 Python)
rem -------------------------------------------------
set "PYTHON_EXE="

if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
    echo [INFO] venv 가상환경을 감지했습니다.
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    echo [INFO] .venv 가상환경을 감지했습니다.
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_EXE=python"
        echo [INFO] 시스템 Python을 사용합니다.
    ) else (
        echo [ERROR] Python을 찾을 수 없습니다.
        echo         venv 또는 .venv 가상환경을 생성하거나, Python을 PATH에 추가해주세요.
        pause
        exit /b 1
    )
)

echo [INFO] Using: %PYTHON_EXE%

rem -------------------------------------------------
rem 필요 패키지 확인 및 자동 설치
rem -------------------------------------------------
%PYTHON_EXE% -c "import webview" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 필요한 패키지를 설치합니다...
    %PYTHON_EXE% -m pip install -r requirements.txt pywebview
    if %errorlevel% neq 0 (
        echo [ERROR] 패키지 설치에 실패했습니다.
        pause
        exit /b 1
    )
)

rem -------------------------------------------------
rem Desktop App 실행
rem -------------------------------------------------
%PYTHON_EXE% desktop_app.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 앱 실행 중 오류가 발생했습니다.
    pause
)
